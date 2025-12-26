# 📧 Email System Testing Guide - UPDATED

## 🎉 All Emails Now Testable!

After the latest updates, **ALL 11 email types** can now be tested either through the frontend or via manual methods.

---

## ✅ **TESTABLE via Frontend** (All 10 Types!)

### **Already Working** (6 emails)

| # | Email Type | Frontend Flow | Status |
|---|-----------|---------------|---------|
| 1 | Welcome Email | `/signup` → Register → Verify | ✅ Working |
| 2 | Book Completion (Interactive) | `/create-character/1` → Generate | ✅ Working |
| 3 | Book Completion (Story) | `/adventure-story` → Generate | ✅ Working |
| 4 | Payment Success + Receipt | `/pricing` → Subscribe (test card) | ✅ Working |
| 5 | Payment Failed | `/pricing` → Subscribe (declining card) | ✅ Working |
| 6 | Subscription Cancelled | `/account` → Manage → Cancel | ✅ Working |

### **NEW - Now Testable!** (4 emails)

| # | Email Type | How to Test | Status |
|---|-----------|-------------|---------|
| 7 | **Parental Consent** | Create child profile → Email sent | 🆕 **READY** |
| 8 | **Gift Notification** | Use frontend API call | 🆕 **READY** |
| 9 | **Gift Delivery** | Complete gift book | 🆕 **READY** |
| 10 | **Subscription Renewal** | Run cron job manually | 🆕 **READY** |

---

## 🧪 **Testing Instructions for NEW Emails**

### Test 7: Parental Consent Email

**Method 1: Through Frontend (Automatic)**

1. Go to `/create-child-profile`
2. Create a new child profile
3. The system will automatically queue parental consent email
4. Check your email inbox

```svelte
<!-- In create-child-profile page -->
<!-- The email is automatically triggered when you call: -->
insertChildProfile(childProfile, true, parentEmail, parentName)
```

**Method 2: Via API Call**

```javascript
// From frontend console or your code:
const response = await fetch('http://localhost:8000/api/emails/queue-parental-consent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    parent_email: 'parent@example.com',
    parent_name: 'John Doe',
    child_name: 'Emma'
  })
});

console.log(await response.json());
```

**Expected Email**: "Verify your account on Drawtopia — Help Emma create magical stories"

---

### Test 8: Gift Notification Email

**Method: Via Frontend API Call**

```javascript
// Call from frontend (e.g., gift creation flow):
const response = await fetch('http://localhost:8000/api/emails/queue-gift-notification', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    recipient_email: 'recipient@example.com',
    recipient_name: 'Sarah',
    giver_name: 'Grandma',
    occasion: 'Birthday',
    gift_message: 'Happy Birthday sweetie!',
    delivery_method: 'immediate_email'
  })
});

console.log(await response.json());
```

**OR use the helper function**:

```javascript
import { queueGiftNotificationEmail } from '$lib/emails';

const result = await queueGiftNotificationEmail(
  'recipient@example.com',  // recipient_email
  'Sarah',                   // recipient_name
  'Grandma',                // giver_name
  'Birthday',               // occasion
  'Happy Birthday!',        // gift_message
  'immediate_email'         // delivery_method
);

if (result.success) {
  console.log('Gift notification queued!', result.job_id);
}
```

**Where to add**: In your gift purchase flow (`/gift/purchase` page after payment)

**Expected Email**: "You've been sent a gift on Drawtopia! 🎁✨"

---

### Test 9: Gift Delivery Email

**Method 1: Automatic (when gift book completes)**

1. Create a book that's marked as a gift (set `is_gift: true` or `gift_order_id`)
2. Wait for book generation to complete
3. System automatically sends gift delivery email instead of regular completion email

**Method 2: Via API Call**

```javascript
const response = await fetch('http://localhost:8000/api/emails/queue-gift-delivery', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    recipient_email: 'recipient@example.com',
    recipient_name: 'Sarah',
    giver_name: 'Grandma',
    character_name: 'Luna',
    character_type: 'cat',
    book_title: "Luna's Birthday Adventure",
    special_ability: 'flying',
    gift_message: 'Happy Birthday sweetie!',
    story_link: 'https://yourapp.com/story/123',
    download_link: 'https://yourapp.com/api/books/123/download',
    book_format: 'story_adventure'
  })
});

console.log(await response.json());
```

**OR use the helper function**:

```javascript
import { queueGiftDeliveryEmail } from '$lib/emails';

const result = await queueGiftDeliveryEmail(
  'recipient@example.com',  // recipient_email
  'Sarah',                   // recipient_name
  'Grandma',                // giver_name
  'Luna',                    // character_name
  'cat',                     // character_type
  "Luna's Adventure",        // book_title
  'flying',                  // special_ability
  'Happy Birthday!',         // gift_message
  'https://app.com/story/1', // story_link
  'https://app.com/dl/1',    // download_link
  'story_adventure'          // book_format
);
```

**Expected Email**: "Your gift has arrived! Open 'Luna's Birthday Adventure' now 🎁📖"

---

### Test 10: Subscription Renewal Reminder

**Method 1: Manual Cron Job**

```bash
# Run the cron job manually
cd drawtopia-backend
python subscription_renewal_cron.py
```

**Method 2: Scheduled (Production)**

```bash
# Add to crontab to run daily at 9 AM
0 9 * * * cd /path/to/drawtopia-backend && python subscription_renewal_cron.py

# OR use a scheduler like APScheduler in your main app
```

**Method 3: Test with Modified Date**

```python
# Temporarily modify the cron job to check for subscriptions renewing tomorrow:
target_date = datetime.now() + timedelta(days=1)  # Instead of 7 days

# Then run:
python subscription_renewal_cron.py
```

