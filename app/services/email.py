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
    html_body: Optional[str] = None,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None
):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email or settings.SMTP_USER
        msg["To"] = ", ".join(to_emails)
        
        if reply_to:
            msg["Reply-To"] = reply_to
        
        # Add text part
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)
        
        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_PORT == 587:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_emails}")
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise EmailDeliveryError(f"Failed to send email: {str(e)}")

async def send_welcome_email(email: str, name: str, additional_data: Optional[dict] = None):
    """Send welcome email to new user"""
    subject = f"Welcome to {settings.PROJECT_NAME}!"
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Welcome to {settings.PROJECT_NAME}!</h2>
        <p>Dear {name},</p>
        <p>Welcome to our AI-powered virtual internship platform! We're excited to have you join our community.</p>
        <p>Here's what you can expect:</p>
        <ul>
            <li>Personalized learning paths tailored to your goals</li>
            <li>Expert mentorship from industry professionals</li>
            <li>Real-world projects to build your portfolio</li>
            <li>AI-powered feedback and assessment</li>
            <li>Certificates upon successful completion</li>
        </ul>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{settings.FRONTEND_URL}/login" 
               style="background-color: #007bff; color: white; padding: 12px 30px; 
                      text-decoration: none; border-radius: 5px; font-weight: bold;">
                Get Started Now
            </a>
        </div>
        <p>If you have any questions, our support team is here to help at 
           <a href="mailto:{settings.SUPPORT_EMAIL}">{settings.SUPPORT_EMAIL}</a></p>
        <p>Best regards,<br>The {settings.PROJECT_NAME} Team</p>
        <hr style="margin-top: 30px; border: none; border-top: 1px solid #eee;">
        <p style="font-size: 12px; color: #666;">
            This email was sent to {email}. If you didn't create an account, 
            you can safely ignore this email.
        </p>
    </div>
    """
    
    body = f"""
    Welcome to {settings.PROJECT_NAME}!
    
    Dear {name},
    
    Welcome to our AI-powered virtual internship platform! We're excited to have you join our community.
    
    What you can expect:
    - Personalized learning paths
    - Expert mentorship
    - Real-world projects
    - AI-powered feedback
    - Certificates upon completion
    
    Get started: {settings.FRONTEND_URL}/login
    
    Questions? Contact us at {settings.SUPPORT_EMAIL}
    
    Best regards,
    The {settings.PROJECT_NAME} Team
    """
    
    await send_email([email], subject, body, html_body)

async def send_password_reset_email(email: str, reset_token: str):
    """Send password reset email"""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    subject = f"Password Reset - {settings.PROJECT_NAME}"
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Password Reset Request</h2>
        <p>You have requested to reset your password for {settings.PROJECT_NAME}.</p>
        <p>Click the button below to reset your password:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background-color: #28a745; color: white; padding: 12px 30px; 
                      text-decoration: none; border-radius: 5px; font-weight: bold;">
                Reset Password
            </a>
        </div>
        <p>If you didn't request this password reset, you can safely ignore this email.</p>
        <p>This link will expire in 1 hour for security reasons.</p>
        <p>Best regards,<br>The {settings.PROJECT_NAME} Team</p>
    </div>
    """
    
    body = f"""
    Password Reset Request
    
    You have requested to reset your password for {settings.PROJECT_NAME}.
    
    Reset your password: {reset_url}
    
    If you didn't request this, you can safely ignore this email.
    This link expires in 1 hour.
    
    Best regards,
    The {settings.PROJECT_NAME} Team
    """
    
    await send_email([email], subject, body, html_body)
