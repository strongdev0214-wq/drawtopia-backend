# 📧 Email System Testing Guide - Frontend Testing

## Overview

This guide shows you which emails can be tested through the frontend and which ones require backend/manual testing.

---

## ✅ **TESTABLE via Frontend** (6 Email Types)

These emails can be triggered by normal user actions on the frontend:

### 1. ✅ Welcome Email
**Can Test**: YES  
**How to Test**:
1. Go to `/signup` page
2. Create a new account (email or phone + Google OAuth)
3. Verify OTP code on `/otp-email` or `/otp-phone`
4. **Email triggers automatically** after first successful login

**Test Email**: Your registration email  
**Expected**: Welcome email within 10 seconds

```bash
# Frontend Flow:
/signup → /otp-email → (verify) → Welcome Email Queued
```

---

### 2. ✅ Book Completion Email (Interactive Search)
**Can Test**: YES  
**How to Test**:
1. Login to your account
2. Go to `/create-character/1` (start Interactive Search flow)
3. Complete all character creation steps
4. Wait for book generation to complete (~2-10 minutes)
5. **Email triggers automatically** when status = "completed"

**Test Email**: Your account email  
**Expected**: Book completion email with download link

```bash
# Frontend Flow:
/create-character/1 → Upload Photo → Select Options → Generate
→ Wait for completion → Book Completion Email Queued
```

---

### 3. ✅ Book Completion Email (Story Adventure)
**Can Test**: YES  
**How to Test**:
1. Login to your account
2. Go to `/adventure-story` (start Story Adventure flow)
3. Complete all character creation steps
4. Wait for book generation to complete (~2-10 minutes)
5. **Email triggers automatically** when status = "completed"

**Test Email**: Your account email  
**Expected**: Book completion email with story details

```bash
# Frontend Flow:
/adventure-story → Upload Photo → Select Options → Generate
→ Wait for completion → Book Completion Email Queued
```

---

### 4. ✅ Payment Success Email + Receipt
**Can Test**: YES (with test Stripe account)  
**How to Test**:
1. Login to your account
2. Go to `/pricing` page
3. Click "Subscribe" on Monthly or Yearly plan
4. Complete Stripe checkout (use test card: `4242 4242 4242 4242`)
5. Redirect to `/subscription/success`
6. **Email triggers automatically** via Stripe webhook

**Test Email**: Your account email  
**Expected**: 
- Payment success confirmation
- Receipt email (separate)

```bash
# Frontend Flow:
/pricing → Select Plan → Stripe Checkout → Success
→ Payment Success Email + Receipt Queued
```

**Stripe Test Cards**:
```
Success: 4242 4242 4242 4242
Decline: 4000 0000 0000 0002
Insufficient Funds: 4000 0000 0000 9995
```

---

### 5. ✅ Payment Failed Email
**Can Test**: YES (with test Stripe card)  
**How to Test**:
1. Login to your account
2. Go to `/pricing` page
3. Click "Subscribe" on any plan
4. Use a **declining test card**: `4000 0000 0000 0002`
5. **Email triggers automatically** via Stripe webhook

**Test Email**: Your account email  
**Expected**: Payment failed email with retry link

```bash
# Frontend Flow:
/pricing → Select Plan → Stripe Checkout (use declining card)
→ Payment Failed Email Queued
```

---

