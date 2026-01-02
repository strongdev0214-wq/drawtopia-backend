# Deployment Checklist - Scheduled Gift Delivery System

Use this checklist to ensure proper deployment of the scheduled gift delivery system.

## Pre-Deployment

### 1. Environment Setup
- [ ] Supabase CLI installed (`npm install -g supabase`)
- [ ] Python 3.7+ installed (for testing)
- [ ] Access to Supabase project dashboard
- [ ] Access to backend deployment environment
- [ ] Access to frontend deployment environment

### 2. Generate VAPID Keys
```bash
npx web-push generate-vapid-keys
```
- [ ] Public key saved
- [ ] Private key saved (keep secure!)
- [ ] Keys documented in secure location

### 3. Backup Current System
- [ ] Database backup created
- [ ] Current edge functions backed up
- [ ] Backend code backed up
- [ ] Frontend code backed up

## Database Setup

### 4. Run Migration
- [ ] Connected to Supabase database
- [ ] Ran `scheduled_delivery_migration.sql`
- [ ] Verified no errors in migration
- [ ] Checked tables exist:
  - [ ] `gifts` table has required columns
  - [ ] `push_subscriptions` table created
  - [ ] `scheduled_gifts_pending` view created
- [ ] Verified indexes created:
  - [ ] `idx_gifts_scheduled_delivery`
  - [ ] `idx_push_subscriptions_user_id`

### 5. Verify Database Schema
```sql
-- Run these queries to verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'gifts' 
AND column_name IN ('notification_sent', 'notification_sent_at', 'to_user_id', 'from_user_id');

SELECT * FROM scheduled_gifts_pending LIMIT 1;
```
- [ ] All columns exist
- [ ] View is accessible
- [ ] RLS policies are in place

## Backend Deployment

### 6. Update Backend Code
- [ ] New `/api/gift/deliver` endpoint added to `main.py`
- [ ] Code reviewed for syntax errors
- [ ] No linter errors

### 7. Set Backend Environment Variables
```env
BACKEND_URL=https://your-backend.com
FRONTEND_URL=https://your-frontend.com
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
```
- [ ] All variables set
- [ ] URLs are correct (no trailing slashes)
- [ ] Keys are valid

### 8. Deploy Backend
- [ ] Backend deployed to production
- [ ] Backend health check passes: `GET /health`
- [ ] New endpoint accessible: `POST /api/gift/deliver`
- [ ] Logs are accessible

## Frontend Deployment

### 9. Set Frontend Environment Variables
```env
VITE_VAPID_PUBLIC_KEY=your-vapid-public-key
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```
- [ ] VAPID public key set
- [ ] Supabase URL set
- [ ] Anon key set

### 10. Deploy Frontend
- [ ] Frontend built successfully
- [ ] Service worker (`sw.js`) is accessible
- [ ] Push notification subscription works
- [ ] No console errors

## Edge Functions Deployment

### 11. Set Supabase Secrets
```bash
supabase secrets set VAPID_PUBLIC_KEY=your-key
supabase secrets set VAPID_PRIVATE_KEY=your-key
supabase secrets set VAPID_SUBJECT=mailto:support@drawtopia.com
supabase secrets set BACKEND_URL=https://your-backend.com
```
- [ ] All secrets set
- [ ] Secrets verified: `supabase secrets list`
- [ ] No typos in secret names

### 12. Update Supabase Config
- [ ] `supabase/config.toml` updated with cron schedule
- [ ] Cron frequency appropriate (`*/1 * * * *` for every minute)
- [ ] Both edge functions listed in config

### 13. Deploy Edge Functions
```bash
# Windows
.\deploy_edge_functions.ps1

# Linux/Mac
./deploy_edge_functions.sh
```
- [ ] `check-scheduled-gifts` deployed successfully
- [ ] `send-gift-notification` deployed successfully
- [ ] No deployment errors
- [ ] Functions visible in Supabase Dashboard

### 14. Verify Edge Functions
- [ ] Functions appear in Supabase Dashboard
- [ ] Functions are enabled
- [ ] Cron schedule is active
- [ ] No errors in initial logs

## Testing

### 15. Run Automated Tests
```bash
python test_scheduled_delivery.py
```
- [ ] Backend health check passes
- [ ] Database schema check passes
- [ ] Edge function accessibility passes
- [ ] All tests green

