# PowerShell Deployment Script for Supabase Edge Functions
# This script deploys both edge functions required for scheduled gift delivery

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Edge Functions Deployment..." -ForegroundColor Cyan
Write-Host ""

# Check if Supabase CLI is installed
try {
    $null = Get-Command supabase -ErrorAction Stop
    Write-Host "✅ Supabase CLI found" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Supabase CLI is not installed" -ForegroundColor Red
    Write-Host "Install it with: npm install -g supabase" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Check if logged in
try {
    $null = supabase projects list 2>&1
    Write-Host "✅ Authenticated with Supabase" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Not logged in to Supabase" -ForegroundColor Red
    Write-Host "Run: supabase login" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Check if project is linked
if (-not (Test-Path ".supabase/config.toml")) {
    Write-Host "⚠️  Warning: Project not linked" -ForegroundColor Yellow
    Write-Host "Run: supabase link --project-ref YOUR_PROJECT_REF" -ForegroundColor Yellow
    $response = Read-Host "Do you want to continue anyway? (y/n)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
}

Write-Host "📦 Deploying Edge Functions..." -ForegroundColor Cyan
Write-Host ""

# Deploy send-gift-notification function
Write-Host "1️⃣  Deploying send-gift-notification..." -ForegroundColor Cyan
try {
    supabase functions deploy send-gift-notification --no-verify-jwt
    Write-Host "✅ send-gift-notification deployed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to deploy send-gift-notification" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Deploy check-scheduled-gifts function
Write-Host "2️⃣  Deploying check-scheduled-gifts..." -ForegroundColor Cyan
try {
    supabase functions deploy check-scheduled-gifts --no-verify-jwt
    Write-Host "✅ check-scheduled-gifts deployed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to deploy check-scheduled-gifts" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "🎉 All Edge Functions deployed successfully!" -ForegroundColor Green
Write-Host ""

# Check if secrets are set
Write-Host "🔐 Checking required secrets..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Required secrets for edge functions:" -ForegroundColor Yellow
Write-Host "  - VAPID_PUBLIC_KEY"
Write-Host "  - VAPID_PRIVATE_KEY"
Write-Host "  - VAPID_SUBJECT"
Write-Host "  - BACKEND_URL"
Write-Host "  - SUPABASE_URL (auto-set)"
Write-Host "  - SUPABASE_SERVICE_ROLE_KEY (auto-set)"
Write-Host ""
Write-Host "To set secrets, run:" -ForegroundColor Yellow
Write-Host "  supabase secrets set VAPID_PUBLIC_KEY=your_key"
Write-Host "  supabase secrets set VAPID_PRIVATE_KEY=your_key"
Write-Host "  supabase secrets set VAPID_SUBJECT=mailto:support@drawtopia.com"
Write-Host "  supabase secrets set BACKEND_URL=https://your-backend.com"
Write-Host ""

# List current secrets (without values)
Write-Host "Current secrets:" -ForegroundColor Cyan
try {
    supabase secrets list 2>$null
} catch {
    Write-Host "  (Unable to list secrets)" -ForegroundColor Gray
}
Write-Host ""

Write-Host "📝 Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Set all required secrets (see above)"
Write-Host "  2. Run database migration: psql -f scheduled_delivery_migration.sql"
Write-Host "  3. Test the cron job: Check logs in Supabase Dashboard"
Write-Host "  4. Monitor deliveries using the scheduled_gifts_pending view"
Write-Host ""
Write-Host "✨ Deployment complete!" -ForegroundColor Green

