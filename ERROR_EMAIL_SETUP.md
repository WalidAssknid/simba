# SIMBA Error Email Notification System

## Overview
The SIMBA application now automatically sends email notifications when 500 (Internal Server Error) errors occur. This helps administrators quickly identify and respond to critical system issues.

## Configuration

### Environment Variables
Make sure these environment variables are set in your `.env` file:

```env
EMAIL=your_email@gmail.com
EMAILAPPPWD=your_app_password
DEBUG=False  # Set to False in production to enable error emails
```

### Django Settings
The following settings are automatically configured in `simba/settings.py`:

- **ADMINS**: List of administrators who will receive error emails
- **EMAIL_BACKEND**: SMTP backend for sending emails
- **EMAIL_HOST**: Gmail SMTP server
- **LOGGING**: Configured to send errors to both console and email

## How It Works

### Automatic Error Detection
- The `ErrorEmailMiddleware` automatically catches all unhandled exceptions
- Only sends emails when `DEBUG=False` (production mode)
- Includes detailed error information:
  - Exception type and message
  - Request path, method, and user information
  - Client IP address and user agent
  - Request data (GET/POST parameters)
  - Full traceback
  - Session information

### Email Format
Error emails are sent in both plain text and HTML format with:
- Clear subject line: `[SIMBA] Server Error (500) on {hostname}`
- Detailed error information
- Request context
- Full stack trace
- Professional formatting with SIMBA branding

## Testing

### Method 1: Management Command
Test the email configuration with the management command:

```bash
# Test in development (DEBUG=True)
python manage.py test_error_email --force

# Test in production (DEBUG=False)
python manage.py test_error_email
```

### Method 2: Test Error Endpoint
Visit the test error endpoint (only available to admin users in production):

```
http://your-domain.com/test-error/
```

This will deliberately trigger a 500 error to test the email notification system.

### Method 3: Docker Environment
```bash
# Test from within Docker container
docker-compose exec web python manage.py test_error_email --force
```

## Security Features

### Data Sanitization
- Sensitive form fields (password, secret, token, key) are automatically hidden in emails
- Only essential request information is included
- Session keys are truncated for security

### Access Control
- Error emails only sent when `DEBUG=False` 
- Test endpoints require admin privileges in production
- Email sending failures are logged but don't cause additional errors

## Logging

### Error Logs
All errors are also logged to:
- Console (development)
- File: `logs/django_errors.log` (production)
- Email notifications (production)

### Log Levels
- `ERROR`: Server errors, email sending failures
- `INFO`: General application information
- `DEBUG`: Development debugging information

## Monitoring

### What Gets Reported
- ✅ 500 Internal Server Errors
- ✅ Unhandled Python exceptions
- ✅ Database connection errors
- ✅ Template rendering errors
- ✅ API endpoint failures

### What Doesn't Get Reported
- ❌ 404 Not Found errors
- ❌ 403 Forbidden errors
- ❌ User authentication failures
- ❌ Validation errors
- ❌ Expected business logic exceptions

## Troubleshooting

### Email Not Sending
1. Check environment variables: `EMAIL` and `EMAILAPPPWD`
2. Verify Gmail app password (not regular password)
3. Ensure `DEBUG=False` in production
4. Check `ADMINS` setting in Django configuration
5. Review console logs for email sending errors

### Testing Issues
1. Use `--force` flag for testing in development
2. Ensure admin user permissions for test endpoints
3. Check spam folder for test emails
4. Verify email credentials with management command

### Gmail Configuration
1. Enable 2-factor authentication on Gmail account
2. Generate app-specific password for SIMBA
3. Use app password in `EMAILAPPPWD` environment variable

## Production Recommendations

1. **Remove Test Endpoints**: Remove or secure the `/test-error/` endpoint in production
2. **Monitor Logs**: Regularly check `logs/django_errors.log` for issues
3. **Email Filtering**: Set up email filters to prioritize SIMBA error notifications
4. **Response Procedures**: Establish procedures for responding to error emails
5. **Rate Limiting**: Consider implementing rate limiting for error emails if needed

## Example Error Email

Subject: `[SIMBA] Server Error (500) on simba-refact.irit.fr`

The email will include:
- Error type and message
- Request details (path, method, user, IP)
- Full traceback
- Request parameters
- Session information
- Professional HTML formatting

This ensures administrators have all necessary information to quickly diagnose and resolve issues. 