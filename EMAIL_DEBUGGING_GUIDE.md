# Email System Debugging Guide

## Changes Made

### 1. Enhanced Logging for Payment Success Email
**Location:** `main.py` lines 3458-3480

Added detailed diagnostic logging:
- ✅ Logs customer email and service status before attempting send
- ✅ Logs success/failure with clear emoji indicators (✅/❌)
- ✅ Logs specific error messages if email fails
- ✅ Includes full stack trace on exceptions

### 2. Enhanced Logging for Payment Failed Email
**Location:** `main.py` lines 3535-3557

Same improvements as payment success email.

### 3. Added Email Service Status to Root Endpoint
**Location:** `main.py` lines 1141-1158

Now the root endpoint (`/`) shows:
```json
{
  "email_service": {
    "enabled": true/false,
    "provider": "Gmail SMTP"
  }
}
```

---

## How to Debug Email Issues

### Step 1: Check Email Service Status

Visit your API root endpoint:
```
https://drawtopia-backend.vercel.app/
```

Look for:
```json
"email_service": {
  "enabled": true,  // ← Must be true
  "provider": "Gmail SMTP"
}
```

If `enabled: false`, check your environment variables.

---

### Step 2: Check Environment Variables

In Vercel Dashboard → Settings → Environment Variables, verify:

```bash
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password  # No spaces!
FROM_EMAIL=your.email@gmail.com
FROM_NAME=Strong Dev
```

**Important:** After adding/updating env vars, you must **redeploy** the app!

---

### Step 3: Check Logs on Next Purchase

When a subscription is purchased, you should now see these logs:

```
✅ Successful Flow:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Received Stripe webhook: invoice.payment_succeeded
Payment succeeded for subscription: sub_xxxxx
Updated user xxx with active subscription on payment success
Attempting to send payment success email - Email: user@example.com, Service enabled: True
✅ Payment success email sent to user@example.com
```

```
❌ If Email Service Not Enabled:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Received Stripe webhook: invoice.payment_succeeded
Payment succeeded for subscription: sub_xxxxx
Attempting to send payment success email - Email: user@example.com, Service enabled: False
⚠️ Cannot send payment success email: email service not enabled
```

```
❌ If Customer Email Missing:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Received Stripe webhook: invoice.payment_succeeded
Payment succeeded for subscription: sub_xxxxx
Attempting to send payment success email - Email: None, Service enabled: True
⚠️ Cannot send payment success email: customer_email is missing
```

```
❌ If Gmail Authentication Fails:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Received Stripe webhook: invoice.payment_succeeded
Payment succeeded for subscription: sub_xxxxx
Attempting to send payment success email - Email: user@example.com, Service enabled: True
❌ Failed to send payment success email: Gmail authentication failed. Check your App Password.
```

---

### Step 4: Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `enabled: false` | Env vars not set | Add `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in Vercel |
| `customer_email is missing` | Stripe not sending email | Check Stripe customer has email set |
| `Gmail authentication failed` | Wrong App Password | Regenerate App Password in Google Account |
| `Service enabled: False` | Env vars not loaded | Redeploy after adding env vars |

---

## Testing the Email System

### Option 1: Test with Real Stripe Purchase
1. Make a test subscription purchase
2. Check Vercel logs for the diagnostic messages
3. Check customer's email inbox

### Option 2: Test Email Service Directly (Future)
You can add a test endpoint:

```python
@app.post("/api/test-email")
async def test_email(email: str):
    """Test email sending"""
    if not email_service.is_enabled():
        return {"error": "Email service not enabled"}
    
    result = await email_service.send_email(
        to_email=email,
        subject="Test Email",
        html_content="<h1>Test</h1><p>This is a test email.</p>",
        text_content="Test - This is a test email."
    )
    return result
```

---

## Current Status

### ✅ Working
- Subscription cancellation emails
- Email service infrastructure
- Gmail SMTP integration

### ⚠️ Needs Verification
- Payment success emails (check logs on next purchase)
- Payment failed emails (check logs on failed payment)

### 📋 Next Steps
1. Deploy the updated code to Vercel
2. Verify environment variables are set
3. Make a test purchase
4. Check Vercel logs for new diagnostic messages
5. Verify email arrives in inbox

---

## Quick Checklist

Before testing:
- [ ] Environment variables set in Vercel
- [ ] App redeployed after env var changes
- [ ] Gmail App Password is correct (16 chars, no spaces)
- [ ] Root endpoint shows `"enabled": true`

During testing:
- [ ] Webhook received: `invoice.payment_succeeded`
- [ ] Log shows: `Attempting to send payment success email`
- [ ] Log shows: `✅ Payment success email sent to...`
- [ ] Email arrives in customer's inbox

---

## Support

If emails still don't work after following this guide:
1. Check Vercel logs for the new diagnostic messages
2. Verify Gmail App Password is valid
3. Test sending email from a simple Python script with same credentials
4. Check Gmail account for "Suspicious activity" alerts