### 16. Test Push Notification Subscription
- [ ] Open frontend in browser
- [ ] Go to account settings
- [ ] Enable push notifications
- [ ] Check browser grants permission
- [ ] Verify subscription in `push_subscriptions` table

### 17. Test Manual Gift Delivery
```bash
# Create a test gift first, then:
curl -X POST https://your-backend.com/api/gift/deliver \
  -H "Content-Type: application/json" \
  -d '{"gift_id": "your-test-gift-id"}'
```
- [ ] API returns success
- [ ] Push notification received
- [ ] `notification_sent` set to TRUE
- [ ] `notification_sent_at` timestamp set

### 18. Test Scheduled Delivery
- [ ] Create gift with delivery_time = now + 90 seconds
- [ ] Wait for cron job to run
- [ ] Check edge function logs
- [ ] Verify backend API called
- [ ] Verify push notification sent
- [ ] Verify gift delivered successfully

### 19. Monitor First Hour
- [ ] Cron job runs every minute (check logs)
- [ ] No errors in edge function logs
- [ ] No errors in backend logs
- [ ] Database queries performing well
- [ ] Push notifications delivering successfully

## Monitoring Setup

### 20. Set Up Monitoring
- [ ] Edge function logs accessible
- [ ] Backend logs accessible
- [ ] Database monitoring enabled
- [ ] Alerts configured for:
  - [ ] Edge function failures
  - [ ] Backend API errors
  - [ ] Database query timeouts
  - [ ] Push notification failures

### 21. Create Monitoring Queries
```sql
-- Pending gifts
SELECT * FROM scheduled_gifts_pending;

-- Recent deliveries
SELECT id, delivery_time, notification_sent_at,
       EXTRACT(EPOCH FROM (notification_sent_at - delivery_time)) as delay_seconds
FROM gifts
WHERE notification_sent = TRUE
ORDER BY notification_sent_at DESC
LIMIT 10;

-- Delivery success rate (last 24h)
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN notification_sent THEN 1 ELSE 0 END) as delivered,
  ROUND(100.0 * SUM(CASE WHEN notification_sent THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM gifts
WHERE delivery_time > NOW() - INTERVAL '24 hours';
```
- [ ] Queries saved and accessible
- [ ] Dashboard created (optional)
- [ ] Team has access to monitoring

## Documentation

### 22. Update Documentation
- [ ] Team briefed on new system
- [ ] Documentation shared:
  - [ ] `QUICK_START.md`
  - [ ] `SCHEDULED_DELIVERY_SETUP.md`
  - [ ] `IMPLEMENTATION_SUMMARY.md`
- [ ] Troubleshooting guide accessible
- [ ] Support contacts updated

## Post-Deployment

### 23. Verify Production
- [ ] System running for 24 hours without issues
- [ ] At least one successful scheduled delivery
- [ ] No unexpected errors
- [ ] Performance metrics acceptable
- [ ] User feedback positive

### 24. Optimize if Needed
- [ ] Review cron frequency (adjust if needed)
- [ ] Review batch size (adjust if needed)
- [ ] Review database query performance
- [ ] Review edge function costs

### 25. Final Checks
- [ ] Rollback plan documented
- [ ] Incident response plan ready
- [ ] Team trained on troubleshooting
- [ ] Success metrics defined and tracked

## Rollback Plan (If Needed)

### If Issues Occur:
1. [ ] Disable cron job (remove from `config.toml`)
2. [ ] Redeploy previous backend version
3. [ ] Restore database backup if needed
4. [ ] Notify users of temporary service interruption
5. [ ] Debug issues in staging environment
6. [ ] Re-deploy when issues resolved

## Success Criteria

✅ All checklist items completed  
✅ Zero errors in logs for 24 hours  
✅ At least 3 successful scheduled deliveries  
✅ Push notifications working on multiple devices  
✅ Database queries performing well (<100ms)  
✅ Team comfortable with monitoring and troubleshooting  

## Sign-Off

- [ ] Developer: _________________ Date: _______
- [ ] QA: _________________ Date: _______
- [ ] DevOps: _________________ Date: _______
- [ ] Product Owner: _________________ Date: _______

---

**Deployment Status:** ⬜ Not Started | 🟡 In Progress | ✅ Complete

**Deployment Date:** __________________

**Deployed By:** __________________

**Notes:**
_____________________________________
_____________________________________
_____________________________________