### 6. ✅ Subscription Cancelled Email
**Can Test**: YES (after subscribing)  
**How to Test**:
1. First, subscribe to a plan (see #4 above)
2. Go to `/account` page
3. Click "Manage Subscription" button
4. Cancel subscription in Stripe portal
5. **Email triggers automatically** via Stripe webhook

**Test Email**: Your account email  
**Expected**: Subscription cancellation confirmation

```bash
# Frontend Flow:
/account → Manage Subscription → Stripe Portal → Cancel
→ Subscription Cancelled Email Queued
```

---

## ⏳ **NOT TESTABLE via Frontend** (5 Email Types)

These require additional implementation or backend/manual testing:

### 7. ⏳ Parental Consent Verification Email
**Can Test**: NOT YET  
**Why**: Child profile creation doesn't trigger consent email yet  
**Status**: Template ready, trigger needs to be added

**To Implement**:
```python
# Add to child profile creation endpoint
if user_role == "parent" and creating_child_profile:
    await queue_parental_consent_email(
        supabase=supabase,
        to_email=parent_email,
        parent_name=parent_name,
        child_name=child_name,
        consent_link=f"{FRONTEND_URL}/consent/verify?token={token}"
    )
```

**Manual Test** (Python):
```python
from email_queue import queue_parental_consent_email
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

await queue_parental_consent_email(
    supabase=supabase,
    to_email="parent@example.com",
    parent_name="John Doe",
    child_name="Emma",
    consent_link="https://yourapp.com/consent/verify?token=abc123"
)
```

---

### 8. ⏳ Subscription Renewal Reminder
**Can Test**: NOT YET  
**Why**: Requires cron job to run 7 days before renewal  
**Status**: Template ready, cron job needs setup

**To Implement**:
```python
# Add cron job (runs daily)
import asyncio
from datetime import datetime, timedelta
from email_queue import EmailQueueManager

async def daily_subscription_reminder_job():
    """Run daily to check for subscriptions renewing in 7 days"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    queue_manager = EmailQueueManager(supabase)
    
    # Get subscriptions renewing in 7 days
    renewal_date = (datetime.now() + timedelta(days=7)).date()
    
    subscriptions = supabase.table("subscriptions") \
        .select("*, users(email, first_name)") \
        .eq("status", "active") \
        .execute()
    
    for sub in subscriptions.data:
        # Check if renewal date matches
        # Queue renewal reminder email
        pass
```

**Manual Test** (Python):
```python
from email_queue import EmailQueueManager
from datetime import datetime, timedelta

queue_manager = EmailQueueManager(supabase)

await queue_manager.queue_email(
    email_type="subscription_renewal_reminder",
    to_email="user@example.com",
    email_data={
        "customer_name": "John Doe",
        "plan_type": "Monthly Subscription",
        "renewal_amount": 9.99,
        "renewal_date": datetime.now() + timedelta(days=7),
        "manage_link": "https://yourapp.com/account",
        "cancel_link": "https://billing.stripe.com/cancel/xxx"
    },
    priority=2
)
```

---

### 9. ⏳ Gift Notification Email
**Can Test**: PARTIALLY  
**Why**: Gift flow exists but email trigger not connected  
**Status**: Template ready, needs trigger in gift creation

**Frontend Pages Exist**:
- `/gift/1` - Start gift
- `/gift/recipient/gift1` - Enter recipient
- `/gift/review` - Review gift
- `/gift/purchase` - Purchase gift

**To Implement**:
```python
# Add to gift order creation endpoint
# POST /api/gifts/orders
async def create_gift_order(...):
    # ... create gift order ...
    
    # Queue gift notification
    await queue_gift_notification_email(
        supabase=supabase,
        to_email=recipient_email,
        recipient_name=recipient_name,
        giver_name=user_name,
        occasion=occasion,
        gift_message=message,
        scheduled_for=scheduled_delivery_date  # if scheduled
    )
```

**Manual Test** (Python):
```python
from email_queue import queue_gift_notification_email

await queue_gift_notification_email(
    supabase=supabase,
    to_email="recipient@example.com",
    recipient_name="Sarah",
    giver_name="Grandma",
    occasion="Birthday",
    gift_message="Happy Birthday sweetie!",
    delivery_method="immediate_email"
)
```

---

### 10. ⏳ Gift Delivery Email
**Can Test**: NOT YET  
**Why**: Requires gift order linking to book generation  
**Status**: Template ready, needs book-gift association

**To Implement**:
```python
# In batch_processor.py, check if book is a gift
async def _queue_book_completion_email(self, job_id, job, job_data):
    # ... existing code ...
    
    # Check if this is a gift order
    gift_result = supabase.table("gift_orders") \
        .select("*") \
        .eq("book_id", book_id) \
        .execute()
    
    if gift_result.data:
        # Queue gift delivery email instead
        await queue_gift_delivery_email(...)
    else:
        # Queue regular book completion email
        await queue_book_completion_email(...)
```

**Manual Test** (Python):
```python
from email_queue import queue_gift_delivery_email

await queue_gift_delivery_email(
    supabase=supabase,
    to_email="recipient@example.com",
    recipient_name="Sarah",
    giver_name="Grandma",
    character_name="Luna",
    character_type="cat",
    book_title="Luna's Birthday Adventure",
    special_ability="flying",
    gift_message="Happy Birthday!",
    story_link="https://yourapp.com/gift/unwrap/xyz",
    download_link="https://yourapp.com/api/books/123/download",
    book_format="story_adventure"
)
```

---

### 11. ⏳ Receipt Email
**Can Test**: YES (same as Payment Success)  
**Why**: Already implemented with payment success  
**Status**: ✅ Working

**Note**: Receipt email is automatically queued alongside payment success email.

---

## 🧪 **Testing Checklist**

### Before Testing
- [ ] Gmail SMTP configured in `.env`
- [ ] Backend running (`python -m uvicorn main:app --reload`)
- [ ] Email background worker started (check logs)
- [ ] Database migration run (`email_queue` table exists)
- [ ] Frontend running (`npm run dev`)

### Test Each Email Type

| # | Email Type | Can Test? | Method | Status |
|---|-----------|-----------|--------|--------|
| 1 | Welcome Email | ✅ YES | Register new account | Ready |
| 2 | Book Completion (Interactive) | ✅ YES | Create Interactive Search book | Ready |
| 3 | Book Completion (Story) | ✅ YES | Create Story Adventure book | Ready |
| 4 | Payment Success + Receipt | ✅ YES | Subscribe with test card | Ready |
| 5 | Payment Failed | ✅ YES | Use declining test card | Ready |
| 6 | Subscription Cancelled | ✅ YES | Cancel via Stripe portal | Ready |
| 7 | Parental Consent | ⏳ NO | Manual Python test | Need trigger |
| 8 | Subscription Renewal | ⏳ NO | Manual Python test | Need cron |
| 9 | Gift Notification | ⏳ PARTIAL | Manual Python test | Need trigger |
| 10 | Gift Delivery | ⏳ NO | Manual Python test | Need trigger |

---

## 📊 **Monitor Testing**

### Check Email Queue

**Supabase Dashboard**:
1. Go to Table Editor → `email_queue`
2. Filter: `status = 'pending'` (waiting to send)
3. Filter: `status = 'completed'` (successfully sent)
4. Filter: `status = 'failed'` (failed to send)

**Check Last Error**:
```sql
SELECT * FROM email_queue 
WHERE status = 'failed' 
ORDER BY created_at DESC 
LIMIT 10;
```

### Check Backend Logs

Look for these messages:
```
✅ Payment success email queued for user@example.com
✅ Successfully sent welcome email to user@example.com
✅ Book completion email queued for user@example.com (Job 123)
❌ Failed to queue email: Invalid email address
```

---

## 🐛 **Troubleshooting Tests**

### Email Not Received

1. **Check Queue Status**:
   ```sql
   SELECT * FROM email_queue 
   WHERE to_email = 'your@email.com' 
   ORDER BY created_at DESC;
   ```

2. **Check Last Error**:
   - If `status = 'failed'`, check `last_error` column
   - If `status = 'pending'`, wait 10 seconds for processing

3. **Check Backend Logs**:
   ```
   ✅ Email background worker started
   📬 Processing X pending emails
   ```

4. **Check Spam Folder**: Gmail might flag test emails as spam

### Payment Test Not Working

1. **Use Stripe Test Mode**: Ensure you're using test API keys
2. **Test Cards**: Use `4242 4242 4242 4242` for success
3. **Webhook**: Ensure Stripe webhook is configured
4. **Logs**: Check backend logs for webhook events

### Book Completion Email Not Sent

1. **Check Book Status**:
   ```sql
   SELECT id, title, status FROM stories 
   ORDER BY created_at DESC LIMIT 10;
   ```

2. **Ensure Status is "completed"**: Email only sends on completion
3. **Check Job Queue**: Verify book generation job completed
4. **Wait Time**: Book generation takes 2-10 minutes

---

## 🎯 **Quick Test Scenarios**

### Scenario 1: Test All Working Emails (30 minutes)

```bash
# 1. Welcome Email (2 min)
- Register new account
- Verify OTP
- Check email

# 2. Book Completion (10 min)
- Create Interactive Search book
- Wait for completion
- Check email

# 3. Payment Success (5 min)
- Go to /pricing
- Subscribe with 4242...
- Check for 2 emails (success + receipt)

# 4. Payment Failed (2 min)
- Go to /pricing
- Subscribe with 4000 0000 0000 0002
- Check email

# 5. Subscription Cancelled (5 min)
- Cancel via Stripe portal
- Check email
```

### Scenario 2: Manual Python Tests (10 minutes)

```python
# Test remaining emails via Python
import asyncio
from email_queue import EmailQueueManager
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
queue_manager = EmailQueueManager(supabase)

# Test Parental Consent
await queue_manager.queue_email(
    email_type="parental_consent",
    to_email="test@example.com",
    email_data={...}
)

# Test Gift Notification
await queue_manager.queue_email(
    email_type="gift_notification",
    to_email="test@example.com",
    email_data={...}
)

# Check results
await queue_manager.process_email_queue()
```

---

## 📝 **Summary**

### ✅ Ready to Test Now (6 types):
1. Welcome Email
2. Book Completion (Interactive Search)
3. Book Completion (Story Adventure)
4. Payment Success
5. Payment Failed
6. Subscription Cancelled

### ⏳ Need Additional Setup (4 types):
7. Parental Consent (needs trigger)
8. Subscription Renewal Reminder (needs cron)
9. Gift Notification (needs trigger)
10. Gift Delivery (needs trigger)

### 🔥 Recommendation:

**Start with these 6 testable emails** to verify the system works, then add triggers for the remaining 4 emails as you develop those features.

---

## 🚀 **Next Steps**

1. **Test the 6 working emails** using frontend
2. **Verify emails arrive** in your inbox
3. **Check Supabase queue** for status
4. **Add remaining triggers** as needed
5. **Set up cron jobs** for scheduled emails

Need help? Check logs and email queue table! 📧

