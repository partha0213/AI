import os
import uuid
import hashlib
import magic
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import UploadFile, HTTPException
from PIL import Image
import aiofiles
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import FileUploadError, FileSizeExceededError, UnsupportedFileTypeError

class SecureFileHandler:
    """Enhanced secure file handling with comprehensive validation"""
    
    def __init__(self):
        self.s3_client = None
        if settings.AWS_ACCESS_KEY_ID:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
        
        # File type validation
        self.allowed_mime_types = {
            'application/pdf': ['.pdf'],
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
            'image/gif': ['.gif'],
            'application/msword': ['.doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
            'text/plain': ['.txt']
        }
        
        # Size limits per file type (in bytes)
        self.size_limits = {
            '.pdf': 10 * 1024 * 1024,   # 10MB
            '.doc': 5 * 1024 * 1024,    # 5MB
            '.docx': 5 * 1024 * 1024,   # 5MB
            '.jpg': 2 * 1024 * 1024,    # 2MB
            '.jpeg': 2 * 1024 * 1024,   # 2MB
            '.png': 2 * 1024 * 1024,    # 2MB
            '.gif': 1 * 1024 * 1024,    # 1MB
            '.txt': 1 * 1024 * 1024     # 1MB
        }
        
        # Quarantine directory for suspicious files
        self.quarantine_dir = Path("quarantine")
        self.quarantine_dir.mkdir(exist_ok=True)
    
    async def validate_file_security(self, file: UploadFile) -> Dict[str, Any]:
        """Comprehensive file security validation"""
        
        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        file_size = len(content)
        file_extension = Path(file.filename).suffix.lower() if file.filename else ""
        
        validation_result = {
            "is_safe": True,
            "warnings": [],
            "errors": [],
            "file_info": {
                "name": file.filename,
                "size": file_size,
                "extension": file_extension,
                "content_type": file.content_type
            }
        }
        
        # 1. File size validation
        if file_extension in self.size_limits:
            max_size = self.size_limits[file_extension]
            if file_size > max_size:
                validation_result["errors"].append(f"File size ({file_size}) exceeds limit ({max_size})")
                validation_result["is_safe"] = False
        
        # 2. MIME type validation using magic numbers
        try:
            detected_mime = magic.from_buffer(content, mime=True)
            validation_result["file_info"]["detected_mime"] = detected_mime
            
            if detected_mime not in self.allowed_mime_types:
                validation_result["errors"].append(f"File type {detected_mime} not allowed")
                validation_result["is_safe"] = False
            
            # Check if extension matches MIME type
            expected_extensions = self.allowed_mime_types.get(detected_mime, [])
            if file_extension not in expected_extensions:
                validation_result["warnings"].append(f"Extension {file_extension} doesn't match detected type {detected_mime}")
        
        except Exception as e:
            validation_result["errors"].append(f"Failed to detect file type: {str(e)}")
            validation_result["is_safe"] = False
        
        # 3. Malware scanning (basic signature detection)
        malware_signatures = [
            b'\x4d\x5a',  # PE executable
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'<script',  # Potential script injection
            b'javascript:',  # JavaScript protocol
            b'vbscript:',  # VBScript protocol
        ]
        
        content_lower = content.lower()
        for signature in malware_signatures:
            if signature in content_lower:
                validation_result["errors"].append("Potentially malicious content detected")
                validation_result["is_safe"] = False
                break
        
        # 4. Image-specific validation
        if detected_mime and detected_mime.startswith('image/'):
            try:
                with Image.open(file.file) as img:
                    # Check for reasonable image dimensions
                    width, height = img.size
                    if width > 10000 or height > 10000:
                        validation_result["warnings"].append("Unusually large image dimensions")
                    
                    # Check for embedded data (basic)
                    if hasattr(img, 'info') and img.info:
                        validation_result["file_info"]["metadata"] = str(img.info)
                
                await file.seek(0)  # Reset after PIL read
                
            except Exception as e:
                validation_result["errors"].append(f"Invalid image file: {str(e)}")
                validation_result["is_safe"] = False
        
        # 5. Generate file hash for integrity
        file_hash = hashlib.sha256(content).hexdigest()
        validation_result["file_info"]["sha256"] = file_hash
        
        return validation_result
    
    async def quarantine_file(self, file: UploadFile, reason: str) -> str:
        """Move suspicious file to quarantine"""
        
        quarantine_filename = f"{uuid.uuid4()}_{file.filename}"
        quarantine_path = self.quarantine_dir / quarantine_filename
        
        # Save file to quarantine
        content = await file.read()
        async with aiofiles.open(quarantine_path, 'wb') as f:
            await f.write(content)
        
        # Log quarantine action
        import logging
        logger = logging.getLogger("security")
        logger.warning(
            f"File quarantined",
            extra={
                "original_filename": file.filename,
                "quarantine_path": str(quarantine_path),
                "reason": reason,
                "file_size": len(content)
            }
        )
        
        return str(quarantine_path)
    
    async def process_and_upload_file(
        self,
        file: UploadFile,
        upload_path: str,
        allowed_types: Optional[List[str]] = None,
        max_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process and upload file with security validation"""
        
        # Security validation
        validation_result = await self.validate_file_security(file)
        
        if not validation_result["is_safe"]:
            # Quarantine unsafe file
            quarantine_path = await self.quarantine_file(
                file, 
                f"Security validation failed: {'; '.join(validation_result['errors'])}"
            )
            
            raise FileUploadError(
                f"File rejected due to security concerns: {'; '.join(validation_result['errors'])}"
            )
        
        # Generate secure filename
        secure_filename = self._generate_secure_filename(file.filename)
        full_path = f"{upload_path}/{secure_filename}"
        
        try:
            if self.s3_client:
                # Upload to S3
                content = await file.read()
                
                self.s3_client.put_object(
                    Bucket=settings.AWS_BUCKET_NAME,
                    Key=full_path,
                    Body=content,
                    ContentType=file.content_type,
                    Metadata={
                        'original_filename': file.filename,
                        'upload_timestamp': str(int(asyncio.get_event_loop().time())),
                        'file_hash': validation_result["file_info"]["sha256"]
                    }
                )
                
                file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{full_path}"
                
            else:
                # Local storage fallback
                local_path = Path("uploads") / upload_path
                local_path.mkdir(parents=True, exist_ok=True)
                
                content = await file.read()
                async with aiofiles.open(local_path / secure_filename, 'wb') as f:
                    await f.write(content)
                
                file_url = f"/uploads/{upload_path}/{secure_filename}"
            
            return {
                "success": True,
                "file_url": file_url,
                "secure_filename": secure_filename,
                "file_info": validation_result["file_info"],
                "warnings": validation_result["warnings"]
            }
            
        except Exception as e:
            # Log upload failure
            import logging
            logger = logging.getLogger("app")
            logger.error(f"File upload failed: {str(e)}")
            
            raise FileUploadError(f"File upload failed: {str(e)}")
    
    def _generate_secure_filename(self, original_filename: str) -> str:
        """Generate secure filename to prevent directory traversal"""
        
        if not original_filename:
            return f"{uuid.uuid4()}.bin"
        
        # Remove directory traversal attempts
        safe_filename = os.path.basename(original_filename)
        
        # Remove or replace dangerous characters
        safe_chars = []
        for char in safe_filename:
            if char.isalnum() or char in '.-_':
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        
        safe_filename = ''.join(safe_chars)
        
        # Ensure filename isn't too long
        if len(safe_filename) > 100:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:95] + ext
        
        # Add UUID prefix to prevent conflicts
        unique_prefix = str(uuid.uuid4())[:8]
        return f"{unique_prefix}_{safe_filename}"
    
    async def scan_with_clamav(self, file_path: str) -> Dict[str, Any]:
        """Scan file with ClamAV (if available)"""
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['clamscan', '--no-summary', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {"status": "clean", "result": result.stdout}
            elif result.returncode == 1:
                return {"status": "infected", "result": result.stdout}
            else:
                return {"status": "error", "result": result.stderr}
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            return {"status": "unavailable", "error": str(e)}

# Global secure file handler
secure_file_handler = SecureFileHandler()
