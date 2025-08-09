import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from app.core.config import settings
from app.core.exceptions import EmailDeliveryError

logger = logging.getLogger(__name__)

async def send_email(
    to_emails: List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None
):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = ", ".join(to_emails)
        
        # Add text part
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)
        
        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_emails}")
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise EmailDeliveryError(f"Failed to send email: {str(e)}")

async def send_welcome_email(email: str, name: str):
    """Send welcome email to new intern"""
    subject = f"Welcome to {settings.PROJECT_NAME}!"
    body = f"""
    Hi {name},
    
    Welcome to our AI Virtual Internship Platform! We're excited to have you join our program.
    
    You can access your dashboard at: https://your-domain.com
    
    Best regards,
    The Internship Team
    """
    
    await send_email([email], subject, body)
