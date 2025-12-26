# 🎉 Complete Email System - Testing Guide

## ✅ **ALL 11 EMAIL TYPES NOW TESTABLE!**

---

## 🚀 **Quick Test Guide** (30 Minutes)

### Prerequisites
```bash
✅ Backend running: python -m uvicorn main:app --reload
✅ Frontend running: npm run dev
✅ Gmail SMTP configured in .env
✅ Database migration run (email_queue table exists)
```

---

## 📧 **Test Each Email Type**

### 1. ✅ Welcome Email (2 min)
**Test**: Register new account
```bash
1. Go to http://localhost:5173/signup
2. Enter email + verify OTP
3. Check your email inbox
✅ Expect: "Welcome to Drawtopia" email
```

---

### 2. ✅ Book Completion - Interactive Search (10 min)
**Test**: Create Interactive Search book
```bash
1. Login → /create-character/1
2. Upload photo → Complete steps
3. Wait for generation (2-10 min)
✅ Expect: "Your book is ready!" email
```

---

### 3. ✅ Book Completion - Story Adventure (10 min)
**Test**: Create Story Adventure book
```bash
1. Login → /adventure-story
2. Upload photo → Complete steps
3. Wait for generation (2-10 min)
✅ Expect: "Your story is ready!" email
```

---

### 4. ✅ Payment Success + Receipt (5 min)
**Test**: Subscribe with test card
```bash
1. Go to /pricing
2. Click "Subscribe"
3. Use card: 4242 4242 4242 4242
4. Complete checkout
✅ Expect: 2 emails (success + receipt)
```

---

### 5. ✅ Payment Failed (2 min)
**Test**: Use declining card
```bash
1. Go to /pricing
2. Click "Subscribe"
3. Use card: 4000 0000 0000 0002
4. Try checkout
✅ Expect: "Payment failed" email
```

---

### 6. ✅ Subscription Cancelled (5 min)
**Test**: Cancel via Stripe portal
```bash
1. Subscribe first (Test 4)
2. Go to /account
3. Click "Manage Subscription"
4. Cancel in Stripe portal
✅ Expect: "Subscription cancelled" email
```

---

### 7. ✅ **Parental Consent** (2 min) **[NEW!]**
**Test**: Create child profile
```bash
1. Login to your account
2. Go to /create-child-profile
3. Add child profile
4. Check "Send consent email"
5. Enter parent email
✅ Expect: "Verify your account" email to parent
```

**Manual Test**:
```bash
curl -X POST http://localhost:8000/api/emails/parental-consent \
  -H "Content-Type: application/json" \
  -d '{
    "parent_email": "parent@example.com",
    "parent_name": "John Doe",
    "child_name": "Emma"
  }'
```

---

### 8. ✅ **Subscription Renewal Reminder** (Automatic) **[NEW!]**
**Test**: Cron runs daily
```bash
# Automatic - runs every 24 hours
# Checks for subscriptions renewing in 7 days

# Check logs for:
✅ Subscription renewal reminder worker started
📬 Checking for subscriptions renewing in 7 days...
✅ Sent X subscription renewal reminders
```

**Manual Test** (Force check):
```sql
-- In Supabase: Set renewal to 7 days from now
UPDATE subscriptions 
SET current_period_end = (NOW() + INTERVAL '7 days')::timestamp
WHERE id = 'your_subscription_id';

-- Restart backend to trigger immediate check
```

---

### 9. ✅ **Gift Notification** (5 min) **[NEW!]**
**Test**: Create gift through frontend
```bash
1. Login to your account
2. Go to /gift/1
3. Fill in recipient details:
   - Name: "Sarah"
   - Email: "recipient@example.com"
   - Occasion: "Birthday"
   - Message: "Happy Birthday!"
4. Complete all gift steps
5. Click "Finish" on /gift/purchase
✅ Expect: "You've been sent a gift!" email to recipient
```

**Manual Test**:
```bash
curl -X POST http://localhost:8000/api/emails/gift-notification \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "recipient@example.com",
    "recipient_name": "Sarah",
    "giver_name": "Grandma",
    "occasion": "Birthday",
    "gift_message": "Happy Birthday sweetie!",
    "delivery_method": "immediate_email"
  }'
```

---

### 10. ✅ **Gift Delivery** (15 min) **[NEW!]**
**Test**: Gift story completes
```bash
1. Create gift (Test 9 above)
2. Gift story generates automatically
3. Wait 2-10 minutes for generation
4. When complete:
✅ Expect: "Your gift has arrived!" email to recipient
✅ Gift status → "completed" in database
```

