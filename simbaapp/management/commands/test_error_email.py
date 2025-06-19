from django.core.management.base import BaseCommand
from django.core.mail import mail_admins
from django.conf import settings
from django.utils.html import escape
import logging


class Command(BaseCommand):
    help = 'Test the error email functionality by sending a test error notification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force send email even if DEBUG is True',
        )

    def handle(self, *args, **options):
        """Send a test error email to verify the configuration"""
        
        if settings.DEBUG and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    'DEBUG is True. Use --force to send test email anyway.'
                )
            )
            return

        if not hasattr(settings, 'ADMINS') or not settings.ADMINS:
            self.stdout.write(
                self.style.ERROR(
                    'No ADMINS configured in settings. Please add ADMINS to receive error emails.'
                )
            )
            return

        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            self.stdout.write(
                self.style.ERROR(
                    'Email credentials not configured. Please set EMAIL and EMAILAPPPWD environment variables.'
                )
            )
            return

        try:
            # Test error details
            error_details = {
                'exception_type': 'TestException',
                'exception_message': 'This is a test error to verify email notifications are working correctly.',
                'request_path': '/test/error/path',
                'request_method': 'GET',
                'user': 'test_user',
                'remote_addr': '127.0.0.1',
                'user_agent': 'Mozilla/5.0 (Test Agent)',
                'referer': 'https://simba.test/',
                'traceback': 'Traceback (most recent call last):\n  File "test.py", line 1, in <module>\n    raise TestException("Test error")\nTestException: Test error',
                'request_data': {'GET': {}, 'POST': {}, 'session_key': 'test_session_key'}
            }

            # Create email subject and message
            subject = f'[SIMBA TEST] Server Error Email Test'
            
            # Plain text message
            message = f"""
SIMBA Server Error Email Test
============================

This is a test email to verify that SIMBA error notifications are working correctly.

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

If you received this email, the error notification system is working correctly.
            """.strip()

            # HTML message
            html_message = f"""
            <html>
            <body style="font-family: Arial, sans-serif; margin: 20px; line-height: 1.6;">
                <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                    ✅ SIMBA Error Email Test
                </h2>
                
                <div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0;">
                    <h3 style="color: #155724; margin-top: 0;">Test Results</h3>
                    <p><strong>Status:</strong> Email system is working correctly</p>
                    <p><strong>Test Error Type:</strong> {escape(error_details['exception_type'])}</p>
                    <p><strong>Test Message:</strong> {escape(error_details['exception_message'])}</p>
                </div>
                
                <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">Sample Request Information</h3>
                    <p><strong>Path:</strong> {escape(error_details['request_path'])}</p>
                    <p><strong>Method:</strong> {escape(error_details['request_method'])}</p>
                    <p><strong>User:</strong> {escape(error_details['user'])}</p>
                    <p><strong>IP Address:</strong> {escape(error_details['remote_addr'])}</p>
                    <p><strong>User Agent:</strong> {escape(error_details['user_agent'])}</p>
                    <p><strong>Referer:</strong> {escape(error_details['referer'])}</p>
                </div>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">Sample Request Data</h3>
                    <pre style="background-color: white; padding: 10px; border: 1px solid #dee2e6; border-radius: 3px; overflow-x: auto;">
{escape(str(error_details['request_data']))}</pre>
                </div>
                
                <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #721c24; margin-top: 0;">Sample Traceback</h3>
                    <pre style="background-color: white; padding: 10px; border: 1px solid #f5c6cb; border-radius: 3px; overflow-x: auto; font-size: 12px;">
{escape(error_details['traceback'])}</pre>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding: 20px; background-color: #d1ecf1; border-radius: 5px;">
                    <p style="color: #0c5460; font-weight: bold; margin: 0;">
                        ✅ If you received this email, the SIMBA error notification system is working correctly!
                    </p>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                    <h4 style="color: #495057; margin-top: 0;">Configuration Details:</h4>
                    <p><strong>Email Backend:</strong> {escape(str(settings.EMAIL_BACKEND))}</p>
                    <p><strong>Email Host:</strong> {escape(str(settings.EMAIL_HOST))}</p>
                    <p><strong>Email Port:</strong> {escape(str(settings.EMAIL_PORT))}</p>
                    <p><strong>Use TLS:</strong> {escape(str(settings.EMAIL_USE_TLS))}</p>
                    <p><strong>From Email:</strong> {escape(str(settings.DEFAULT_FROM_EMAIL))}</p>
                    <p><strong>Admins:</strong> {escape(str([admin[1] for admin in settings.ADMINS]))}</p>
                </div>
            </body>
            </html>
            """.strip()

            # Send the test email
            mail_admins(
                subject=subject,
                message=message,
                fail_silently=False,
                html_message=html_message
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Test error email sent successfully to: {[admin[1] for admin in settings.ADMINS]}'
                )
            )

            # Also test logging
            logger = logging.getLogger('simbaapp')
            logger.error('Test error log entry - Error email functionality test')

            self.stdout.write(
                self.style.SUCCESS(
                    'Test error also logged to file successfully.'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to send test error email: {e}'
                )
            )
            
            # Log the email sending error
            logger = logging.getLogger('django')
            logger.error(f"Test error email failed: {e}") 