**Expected Email**: "Your Drawtopia subscription renews on [date]"

---

## 🔧 **Setup Required**

### 1. Frontend Email Helper

Already created: `drawtopia-frontend/src/lib/emails.ts`

Functions available:
- `queueParentalConsentEmail()`
- `queueGiftNotificationEmail()`
- `queueGiftDeliveryEmail()`

### 2. Backend API Endpoints

Already added to `main.py`:
- `POST /api/emails/queue-parental-consent`
- `POST /api/emails/queue-gift-notification`
- `POST /api/emails/queue-gift-delivery`

### 3. Child Profile Integration

Already updated: `drawtopia-frontend/src/lib/database/childProfiles.ts`

The `insertChildProfile()` function now accepts:
```typescript
insertChildProfile(
  childProfile,
  sendConsentEmail: true,    // NEW parameter
  parentEmail: string,       // NEW parameter
  parentName: string         // NEW parameter
)
```

### 4. Gift Delivery Integration

Already updated: `drawtopia-backend/batch_processor.py`

Now checks if book is a gift and sends appropriate email.

### 5. Subscription Renewal Cron

New file: `drawtopia-backend/subscription_renewal_cron.py`

Run daily to send renewal reminders.

---

## 📊 **Complete Testing Checklist**

### Quick Test All Emails (45 minutes)

```bash
# 1. Welcome Email (2 min)
- Register new account → ✅ Email

# 2. Book Completion (10 min)
- Create book → Wait → ✅ Email

# 3. Payment Success (5 min)
- Subscribe → ✅ 2 Emails (success + receipt)

# 4. Payment Failed (2 min)
- Subscribe with declining card → ✅ Email

# 5. Subscription Cancelled (5 min)
- Cancel subscription → ✅ Email

# 6. Parental Consent (1 min)
- Create child profile → ✅ Email

# 7. Gift Notification (1 min)
- Call API → ✅ Email

# 8. Gift Delivery (1 min)
- Call API → ✅ Email

# 9. Subscription Renewal (1 min)
- Run cron job → ✅ Email

# Total: 9 different emails tested! ✅
```

---

## 💻 **Frontend Integration Examples**

### Example 1: Child Profile with Consent Email

```svelte
<script>
  import { insertChildProfile } from '$lib/database/childProfiles';
  import { user } from '$lib/stores/auth';
  
  async function saveChildProfile() {
    const childProfile = {
      first_name: childName,
      age_group: ageGroup,
      relationship: relationship,
      parent_id: $user.id,
      avatar_url: avatarUrl
    };
    
    // Send parental consent email automatically
    const result = await insertChildProfile(
      childProfile,
      true,                    // Send consent email
      $user.email,             // Parent email
      $user.first_name         // Parent name
    );
    
    if (result.success) {
      console.log('✅ Child profile created and consent email sent!');
    }
  }
</script>
```

### Example 2: Gift Purchase with Notifications

```svelte
<script>
  import { queueGiftNotificationEmail } from '$lib/emails';
  import { giftCreation } from '$lib/stores/giftCreation';
  
  async function completePurchase() {
    // ... handle payment ...
    
    // Send gift notification email
    const emailResult = await queueGiftNotificationEmail(
      $giftCreation.recipientEmail,
      $giftCreation.recipientName,
      $user.first_name,
      $giftCreation.occasion,
      $giftCreation.message,
      $giftCreation.deliveryMethod
    );
    
    if (emailResult.success) {
      console.log('✅ Gift notification queued!');
      // Proceed to success page
    }
  }
</script>
```

---

## 🎯 **All Email Types - Complete Overview**

| # | Email | Trigger | Method | Status |
|---|-------|---------|--------|---------|
| 1 | Welcome | User registers | Auto | ✅ |
| 2 | Book Complete (Interactive) | Book generation done | Auto | ✅ |
| 3 | Book Complete (Story) | Book generation done | Auto | ✅ |
| 4 | Payment Success | Stripe webhook | Auto | ✅ |
| 5 | Receipt | Stripe webhook | Auto | ✅ |
| 6 | Payment Failed | Stripe webhook | Auto | ✅ |
| 7 | Subscription Cancelled | Stripe webhook | Auto | ✅ |
| 8 | Parental Consent | Child profile created | API/Auto | ✅ |
| 9 | Gift Notification | Gift order created | API | ✅ |
| 10 | Gift Delivery | Gift book complete | Auto | ✅ |
| 11 | Subscription Renewal | Cron job (7 days before) | Cron | ✅ |

---

## 🚀 **Production Deployment**

### Cron Job Setup

**Option 1: System Crontab**
```bash
# Edit crontab
crontab -e

# Add line (runs daily at 9 AM):
0 9 * * * cd /path/to/drawtopia-backend && /path/to/python subscription_renewal_cron.py >> /var/log/drawtopia/renewal-cron.log 2>&1
```

**Option 2: APScheduler in main.py**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=9, minute=0)
async def renewal_reminder_job():
    from subscription_renewal_cron import send_renewal_reminders
    await send_renewal_reminders()

scheduler.start()
```

**Option 3: GitHub Actions (if using GitHub)**
```yaml
name: Subscription Renewal Reminder
on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC

jobs:
  run-cron:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run renewal reminder
        run: python drawtopia-backend/subscription_renewal_cron.py
```

---

## ✅ **Success!**

All 11 email types are now:
- ✅ **Implemented** with templates
- ✅ **Testable** via frontend or API
- ✅ **Documented** with examples
- ✅ **Production-ready** with proper error handling

**Next Steps**:
1. Test each email type using this guide
2. Customize templates as needed
3. Set up cron job for production
4. Monitor email queue in Supabase

Need help? Check `EMAIL_SYSTEM_SETUP.md` for troubleshooting! 📧

