# Drawtopia Email System - Setup Guide

## Overview

The Drawtopia transactional email system sends automated emails for various user actions and workflows. The system uses:

- **Gmail SMTP** for sending emails
- **Supabase** for email queue management
- **Asynchronous processing** via background workers
- **Automatic retry logic** with exponential backoff

## Email Types

The system supports the following transactional emails:

1. **Welcome Email** - Sent when a new user registers
2. **Parental Consent Verification** - Required for COPPA compliance when creating child profiles
3. **Book Completion Notification** - Sent when story generation completes (format-specific)
4. **Payment Success** - Confirms successful payment with details
5. **Payment Receipt** - Detailed receipt for tax/record purposes
6. **Payment Failed** - Alerts user to payment failure with retry options
7. **Subscription Cancelled** - Confirms subscription cancellation
8. **Subscription Renewal Reminder** - Sent 7 days before renewal
9. **Gift Notification** - Notifies recipient of incoming gift
10. **Gift Delivery** - Delivers completed gift story to recipient

## Setup Instructions

### 1. Configure Gmail SMTP

#### Option A: Gmail Account with App Password (Recommended)

1. Go to your Google Account settings: https://myaccount.google.com/
2. Navigate to **Security** → **2-Step Verification**
3. Enable 2-Step Verification if not already enabled
4. Go to **Security** → **App passwords**
5. Create a new app password for "Mail"
6. Copy the 16-character app password

#### Option B: Gmail Workspace Account

If using a Google Workspace account, you can use the same process or configure SMTP relay.

### 2. Update Environment Variables

Add the following to your `.env` file:

```env
# Email Service Configuration (Gmail SMTP)
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# General Email Settings
FROM_EMAIL=your.email@gmail.com
FROM_NAME=Drawtopia
FRONTEND_URL=http://localhost:5173
```

**Production Settings:**
```env
GMAIL_ADDRESS=noreply@yourdomain.com
GMAIL_APP_PASSWORD=your_production_app_password
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Drawtopia
FRONTEND_URL=https://yourdomain.com
```

### 3. Run Database Migration

Run the email queue migration to create the required table:

```bash
# Using Supabase CLI
supabase db push

# Or run the SQL directly in Supabase dashboard
# Copy contents from: drawtopia-frontend/email_queue_migration.sql
```

### 4. Start the Backend

The email system will automatically start with the backend:

```bash
cd drawtopia-backend
python -m uvicorn main:app --reload
```

You should see these log messages:
```
✅ Email service (Gmail SMTP) initialized successfully
✅ Email queue manager initialized
✅ Queue manager and batch processor initialized
✅ Background worker started
✅ Email background worker started
```

## Architecture

### Email Flow

```
User Action → API Endpoint → Email Queue (Supabase)
                                    ↓
                        Email Background Worker
                                    ↓
                        Gmail SMTP → Delivered
                                    ↓ (if failed)
                        Retry Logic (exponential backoff)
```

### Components

1. **email_service.py** - Email templates and sending logic
2. **email_queue.py** - Queue manager for asynchronous processing
3. **email_queue table** - Supabase table storing queued emails
4. **Email Background Worker** - Processes emails from queue every 10 seconds
5. **Retry Logic** - Automatic retries with exponential backoff (5 attempts)

### Priority Levels

Emails are processed based on priority (1-10, where 1 is highest):

- **Priority 1** - Payment confirmations, payment failures, parental consent
- **Priority 2** - Book completions, gift emails, receipts
- **Priority 3** - Welcome emails
- **Priority 5** - General notifications

## Email Triggers

### Automatic Triggers

| Event | Email Type | Trigger Location |
|-------|------------|------------------|
| User registration (first time) | Welcome | `main.py:3650` (auth sync) |
| Child profile creation | Parental Consent | (To be implemented) |
| Book generation complete | Book Completion | `batch_processor.py:90` |
| Stripe payment success | Payment Success + Receipt | `main.py:3530` (webhook) |
| Stripe payment failed | Payment Failed | `main.py:3640` (webhook) |
| Subscription cancelled | Subscription Cancelled | `main.py:3422` (webhook) |
| Gift order created | Gift Notification | (To be implemented) |
| Gift story complete | Gift Delivery | (To be implemented) |

