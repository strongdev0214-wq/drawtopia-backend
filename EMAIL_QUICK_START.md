# 🚀 Email System Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Get Gmail App Password

1. Visit https://myaccount.google.com/security
2. Enable **2-Step Verification** (if not already enabled)
3. Go to **App passwords** → Select **Mail** → Generate
4. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### Step 2: Update .env File

Add these lines to `drawtopia-backend/.env`:

```env
# Email Configuration
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
FROM_EMAIL=your.email@gmail.com
FROM_NAME=Drawtopia
```

### Step 3: Run Database Migration

**Option A: Supabase Dashboard**
1. Open Supabase Dashboard → SQL Editor
2. Copy contents from `drawtopia-frontend/email_queue_migration.sql`
3. Click "Run"

**Option B: Supabase CLI**
```bash
supabase db push
```

### Step 4: Start Backend

```bash
cd drawtopia-backend
python -m uvicorn main:app --reload
```

✅ Look for these success messages:
```
✅ Email service (Gmail SMTP) initialized successfully
✅ Email queue manager initialized
✅ Email background worker started
```

### Step 5: Test It!

**Python Console Test:**

```python
import asyncio
from email_service import email_service

async def test():
    result = await email_service.send_welcome_email(
        to_email="your.test@gmail.com",  # ← Your email here
        customer_name="Test User"
    )
    print("Success!" if result.get("success") else "Failed!")

asyncio.run(test())
```

**Check Your Email** - You should receive a welcome email! 📧

---

## ✅ What's Implemented

✅ **11 Email Types**:
- Welcome
- Parental Consent
- Book Completion (2 formats)
- Payment Success
- Payment Receipt
- Payment Failed
- Subscription Cancelled
- Subscription Renewal Reminder
- Gift Notification
- Gift Delivery

✅ **Automatic Triggers**:
- User registration → Welcome email
- Payment success → Payment + Receipt emails
- Payment failed → Payment Failed email
- Book completion → Book Completion email
- Subscription cancelled → Cancellation email

✅ **Queue System**:
- Asynchronous processing (non-blocking)
- Automatic retries (5 attempts)
- Priority system (1-10)
- Background worker (every 10 seconds)
- Persistent queue (Supabase)

---

## 🎯 Trigger New Emails

### Welcome Email (Auto-triggered)
Automatically sent when new user registers

### Book Completion Email (Auto-triggered)
Automatically sent when book generation completes

### Payment Emails (Auto-triggered)
Automatically sent via Stripe webhooks

### Manual Trigger Example

```python
from email_queue import EmailQueueManager
from supabase import create_client

# Initialize
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
queue_manager = EmailQueueManager(supabase)

# Queue an email
result = queue_manager.queue_email(
    email_type="parental_consent",
    to_email="parent@example.com",
    email_data={
        "parent_name": "John Doe",
        "child_name": "Emma",
        "consent_link": "https://yourapp.com/consent/abc123"
    },
    priority=1
)

print(f"Queued: {result.get('id')}")
```

---

## 🔍 Monitor Queue

### View in Supabase Dashboard

1. Go to **Table Editor** → `email_queue`
2. Filter by status:
   - `pending` - Waiting to send
   - `processing` - Currently sending
   - `completed` - Successfully sent
   - `failed` - Failed after 5 retries

### Check Queue Stats (Python)

```python
stats = queue_manager.get_queue_stats()
print(stats)
# Output: {'pending': 2, 'processing': 0, 'completed': 45, 'failed': 0}
```

---

## 🐛 Troubleshooting

### "Email service not enabled"

**Problem**: Gmail credentials missing

**Solution**:
```bash
# Check .env file
cat .env | grep GMAIL

# Should show:
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

### "Authentication failed"

**Problem**: Invalid App Password

**Solution**:
1. Delete old app password in Google Account
2. Generate new app password
3. Update `.env` with new password (no spaces!)
4. Restart backend

### Emails not sending

**Problem**: Background worker not running

**Solution**:
```bash
# Check logs for:
✅ Email background worker started

# If missing, restart backend
```

### Emails stuck in "pending"

**Problem**: Processing error

**Solution**:
1. Check Supabase → `email_queue` table
2. Look at `last_error` column
3. Check backend logs for errors
4. Restart backend if needed

---

## 📖 Full Documentation

- **Setup Guide**: `EMAIL_SYSTEM_SETUP.md`
- **Implementation Summary**: `EMAIL_IMPLEMENTATION_SUMMARY.md`
- **Requirements**: See attached requirements document

---

## 🎨 Customize Email Templates

**Location**: `email_service.py`

**Example** - Update welcome email:

```python
# Find: send_welcome_email() method
# Edit: html_content and text_content strings
# Test: Send test email to verify changes
```

All emails use:
- **Brand Colors**: Purple gradient (#667eea → #764ba2)
- **Responsive Design**: Works on mobile + desktop
- **HTML + Text**: Fallback for all email clients

---

## 🚀 Production Deploy

Before going live:

- [ ] Use dedicated Gmail account (not personal)
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Run migration in production Supabase
- [ ] Test all email types in production
- [ ] Configure SPF/DKIM for your domain
- [ ] Set up monitoring/alerts

**Gmail Limits**:
- Free Gmail: 500 emails/day
- Google Workspace: 2,000 emails/day

For higher volume, consider:
- Resend (recommended)
- SendGrid
- Mailgun
- Postmark

---

## 📊 Email Queue Table Schema

```sql
CREATE TABLE email_queue (
    id BIGSERIAL PRIMARY KEY,
    email_type TEXT NOT NULL,           -- welcome, payment_success, etc.
    to_email TEXT NOT NULL,             -- recipient@example.com
    email_data JSONB NOT NULL,          -- template data
    status TEXT NOT NULL,               -- pending, processing, completed, failed
    priority INTEGER NOT NULL,          -- 1-10 (1 = highest)
    retry_count INTEGER DEFAULT 0,      -- current retry attempt
    max_retries INTEGER DEFAULT 5,      -- max retry attempts
    scheduled_for TIMESTAMPTZ,          -- optional: schedule for later
    last_error TEXT,                    -- error message if failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

---

## 🎉 You're Done!

Your email system is now:
- ✅ **Configured** and ready
- ✅ **Processing** emails automatically
- ✅ **Monitored** via Supabase
- ✅ **Reliable** with retry logic
- ✅ **Scalable** with queue system

Need help? Check the full docs or contact hello@drawtopia.ai

---

**Happy Emailing! 📧**

