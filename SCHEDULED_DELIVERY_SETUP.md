# Scheduled Gift Delivery System Setup Guide

This guide explains how to set up and deploy the scheduled gift delivery system with web push notifications.

## Overview

The system consists of three main components:

1. **Edge Function (Cron Job)**: `check-scheduled-gifts` - Runs every minute to check for gifts ready to be delivered
2. **Backend API**: `/api/gift/deliver` - Handles gift delivery and triggers web push notifications
3. **Frontend Service Worker**: Receives and displays push notifications to users

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Cron Job (Every Minute)                                      │
│     check-scheduled-gifts Edge Function                          │
│     - Queries gifts table for delivery_time within 2 mins        │
│     - notification_sent = FALSE                                  │
│     - status = 'completed'                                       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Backend API Call                                             │
│     POST /api/gift/deliver                                       │
│     - Validates gift                                             │
│     - Calls send-gift-notification edge function                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Web Push Notification                                        │
│     send-gift-notification Edge Function                         │
│     - Gets user's push subscriptions                             │
│     - Sends web push to all devices                              │
│     - Marks notification_sent = TRUE                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. User Device                                                  │
│     Service Worker (sw.js)                                       │
│     - Receives push notification                                 │
│     - Displays notification to user                              │
│     - User clicks → Opens gift page                              │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. VAPID Keys for Web Push

Generate VAPID keys for web push notifications:

```bash
npx web-push generate-vapid-keys
```

This will output:
```
Public Key: BNxxx...
Private Key: xxx...
```

### 2. Environment Variables

#### Backend (.env)
```env
# Existing variables...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
BACKEND_URL=https://your-backend.com
FRONTEND_URL=https://your-frontend.com
```

#### Frontend (.env)
```env
VITE_VAPID_PUBLIC_KEY=BNxxx... (from step 1)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

#### Supabase Edge Function Secrets
Set these in your Supabase dashboard (Settings > Edge Functions > Secrets):

```bash
# Via Supabase CLI:
supabase secrets set VAPID_PUBLIC_KEY=BNxxx...
supabase secrets set VAPID_PRIVATE_KEY=xxx...
supabase secrets set VAPID_SUBJECT=mailto:support@drawtopia.com
supabase secrets set BACKEND_URL=https://your-backend.com
```

## Database Schema

Ensure your `gifts` table has these fields:

```sql
CREATE TABLE IF NOT EXISTS gifts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  user_id UUID REFERENCES auth.users(id),
  from_user_id UUID REFERENCES auth.users(id),
  to_user_id UUID REFERENCES auth.users(id),
  status TEXT NOT NULL,
  occasion TEXT,
  relationship TEXT,
  delivery_time TIMESTAMP WITH TIME ZONE,
  delivery_email TEXT,
  child_name TEXT,
  age_group TEXT,
  child_profile_id UUID,
  special_msg TEXT,
  checked BOOLEAN DEFAULT FALSE,
  notification_sent BOOLEAN DEFAULT FALSE,
  notification_sent_at TIMESTAMP WITH TIME ZONE
);

-- Index for scheduled delivery queries (important for performance)
CREATE INDEX idx_gifts_scheduled_delivery 
ON gifts(delivery_time, notification_sent, status) 
WHERE notification_sent = FALSE AND status = 'completed';
```

Ensure `push_subscriptions` table exists:

```sql
CREATE TABLE IF NOT EXISTS push_subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  endpoint TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, endpoint)
);

-- Index for faster lookups
CREATE INDEX idx_push_subscriptions_user_id ON push_subscriptions(user_id);
```

## Deployment Steps

### 1. Deploy Edge Functions

#### Option A: Using Supabase CLI

```bash
# Login to Supabase
supabase login

# Link to your project
supabase link --project-ref your-project-ref

# Deploy both edge functions
supabase functions deploy check-scheduled-gifts
supabase functions deploy send-gift-notification
```

#### Option B: Using Supabase Dashboard

1. Go to Edge Functions in Supabase Dashboard
2. Create new function `check-scheduled-gifts`
3. Copy content from `supabase/functions/check-scheduled-gifts/index.ts`
4. Deploy
5. Repeat for ` send-gift-notification` if not already deployed

### 2. Enable Cron Schedule

The cron schedule is configured in `supabase/config.toml`:

```toml
[[edge_runtime.functions]]
name = "check-scheduled-gifts"
verify_jwt = false
cron = "*/1 * * * *"  # Run every minute
```

For production, you may want to adjust the frequency:
- `*/1 * * * *` - Every minute (recommended for responsive delivery)
- `*/5 * * * *` - Every 5 minutes (lighter load)
- `*/15 * * * *` - Every 15 minutes (minimal load)

Apply the configuration:

```bash
# Push config to Supabase
supabase db push
```

### 3. Deploy Backend API

Ensure the new `/api/gift/deliver` endpoint is deployed with your backend:

```bash
# If using Docker
docker build -t drawtopia-backend .
docker push your-registry/drawtopia-backend

