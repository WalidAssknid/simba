from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import EmailVerificationToken, PasswordResetToken
import logging

logger = logging.getLogger(__name__)


def send_email_verification(user, next_url=None):
    """
    Send email verification email to user
    """
    try:
        token = EmailVerificationToken.objects.create(user=user)
        
        verification_url = f"{settings.BASE_URL}/verify-email/{token.token}"
        if next_url:
            verification_url += f"?next={next_url}"
        
        subject = "Verify Your Email - Simba"
        
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Welcome to Simba!</h2>
                
                <p>Hello {user.username},</p>
                
                <p>Thank you for registering with Simba. To complete your registration and access all features, please verify your email address by clicking the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #d64000; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>
                
                <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #3498db;">{verification_url}</p>
                
                <p><strong>Important:</strong> This verification link will expire in 24 hours for security reasons.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="font-size: 14px; color: #666;">
                    If you didn't create an account with Simba, please ignore this email.
                </p>
                
                <p style="font-size: 14px; color: #666;">
                    Best regards,<br>
                    The Simba Team
                </p>
            </div>
        </body>
        </html>
        """
        
        plain_message = f"""
        Welcome to Simba!
        
        Hello {user.username},
        
        Thank you for registering with Simba. To complete your registration and access all features, please verify your email address by visiting this link:
        
        {verification_url}
        
        Important: This verification link will expire in 24 hours for security reasons.
        
        If you didn't create an account with Simba, please ignore this email.
        
        Best regards,
        The Simba Team
        """
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Email verification sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email verification to {user.email}: {str(e)}")
        return False


def send_password_reset_email(user):
    """
    Send password reset email to user
    """
    try:
        token = PasswordResetToken.objects.create(user=user)
        
        reset_url = f"{settings.BASE_URL}/reset-password/{token.token}"

        subject = "Password Reset - Simba"
        
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Password Reset Request</h2>
                
                <p>Hello {user.username},</p>
                
                <p>We received a request to reset your password for your Simba account. If you made this request, click the button below to set a new password:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #e74c3c; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                
                <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #e74c3c;">{reset_url}</p>
                
                <p><strong>Important:</strong> This reset link will expire in 1 hour for security reasons.</p>
                
                <p><strong>If you didn't request this password reset, please ignore this email.</strong> Your password will remain unchanged.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                
                <p style="font-size: 14px; color: #666;">
                    For security reasons, this link can only be used once and will expire after 1 hour.
                </p>
                
                <p style="font-size: 14px; color: #666;">
                    Best regards,<br>
                    The Simba Team
                </p>
            </div>
        </body>
        </html>
        """
        
        plain_message = f"""
        Password Reset Request
        
        Hello {user.username},
        
        We received a request to reset your password for your Simba account. If you made this request, visit this link to set a new password:
        
        {reset_url}
        
        Important: This reset link will expire in 1 hour for security reasons.
        
        If you didn't request this password reset, please ignore this email. Your password will remain unchanged.
        
        Best regards,
        The Simba Team
        """
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        return False 