### Manual Triggers

You can manually queue emails using the API or Python code:

```python
from email_queue import queue_welcome_email

# Queue a welcome email
await queue_welcome_email(
    supabase=supabase,
    to_email="user@example.com",
    customer_name="John Doe"
)
```

## Monitoring

### Check Email Queue Status

```python
# Get queue statistics
stats = email_queue_manager.get_queue_stats()
print(stats)
# Output: {'pending': 5, 'processing': 1, 'completed': 120, 'failed': 2}
```

### View Email Queue in Supabase

1. Go to Supabase Dashboard → Table Editor
2. Select `email_queue` table
3. View pending, processing, completed, or failed emails
4. Check `last_error` column for failed emails

### Common Issues

#### Email service not enabled
```
⚠️ Gmail SMTP not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env
```
**Solution**: Add Gmail credentials to `.env` file

#### Authentication failed
```
❌ Gmail authentication failed: (535, b'5.7.8 Username and Password not accepted')
```
**Solution**: 
- Verify App Password is correct (16 characters, no spaces)
- Ensure 2-Step Verification is enabled
- Generate a new App Password

#### Emails stuck in queue
```
Email queue processor already running
```
**Solution**: 
- Check if background worker is running
- Look for errors in logs
- Restart the backend service

## Testing

### Send Test Email

You can test the email system using the Python console:

```python
import asyncio
from email_service import email_service

async def test_email():
    result = await email_service.send_welcome_email(
        to_email="your.test@email.com",
        customer_name="Test User"
    )
    print(result)

asyncio.run(test_email())
```

### Test Email Queue

```python
from email_queue import EmailQueueManager
from supabase import create_client, Client

supabase = create_client("your_url", "your_key")
queue_manager = EmailQueueManager(supabase)

# Queue a test email
result = queue_manager.queue_email(
    email_type="welcome",
    to_email="test@example.com",
    email_data={"customer_name": "Test User"},
    priority=3
)
print(f"Queued email: {result}")
```

## Email Templates

All email templates are in `email_service.py`. Each template includes:

- **HTML version** - Rich, styled email
- **Plain text version** - Fallback for email clients without HTML support
- **Responsive design** - Works on mobile and desktop
- **Brand colors** - Purple gradient (#667eea to #764ba2)
- **Call-to-action buttons** - Clear next steps for users

### Customizing Templates

To customize email templates:

1. Open `email_service.py`
2. Find the template method (e.g., `send_book_completion_email`)
3. Edit the `html_content` or `text_content` strings
4. Test the changes by sending a test email

## Production Considerations

### Rate Limiting

Gmail SMTP has the following limits:
- **Free Gmail**: 500 emails per day
- **Google Workspace**: 2,000 emails per day

For higher volumes, consider:
- Transactional email service (SendGrid, Mailgun, Postmark)
- Multiple sender accounts with round-robin
- Dedicated email infrastructure

### Email Deliverability

To improve deliverability:

1. **SPF Record**: Add Gmail's SPF to your domain DNS
2. **DKIM**: Configure DKIM signing in Google Workspace
3. **DMARC**: Set up DMARC policy for your domain
4. **Monitor bounces**: Check failed emails in queue regularly
5. **Warm up**: Gradually increase sending volume when starting

### Monitoring Production

1. **Set up alerts** for failed emails (>10 failures)
2. **Monitor queue size** - alert if pending > 100
3. **Track delivery rates** - aim for >98% success
4. **Review unsubscribes** - add unsubscribe handling
5. **Check spam reports** - monitor sender reputation

## Future Enhancements

- [ ] Add unsubscribe functionality
- [ ] Implement email preferences (digest, frequency)
- [ ] Add email open/click tracking
- [ ] Support for HTML email builder/templates
- [ ] Switch to Resend or similar service for scalability
- [ ] Add email preview endpoint
- [ ] Implement A/B testing for subject lines
- [ ] Add multi-language support

## Support

For issues or questions:
- Check logs in `main.py` and `email_queue.py`
- Review Supabase `email_queue` table
- Contact: hello@drawtopia.ai

---

**Last Updated**: December 2024
**Version**: 1.0

