# Quick Email Testing Guide

## 🚀 Quick Start (5 Minutes)

### **Step 1: Configure Gmail (2 minutes)**
```bash
# Edit .env file
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # 16 characters from Google
FRONTEND_URL=http://localhost:5173
```

### **Step 2: Restart Backend (30 seconds)**
```bash
# Stop backend (Ctrl+C)
# Start backend
python main.py
```

### **Step 3: Test Welcome Email (2 minutes)**
```bash
# Option A: Via curl
curl -X POST http://localhost:8000/api/auth/sync \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-'$(date +%s)'",
    "email": "YOUR-EMAIL@example.com",
    "name": "Test User"
  }'

# Option B: Via Python
python -c "
import requests
import time
response = requests.post('http://localhost:8000/api/auth/sync', json={
    'user_id': f'test-{int(time.time())}',
    'email': 'YOUR-EMAIL@example.com',
    'name': 'Test User'
})
print(response.json())
"
```

### **Step 4: Check Results**
✅ **Backend logs should show:**
```
New user detected: test-xxx, sending welcome email
✅ Welcome email sent to YOUR-EMAIL@example.com
```

✅ **API response should show:**
```json
{
  "success": true,
  "is_new_user": true,
  "welcome_email_sent": true,
  "message": "User synced successfully"
}
```

✅ **Check your email inbox** (and spam folder!)

---

## 🧪 Test All Email Types

### **1. Welcome Email** ✅
```bash
curl -X POST http://localhost:8000/api/auth/sync \
  -H "Content-Type: application/json" \
  -d '{"user_id": "new-user-'$(date +%s)'", "email": "test@example.com", "name": "Test"}'
```

### **2. Parental Consent Email** ✅
```bash
curl -X POST http://localhost:8000/api/emails/parental-consent \
  -H "Content-Type: application/json" \
  -d '{
    "parent_email": "parent@example.com",
    "parent_name": "Parent Name",
    "child_name": "Child Name"
  }'
```

### **3. Gift Notification Email** ✅
```bash
curl -X POST http://localhost:8000/api/emails/gift-notification \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "recipient@example.com",
    "recipient_name": "Recipient",
    "giver_name": "Giver",
    "occasion": "Birthday",
    "gift_message": "Happy Birthday!"
  }'
```

### **4. Payment Emails** ✅
**Requires Stripe webhook** - Test via Stripe Dashboard → Webhooks → Send test webhook

### **5. Book Completion Email** ✅
**Automatic** - Generated when book creation completes

---

## ⚡ Quick Troubleshooting

### **Problem: "Email service not enabled"**
```bash
# Check .env file has:
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Restart backend after adding
```

### **Problem: "Exception sending email"**
```bash
# Check Gmail App Password:
# 1. Must be 16 characters
# 2. No spaces
# 3. 2FA must be enabled on Gmail
# 4. Generate new one at: https://myaccount.google.com/apppasswords
```

### **Problem: "User already exists"**
```bash
# Welcome email only sent for NEW users
# Use different user_id or delete from database:
# DELETE FROM users WHERE id = 'test-user-id';
```

### **Problem: Email goes to spam**
```bash
# 1. Add sender email to contacts
# 2. Mark as "Not Spam"
# 3. Check email content for spam triggers
```

---

## 📊 Expected Response Times

| Email Type | Expected Time | Status |
|------------|---------------|--------|
| Welcome | 1-3 seconds | ✅ Immediate |
| Payment | 1-3 seconds | ✅ Immediate |
| Parental Consent | 1-3 seconds | ✅ Immediate |
| Gift Notification | 1-3 seconds | ✅ Immediate |
| Book Completion | 1-3 seconds after job completes | ✅ Immediate |

---

## 🔍 Check Email Service Status

### **Method 1: Python Console**
```python
from email_service import email_service
print(f"Enabled: {email_service.is_enabled()}")
print(f"Gmail: {email_service.gmail_address}")
```

### **Method 2: Backend Logs**
```bash
# Look for on startup:
✅ Email service initialized successfully
# Or:
⚠️ Email service not configured (missing credentials)
```

### **Method 3: Test Endpoint**
```bash
# Check health endpoint
curl http://localhost:8000/health
```

---

## 📝 Quick Checklist

- [ ] `.env` file has `GMAIL_ADDRESS`
- [ ] `.env` file has `GMAIL_APP_PASSWORD` (16 chars)
- [ ] `.env` file has `FRONTEND_URL`
- [ ] Backend restarted after `.env` changes
- [ ] Backend logs show "Email service initialized"
- [ ] Test email sent successfully
- [ ] Email received (check spam folder)
- [ ] Email content looks correct
- [ ] Links in email work

---

## 🎯 Success Indicators

### **Backend Logs**
```
✅ Email service initialized successfully
✅ New user detected: xxx, sending welcome email
✅ Welcome email sent to test@example.com
```

### **API Response**
```json
{
  "success": true,
  "welcome_email_sent": true
}
```

### **Email Received**
- Subject: "🎉 Welcome to Drawtopia - Let's Create Something Amazing!"
- From: Your configured Gmail address
- Content: Personalized with user's name
- Links: Working and pointing to correct URLs

---

## 🆘 Still Not Working?

1. **Check Gmail Settings:**
   - 2FA enabled? → https://myaccount.google.com/security
   - App password generated? → https://myaccount.google.com/apppasswords
   - Less secure apps OFF (use app password instead)

2. **Check Backend:**
   - Server running?
   - No errors in logs?
   - `.env` file in correct location?

3. **Check Network:**
   - Can reach smtp.gmail.com:465?
   - Firewall blocking SMTP?
   - VPN interfering?

4. **Test SMTP Directly:**
```python
import smtplib, ssl
context = ssl.create_default_context()
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login("your-email@gmail.com", "your-app-password")
    print("✅ SMTP works!")
```

---

**Need Help?** Check the detailed review in `WELCOME_EMAIL_REVIEW.md`

**Last Updated:** December 26, 2025