# If using direct deployment
# Deploy to your hosting service (e.g., Railway, Heroku, AWS)
```

### 4. Deploy Frontend

Ensure the service worker is properly registered:

```bash
cd drawtopia-frontend
npm run build
# Deploy to your hosting service
```

## Testing

### 1. Test Push Notification Subscription

1. Open frontend in browser
2. Go to Account Settings
3. Enable push notifications
4. Check browser console for subscription success

### 2. Test Gift Creation with Scheduled Delivery

```javascript
// In browser console or API testing tool
const gift = {
  status: 'completed',
  occasion: 'birthday',
  relationship: 'parent',
  delivery_time: new Date(Date.now() + 60000).toISOString(), // 1 minute from now
  child_name: 'Test Child',
  age_group: '5-7',
  delivery_email: 'recipient@example.com',
  special_msg: 'Happy Birthday!'
};

// Create gift via your app
```

### 3. Monitor Cron Job Execution

Check Supabase Edge Function logs:

```bash
supabase functions logs check-scheduled-gifts
```

Or in Supabase Dashboard:
- Edge Functions → check-scheduled-gifts → Logs

### 4. Test Manual Delivery

```bash
# Test the backend endpoint directly
curl -X POST https://your-backend.com/api/gift/deliver \
  -H "Content-Type: application/json" \
  -d '{"gift_id": "your-gift-uuid"}'
```

### 5. Monitor Delivery

Check for:
1. ✅ Cron job runs every minute (check edge function logs)
2. ✅ Gifts are detected when delivery_time approaches
3. ✅ Backend API is called successfully
4. ✅ Push notification is sent
5. ✅ `notification_sent` is set to TRUE in database
6. ✅ User receives notification on their device

## Troubleshooting

### Issue: Cron job not running

**Solution:**
- Check `supabase/config.toml` has the cron schedule
- Verify edge function is deployed: `supabase functions list`
- Check edge function logs for errors

### Issue: No push notification received

**Checklist:**
1. User has granted notification permission
2. User has subscribed to push notifications (check `push_subscriptions` table)
3. VAPID keys are set correctly in edge function secrets
4. Service worker is registered (`/sw.js` accessible)
5. Check browser console for service worker errors

### Issue: Gift not being detected

**Checklist:**
1. `delivery_time` is within 2 minutes of current time
2. `notification_sent` is FALSE or NULL
3. `status` is 'completed'
4. `to_user_id` is not NULL
5. Check database index exists (see schema above)

### Issue: Backend API returning error

**Checklist:**
1. Backend is running and accessible
2. Environment variables are set (`SUPABASE_URL`, `SUPABASE_ANON_KEY`)
3. Check backend logs for detailed error messages
4. Verify edge function URL is correct

## Security Considerations

1. **Edge Function Authentication**: The cron job runs without JWT verification (internal service)
2. **Backend Endpoint**: Consider adding an internal service token for the `/api/gift/deliver` endpoint
3. **VAPID Keys**: Keep private key secret, only public key can be exposed to frontend
4. **Database RLS**: Ensure proper Row Level Security policies on `gifts` and `push_subscriptions` tables

## Monitoring & Maintenance

### Key Metrics to Monitor

1. **Cron Job Success Rate**: % of successful runs
2. **Delivery Success Rate**: % of gifts successfully delivered
3. **Push Subscription Count**: Active users with push enabled
4. **Notification Delivery Time**: Time from scheduled delivery to actual delivery

### Recommended Monitoring Setup

```javascript
// Add to your monitoring service (e.g., Sentry, DataDog)
- Edge function execution count
- Edge function error rate
- Backend API response time
- Push notification success rate
```

## Cost Optimization

1. **Cron Frequency**: Adjust from every minute to every 5 minutes if acceptable
2. **Query Limits**: Already limited to 50 gifts per run
3. **Edge Function Timeout**: Set appropriate timeout (currently 30 seconds)
4. **Database Indexing**: Ensure indexes are in place for fast queries

## Future Enhancements

- [ ] Add retry logic for failed deliveries
- [ ] Support for multiple notification types (email + push + SMS)
- [ ] User timezone awareness for better scheduling
- [ ] Delivery status dashboard for senders
- [ ] A/B testing for notification content
- [ ] Analytics tracking for notification engagement

## Support

For issues or questions:
- Check logs in Supabase Dashboard
- Review backend logs
- Check browser console for frontend errors
- Contact: support@drawtopia.com

