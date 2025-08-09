import os
import uuid
import boto3
import aiofiles
from typing import List, Optional, Tuple
from fastapi import UploadFile
from PIL import Image
import hashlib
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import (
    FileUploadError,
    FileSizeExceededError,
    UnsupportedFileTypeError
)

class FileHandler:
    """Handle file uploads, validation, and storage"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_BUCKET_NAME
        self.allowed_extensions = settings.ALLOWED_FILE_TYPES
        self.max_file_size = settings.MAX_FILE_SIZE
    
    async def validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file"""
        
        # Check file size
        file_size = 0
        content = await file.read()
        file_size = len(content)
        await file.seek(0)  # Reset file pointer
        
        if file_size > self.max_file_size:
            raise FileSizeExceededError(file_size, self.max_file_size)
        
        # Check file extension
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ""
        if file_extension not in self.allowed_extensions:
            raise UnsupportedFileTypeError(file_extension, self.allowed_extensions)
        
        return True
    
    async def upload_to_s3(
        self, 
        file: UploadFile, 
        folder: str = "uploads",
        custom_filename: Optional[str] = None
    ) -> str:
        """Upload file to S3 and return URL"""
        
        try:
            await self.validate_file(file)
            
            # Generate unique filename
            if custom_filename:
                filename = custom_filename
            else:
                file_extension = file.filename.split('.')[-1].lower()
                unique_id = str(uuid.uuid4())
                filename = f"{unique_id}.{file_extension}"
            
            # Create S3 key
            s3_key = f"{folder}/{datetime.now().year}/{datetime.now().month:02d}/{filename}"
            
            # Upload to S3
            file_content = await file.read()
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=file.content_type
            )
            
            # Generate file URL
            file_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            
            return file_url
            
        except Exception as e:
            raise FileUploadError(f"Failed to upload file: {str(e)}")
    
    async def upload_resume(self, file: UploadFile, intern_id: int) -> str:
        """Upload resume file"""
        
        # Validate file type for resumes
        allowed_resume_types = ['pdf', 'doc', 'docx']
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ""
        
        if file_extension not in allowed_resume_types:
            raise UnsupportedFileTypeError(file_extension, allowed_resume_types)
        
        custom_filename = f"resume_intern_{intern_id}.{file_extension}"
        return await self.upload_to_s3(file, "resumes", custom_filename)
    
    async def upload_task_files(self, files: List[UploadFile], task_id: int) -> List[str]:
        """Upload multiple task submission files"""
        
        file_urls = []
        for i, file in enumerate(files):
            file_extension = file.filename.split('.')[-1].lower() if file.filename else ""
            custom_filename = f"task_{task_id}_file_{i+1}.{file_extension}"
            file_url = await self.upload_to_s3(file, "task_submissions", custom_filename)
            file_urls.append(file_url)
        
        return file_urls
    
    async def upload_profile_image(self, file: UploadFile, user_id: int) -> str:
        """Upload and process profile image"""
        
        # Validate image file
        allowed_image_types = ['jpg', 'jpeg', 'png', 'gif']
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ""
        
        if file_extension not in allowed_image_types:
            raise UnsupportedFileTypeError(file_extension, allowed_image_types)
        
        # Process image (resize, optimize)
        processed_file = await self.process_image(file)
        
        custom_filename = f"profile_{user_id}.{file_extension}"
        return await self.upload_to_s3(processed_file, "profile_images", custom_filename)
    
    async def process_image(self, file: UploadFile) -> UploadFile:
        """Process and optimize image"""
        
        try:
            # Read image
            image_content = await file.read()
            
            # Open with PIL
            with Image.open(io.BytesIO(image_content)) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save optimized image
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)
                
                # Create new UploadFile object
                return UploadFile(
                    filename=file.filename,
                    file=output,
                    content_type="image/jpeg"
                )
                
        except Exception as e:
            raise FileUploadError(f"Failed to process image: {str(e)}")
    
    async def delete_file(self, file_url: str) -> bool:
        """Delete file from S3"""
        
        try:
            # Extract S3 key from URL
            s3_key = file_url.split(f"{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return True
            
        except Exception as e:
            raise FileUploadError(f"Failed to delete file: {str(e)}")
    
    def generate_file_hash(self, content: bytes) -> str:
        """Generate MD5 hash for file content"""
        return hashlib.md5(content).hexdigest()
    
    async def save_local_file(self, file: UploadFile, directory: str) -> str:
        """Save file locally (for development)"""
        
        await self.validate_file(file)
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.split('.')[-1].lower()
        unique_id = str(uuid.uuid4())
        filename = f"{unique_id}.{file_extension}"
        file_path = os.path.join(directory, filename)
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        return file_path

# Global file handler instance
file_handler = FileHandler()
