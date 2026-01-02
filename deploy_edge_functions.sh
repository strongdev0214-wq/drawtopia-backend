#!/bin/bash
# Deployment script for Supabase Edge Functions
# This script deploys both edge functions required for scheduled gift delivery

set -e  # Exit on error

echo "🚀 Starting Edge Functions Deployment..."
echo ""

# Check if Supabase CLI is installed
if ! command -v supabase &> /dev/null; then
    echo "❌ Error: Supabase CLI is not installed"
    echo "Install it with: npm install -g supabase"
    exit 1
fi

echo "✅ Supabase CLI found"
echo ""

# Check if logged in
if ! supabase projects list &> /dev/null; then
    echo "❌ Error: Not logged in to Supabase"
    echo "Run: supabase login"
    exit 1
fi

echo "✅ Authenticated with Supabase"
echo ""

# Check if project is linked
if [ ! -f ".supabase/config.toml" ]; then
    echo "⚠️  Warning: Project not linked"
    echo "Run: supabase link --project-ref YOUR_PROJECT_REF"
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Deploying Edge Functions..."
echo ""

# Deploy send-gift-notification function
echo "1️⃣  Deploying send-gift-notification..."
if supabase functions deploy send-gift-notification --no-verify-jwt; then
    echo "✅ send-gift-notification deployed successfully"
else
    echo "❌ Failed to deploy send-gift-notification"
    exit 1
fi
echo ""

# Deploy check-scheduled-gifts function
echo "2️⃣  Deploying check-scheduled-gifts..."
if supabase functions deploy check-scheduled-gifts --no-verify-jwt; then
    echo "✅ check-scheduled-gifts deployed successfully"
else
    echo "❌ Failed to deploy check-scheduled-gifts"
    exit 1
fi
echo ""

echo "🎉 All Edge Functions deployed successfully!"
echo ""

# Check if secrets are set
echo "🔐 Checking required secrets..."
echo ""
echo "Required secrets for edge functions:"
echo "  - VAPID_PUBLIC_KEY"
echo "  - VAPID_PRIVATE_KEY"
echo "  - VAPID_SUBJECT"
echo "  - BACKEND_URL"
echo "  - SUPABASE_URL (auto-set)"
echo "  - SUPABASE_SERVICE_ROLE_KEY (auto-set)"
echo ""
echo "To set secrets, run:"
echo "  supabase secrets set VAPID_PUBLIC_KEY=your_key"
echo "  supabase secrets set VAPID_PRIVATE_KEY=your_key"
echo "  supabase secrets set VAPID_SUBJECT=mailto:support@drawtopia.com"
echo "  supabase secrets set BACKEND_URL=https://your-backend.com"
echo ""

# List current secrets (without values)
echo "Current secrets:"
supabase secrets list 2>/dev/null || echo "  (Unable to list secrets)"
echo ""

echo "📝 Next Steps:"
echo "  1. Set all required secrets (see above)"
echo "  2. Run database migration: psql -f scheduled_delivery_migration.sql"
echo "  3. Test the cron job: Check logs in Supabase Dashboard"
echo "  4. Monitor deliveries using the scheduled_gifts_pending view"
echo ""
echo "✨ Deployment complete!"