**How It Works**:
```
Gift Created → Story Generates → Book Complete
                                      ↓
                              Check if Gift?
                                 ↙          ↘
                           YES                NO
                            ↓                  ↓
                    Gift Delivery Email    Book Completion Email
                    (to recipient)         (to parent)
```

---

## 📊 **Monitor All Tests**

### Supabase Dashboard
```bash
1. Go to Table Editor → email_queue
2. Watch emails flow through:
   pending → processing → completed
3. Check failed emails in last_error column
```

### Backend Logs
```bash
# Watch for these messages:
✅ Parental consent email queued for parent@example.com
✅ Gift notification email queued for recipient@example.com  
✅ Gift delivery email queued for recipient@example.com (Job 123)
✅ Book completion email queued for user@example.com (Job 456)
📬 Processing 5 pending emails
✅ Successfully sent welcome email to user@example.com
```

---

## 🎯 **Complete Test Checklist**

### Ready to Test (11 Total):

- [ ] 1. Welcome Email (Register)
- [ ] 2. Book Completion - Interactive (Create book)
- [ ] 3. Book Completion - Story (Create book)
- [ ] 4. Payment Success (Subscribe)
- [ ] 5. Payment Receipt (Subscribe)
- [ ] 6. Payment Failed (Declining card)
- [ ] 7. Subscription Cancelled (Cancel)
- [ ] 8. **Parental Consent (Create child profile)** ⭐ NEW!
- [ ] 9. **Gift Notification (Create gift)** ⭐ NEW!
- [ ] 10. **Gift Delivery (Gift completes)** ⭐ NEW!
- [ ] 11. **Subscription Renewal (Automatic cron)** ⭐ NEW!

---

## 🐛 **Quick Troubleshooting**

### Email Not Received?

**1. Check Queue Status**:
```sql
SELECT id, email_type, to_email, status, last_error, created_at
FROM email_queue 
WHERE to_email = 'your@email.com'
ORDER BY created_at DESC 
LIMIT 10;
```

**2. Check Status**:
- `pending`: Wait 10 seconds
- `processing`: Wait 30 seconds
- `failed`: Check `last_error`
- `completed`: Check spam folder

**3. Check Backend Logs**:
```bash
# Should see:
✅ Email service (Gmail SMTP) initialized successfully
✅ Email background worker started
```

---

### Gift Email Not Working?

**1. Check Gift Created**:
```sql
SELECT * FROM gifts 
WHERE delivery_email = 'recipient@example.com'
ORDER BY created_at DESC;
```

**2. Check Child Profile ID**:
```sql
-- Gift must have child_profile_id
SELECT id, child_profile_id, delivery_email, status 
FROM gifts 
WHERE id = 'your_gift_id';
```

**3. Check Story Generation**:
```sql
-- Story must use same child_profile_id
SELECT id, title, status, child_profile_id, job_id
FROM stories 
WHERE child_profile_id = 'gift_child_profile_id';
```

---

### Workers Not Running?

**Check Logs**:
```bash
# Should see on startup:
✅ Queue manager and batch processor initialized
✅ Background worker started
✅ Email background worker started
✅ Subscription renewal reminder worker started
```

**If Missing**:
```bash
# Restart backend
python -m uvicorn main:app --reload

# Watch for initialization messages
```

---

## 📈 **Expected Results**

### Successful Test Run:

```bash
# Email Queue (Supabase):
pending: 0
processing: 0  
completed: 11 ✅
failed: 0

# Email Inboxes:
✅ Welcome email received
✅ 2 book completion emails received
✅ Payment success + receipt received
✅ Payment failed email received
✅ Subscription cancelled received
✅ Parental consent received
✅ Gift notification received
✅ Gift delivery received
✅ (Renewal reminder: check in 24 hours)

# Backend Logs:
✅ All workers running
✅ All emails queued successfully
✅ No errors in processing
```

---

## 🎉 **Success!**

If you can see:
- ✅ Emails arriving in inboxes
- ✅ Queue processing smoothly
- ✅ No errors in logs
- ✅ All workers running

**Your email system is working perfectly!** 🚀

---

## 📞 **Need Help?**

Check these files:
- `EMAIL_SYSTEM_SETUP.md` - Full setup guide
- `EMAIL_TESTING_GUIDE.md` - Detailed testing
- `EMAIL_TRIGGERS_ADDED.md` - What was added
- `EMAIL_QUICK_START.md` - 5-minute setup

Or check:
- Backend logs for errors
- Supabase `email_queue` table
- Gmail SMTP credentials in `.env`

---

**Last Updated**: December 26, 2024  
**Status**: ✅ **ALL 11 EMAIL TYPES FULLY IMPLEMENTED AND TESTABLE!**

