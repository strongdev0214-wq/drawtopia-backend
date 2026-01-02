# Quick Start Guide - Scheduled Gift Delivery

Get the scheduled gift delivery system up and running in 5 minutes.

## Prerequisites

- ✅ Supabase project set up
- ✅ Backend deployed and running
- ✅ Frontend deployed and running
- ✅ Supabase CLI installed: `npm install -g supabase`

## Step 1: Generate VAPID Keys (1 minute)

```bash
npx web-push generate-vapid-keys
```

Save the output:
```
Public Key: BNxxx...
Private Key: xxx...
```

## Step 2: Set Environment Variables (2 minutes)

### Backend `.env`
```env
BACKEND_URL=https://your-backend.com
FRONTEND_URL=https://your-frontend.com
```

### Frontend `.env`
```env
VITE_VAPID_PUBLIC_KEY=BNxxx... (from Step 1)
```

### Supabase Secrets
```bash
supabase secrets set VAPID_PUBLIC_KEY=BNxxx...
supabase secrets set VAPID_PRIVATE_KEY=xxx...
supabase secrets set VAPID_SUBJECT=mailto:support@drawtopia.com
supabase secrets set BACKEND_URL=https://your-backend.com
```

## Step 3: Deploy Database Migration (1 minute)

```bash
# Connect to your Supabase database
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"

# Run migration
\i scheduled_delivery_migration.sql
```

Or via Supabase Dashboard:
1. Go to SQL Editor
2. Copy contents of `scheduled_delivery_migration.sql`
3. Run query

## Step 4: Deploy Edge Functions (1 minute)

### Windows
```powershell
.\deploy_edge_functions.ps1
```

### Linux/Mac
```bash
chmod +x deploy_edge_functions.sh
./deploy_edge_functions.sh
```

Or manually:
```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase functions deploy check-scheduled-gifts --no-verify-jwt
supabase functions deploy send-gift-notification --no-verify-jwt
```

## Step 5: Test the System (1 minute)

```bash
python test_scheduled_delivery.py
```

Expected output:
```
✅ Backend is healthy
✅ Database schema is correct
✅ Edge functions are accessible
✅ All tests passed!
```

## Step 6: Test with Real Gift

1. Create a gift in your app
2. Set `delivery_time` to 1-2 minutes from now
3. Ensure recipient has push notifications enabled
4. Wait for delivery
5. Check logs:
   - Supabase Dashboard → Edge Functions → check-scheduled-gifts → Logs
   - Backend logs for `/api/gift/deliver` calls

## Verify It's Working

### Check Cron Job is Running
```bash
supabase functions logs check-scheduled-gifts
```

You should see logs every minute.

### Check Pending Gifts
```sql
SELECT * FROM scheduled_gifts_pending;
```

### Check Recent Deliveries
```sql
SELECT id, child_name, delivery_time, notification_sent, notification_sent_at
FROM gifts
WHERE notification_sent = TRUE
ORDER BY notification_sent_at DESC
LIMIT 5;
```

## Troubleshooting

### Cron not running?
- Check `supabase/config.toml` has cron configuration
- Redeploy: `supabase functions deploy check-scheduled-gifts --no-verify-jwt`

### No push notification?
- User must enable notifications in browser
- Check `push_subscriptions` table has user's subscription
- Check VAPID keys are set correctly

### Gift not detected?
- Ensure `delivery_time` is within 2 minutes
- Ensure `status` = 'completed'
- Ensure `to_user_id` is not null
- Ensure `notification_sent` = FALSE

## Common Commands

```bash
# Check edge function logs
supabase functions logs check-scheduled-gifts

# List secrets
supabase secrets list

# Set a secret
supabase secrets set KEY=value

# Test backend endpoint
curl -X POST https://your-backend.com/api/gift/deliver \
  -H "Content-Type: application/json" \
  -d '{"gift_id": "your-gift-uuid"}'

# Check database
psql "your-connection-string" -c "SELECT * FROM scheduled_gifts_pending;"
```

## Success Indicators

✅ Cron job runs every minute (check logs)  
✅ Gifts are detected when delivery_time approaches  
✅ Backend API is called successfully  
✅ Push notification is sent  
✅ `notification_sent` is set to TRUE  
✅ User receives notification on device  

## Next Steps

- Monitor edge function logs for first 24 hours
- Set up alerts for failed deliveries
- Adjust cron frequency if needed (in `config.toml`)
- Review `SCHEDULED_DELIVERY_SETUP.md` for advanced configuration

## Need Help?

1. Run: `python test_scheduled_delivery.py`
2. Check: `SCHEDULED_DELIVERY_SETUP.md` (detailed guide)
3. Review: `IMPLEMENTATION_SUMMARY.md` (architecture overview)
4. Logs: Supabase Dashboard → Edge Functions → Logs

---

**Estimated Setup Time:** 5-10 minutes  
**Difficulty:** Easy  
**Status:** Production Ready ✅

