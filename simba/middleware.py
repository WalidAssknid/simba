from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.core.mail import mail_admins
from django.conf import settings
from django.utils.html import escape
import logging
import traceback
import sys

class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Activate English language
        translation.activate('en')
        request.LANGUAGE_CODE = 'en'
        
        response = self.get_response(request)
        
        # Deactivate translation after request
        translation.deactivate()
        
        return response

class ErrorEmailMiddleware(MiddlewareMixin):
    """
    Middleware to send detailed error emails when 500 errors occur
    """
    
    def process_exception(self, request, exception):
        """
        Process any unhandled exception and send email notification
        """
        # Only send emails in production or when DEBUG is False
        if settings.DEBUG or not hasattr(settings, 'ADMINS') or not settings.ADMINS:
            return None
            
        try:
            # Get detailed error information
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            
            # Prepare error details
            error_details = {
                'exception_type': exc_type.__name__ if exc_type else 'Unknown',
                'exception_message': str(exception),
                'request_path': request.get_full_path(),
                'request_method': request.method,
                'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous',
                'remote_addr': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
                'referer': request.META.get('HTTP_REFERER', 'None'),
                'traceback': ''.join(tb_lines),
                'request_data': self.get_request_data(request),
            }
            
            # Create email subject and message
            subject = f'[SIMBA] Server Error (500) on {request.get_host()}'
            
            message = self.format_error_message(error_details)
            
            # Send email to admins
            mail_admins(
                subject=subject,
                message=message,
                fail_silently=True,
                html_message=self.format_error_html(error_details)
            )
            
            # Log the error
            logger = logging.getLogger('simbaapp')
            logger.error(
                f"500 Error: {exception} | Path: {request.get_full_path()} | "
                f"Method: {request.method} | User: {getattr(request, 'user', 'Anonymous')} | "
                f"IP: {self.get_client_ip(request)}"
            )
            
        except Exception as email_error:
            # If email sending fails, log it but don't raise another exception
            logger = logging.getLogger('django')
            logger.error(f"Failed to send error email: {email_error}")
        
        return None  # Let Django handle the exception normally
    
    def get_client_ip(self, request):
        """Get the client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_request_data(self, request):
        """Get sanitized request data"""
        try:
            # Get GET parameters
            get_data = dict(request.GET.items()) if hasattr(request, 'GET') else {}
            
            # Get POST parameters (sanitize sensitive data)
            post_data = {}
            if hasattr(request, 'POST'):
                for key, value in request.POST.items():
                    # Hide sensitive fields
                    if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'token', 'key']):
                        post_data[key] = '***HIDDEN***'
                    else:
                        post_data[key] = value
            
            return {
                'GET': get_data,
                'POST': post_data,
                'session_key': getattr(request.session, 'session_key', 'None') if hasattr(request, 'session') else 'None'
            }
        except Exception:
            return {'error': 'Could not retrieve request data'}
    
    def format_error_message(self, error_details):
        """Format error details as plain text message"""
        message = f"""
SIMBA Server Error Report
========================

Error Type: {error_details['exception_type']}
Error Message: {error_details['exception_message']}

Request Information:
- Path: {error_details['request_path']}
- Method: {error_details['request_method']}
- User: {error_details['user']}
- IP Address: {error_details['remote_addr']}
- User Agent: {error_details['user_agent']}
- Referer: {error_details['referer']}

Request Data:
{error_details['request_data']}

Traceback:
{error_details['traceback']}

Please check the SIMBA application immediately.
        """.strip()
        
        return message
    
    def format_error_html(self, error_details):
        """Format error details as HTML message"""
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 20px; line-height: 1.6;">
            <h2 style="color: #d64000; border-bottom: 2px solid #d64000; padding-bottom: 10px;">
                🚨 SIMBA Server Error Report
            </h2>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #d64000; margin: 20px 0;">
                <h3 style="color: #721c24; margin-top: 0;">Error Details</h3>
                <p><strong>Type:</strong> {escape(error_details['exception_type'])}</p>
                <p><strong>Message:</strong> {escape(error_details['exception_message'])}</p>
            </div>
            
            <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #495057; margin-top: 0;">Request Information</h3>
                <p><strong>Path:</strong> {escape(error_details['request_path'])}</p>
                <p><strong>Method:</strong> {escape(error_details['request_method'])}</p>
                <p><strong>User:</strong> {escape(error_details['user'])}</p>
                <p><strong>IP Address:</strong> {escape(error_details['remote_addr'])}</p>
                <p><strong>User Agent:</strong> {escape(error_details['user_agent'][:100])}{'...' if len(error_details['user_agent']) > 100 else ''}</p>
                <p><strong>Referer:</strong> {escape(error_details['referer'])}</p>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #856404; margin-top: 0;">Request Data</h3>
                <pre style="background-color: white; padding: 10px; border: 1px solid #dee2e6; border-radius: 3px; overflow-x: auto;">
{escape(str(error_details['request_data']))}</pre>
            </div>
            
            <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #721c24; margin-top: 0;">Full Traceback</h3>
                <pre style="background-color: white; padding: 10px; border: 1px solid #f5c6cb; border-radius: 3px; overflow-x: auto; font-size: 12px;">
{escape(error_details['traceback'])}</pre>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding: 20px; background-color: #d1ecf1; border-radius: 5px;">
                <p style="color: #0c5460; font-weight: bold; margin: 0;">
                    Please check the SIMBA application immediately and resolve this issue.
                </p>
            </div>
        </body>
        </html>
        """.strip()
        
        return html_message
