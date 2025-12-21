# Push Notifications Setup Guide

This guide explains how to set up the scheduled push notification system for gift delivery.

## Prerequisites

- Supabase project with CLI installed
- VAPID keys for Web Push (or FCM server key)
- pg_cron enabled in your Supabase project

## Step 1: Database Migration

Run the following SQL files in your Supabase SQL Editor:

1. **Push Notifications Migration**: `push_notifications_migration.sql`
   - Adds notification columns to gifts table
   - Creates push_subscriptions table
   - Sets up RLS policies

2. **pg_cron Setup**: `pg_cron_setup.sql`
   - Enables pg_cron extension
   - Creates scheduled job to check for gifts ready for notification
   - Runs every minute (or every 5 minutes for production)

## Step 2: Generate VAPID Keys

Web Push requires VAPID keys for authentication. Generate them using:

```bash
# Using web-push library
npx web-push generate-vapid-keys
```

Or use an online generator: https://vapidkeys.com/

Save the keys - you'll need them for both backend and frontend.

## Step 3: Set Supabase Secrets

Set the following secrets in your Supabase project:

```bash
# VAPID keys
supabase secrets set VAPID_PUBLIC_KEY="your-public-key"
supabase secrets set VAPID_PRIVATE_KEY="your-private-key"
supabase secrets set VAPID_SUBJECT="mailto:your-email@domain.com"

# Optional: FCM (Firebase Cloud Messaging) key
supabase secrets set FCM_SERVER_KEY="your-fcm-server-key"
```

## Step 4: Deploy Edge Function

Deploy the Edge Function to Supabase:

```bash
cd drawtopia-backend
supabase functions deploy send-gift-notification
```

## Step 5: Configure pg_cron to Call Edge Function

Update the `process_scheduled_gift_notifications()` function to call the Edge Function:

```sql
-- Set your Edge Function URL in database settings
ALTER DATABASE postgres SET app.settings.edge_function_url = 
  'https://your-project-ref.supabase.co/functions/v1/send-gift-notification';

ALTER DATABASE postgres SET app.settings.supabase_anon_key = 
  'your-anon-key';
```

Or use a simpler approach - let the Edge Function poll for scheduled notifications:

```bash
# Create a cron job that calls the Edge Function via HTTP
# (Requires pg_net extension)
SELECT cron.schedule(
  'call-notification-function',
  '* * * * *',  -- Every minute
  $$
  SELECT net.http_post(
    url := 'https://your-project-ref.supabase.co/functions/v1/send-gift-notification',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || current_setting('app.settings.supabase_anon_key')
    ),
    body := jsonb_build_object('mode', 'batch')
  );
  $$
);
```

## Step 6: Frontend Integration

See the frontend setup in `drawtopia-frontend/` for:

1. Service Worker registration
2. Push subscription management
3. Notification display
4. Notification badge

## Testing

### Test Push Notification Manually

Call the Edge Function directly:

```bash
curl -X POST \
  https://your-project-ref.supabase.co/functions/v1/send-gift-notification \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"giftId": "your-gift-id", "mode": "single"}'
```

### Test Scheduled Delivery

1. Create a gift with `delivery_time` set to current time or near future
2. Wait for the cron job to run (every minute)
3. Check that `notification_scheduled` becomes `true`
4. Edge Function will process and send notification
5. Check that `notification_sent` becomes `true` and `notification_sent_at` is set

## Monitoring

### View Cron Job Status

```sql
-- List all cron jobs
SELECT * FROM cron.job;

-- View recent job runs
SELECT * FROM cron.job_run_details 
ORDER BY start_time DESC 
LIMIT 20;
```

### Check Notification Status

```sql
-- Gifts awaiting notification
SELECT id, child_name, delivery_time, notification_scheduled, notification_sent
FROM gifts
WHERE notification_sent = false
  AND status = 'completed'
  AND delivery_time <= NOW()
ORDER BY delivery_time;

-- Recently sent notifications
SELECT id, child_name, delivery_time, notification_sent_at
FROM gifts
WHERE notification_sent = true
ORDER BY notification_sent_at DESC
LIMIT 20;
```

## Troubleshooting

### Notifications Not Sending

1. Check cron job is running: `SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 5;`
2. Verify Edge Function logs in Supabase Dashboard
3. Check push_subscriptions table has valid subscriptions
4. Verify VAPID keys are set correctly
5. Check browser console for service worker errors

### Invalid Push Subscriptions

The system automatically removes invalid subscriptions (HTTP 410 responses).

### Performance

- Cron job processes up to 50 gifts per run
- Adjust frequency based on load (every 1-5 minutes)
- Monitor Edge Function execution time

## Security Notes

- Push subscriptions are user-specific (RLS enabled)
- Edge Function uses service role key to bypass RLS
- VAPID keys should be kept secret
- Consider rate limiting for production

## Alternative: Using Firebase Cloud Messaging (FCM)

If you prefer FCM over raw Web Push:

1. Create a Firebase project
2. Enable Cloud Messaging
3. Get Server Key from Firebase Console
4. Set `FCM_SERVER_KEY` in Supabase secrets
5. Use FCM SDK in frontend instead of Web Push API

The Edge Function already supports FCM as a fallback.

