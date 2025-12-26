"""
Subscription Renewal Reminder Cron Job
Runs daily to send reminder emails 7 days before subscription renewal
"""

import asyncio
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
from email_queue import EmailQueueManager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_KEY else None


async def send_renewal_reminders():
    """
    Send renewal reminder emails for subscriptions renewing in 7 days
    """
    if not supabase:
        logger.error("❌ Supabase not configured")
        return
    
    try:
        email_queue_manager = EmailQueueManager(supabase)
        
        # Calculate target renewal date (7 days from now)
        target_date = datetime.now() + timedelta(days=7)
        target_date_str = target_date.date().isoformat()
        
        logger.info(f"🔍 Checking for subscriptions renewing on {target_date_str}")
        
        # Get active subscriptions renewing in 7 days
        # Note: Adjust the date comparison based on your schema
        subscriptions_response = supabase.table("subscriptions") \
            .select("id, stripe_customer_id, customer_email, plan_type, current_period_end, stripe_subscription_id") \
            .eq("status", "active") \
            .execute()
        
        if not subscriptions_response.data:
            logger.info("✅ No active subscriptions found")
            return
        
        emails_queued = 0
        
        for subscription in subscriptions_response.data:
            try:
                # Parse the renewal date
                renewal_date_str = subscription.get("current_period_end")
                if not renewal_date_str:
                    continue
                
                renewal_date = datetime.fromisoformat(renewal_date_str.replace('Z', '+00:00'))
                renewal_date_only = renewal_date.date()
                
                # Check if renewal is exactly 7 days from now
                if renewal_date_only != target_date.date():
                    continue
                
                # Get user details
                customer_email = subscription.get("customer_email")
                stripe_customer_id = subscription.get("stripe_customer_id")
                
                # Try to get email from customer if not in subscription
                if not customer_email and stripe_customer_id:
                    user_response = supabase.table("users") \
                        .select("email, first_name, last_name") \
                        .eq("stripe_customer_id", stripe_customer_id) \
                        .execute()
                    
                    if user_response.data and len(user_response.data) > 0:
                        user = user_response.data[0]
                        customer_email = user.get("email")
                        customer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Customer"
                    else:
                        customer_name = "Customer"
                else:
                    customer_name = "Customer"
                
                if not customer_email:
                    logger.warning(f"⚠️ No email found for subscription {subscription['id']}")
                    continue
                
                # Get plan amount (you may need to adjust this based on your plan structure)
                plan_type = subscription.get("plan_type", "monthly")
                renewal_amount = 9.99 if plan_type == "monthly" else 99.99
                
                # Generate management links
                manage_link = f"{FRONTEND_URL}/account"
                
                # Stripe portal link (you'll need to generate this via Stripe API in production)
                stripe_subscription_id = subscription.get("stripe_subscription_id")
                cancel_link = f"{FRONTEND_URL}/account"  # User can cancel via account page
                
                # Queue renewal reminder email
                result = email_queue_manager.queue_email(
                    email_type="subscription_renewal_reminder",
                    to_email=customer_email,
                    email_data={
                        "customer_name": customer_name,
                        "plan_type": f"{plan_type.capitalize()} Subscription",
                        "renewal_amount": renewal_amount,
                        "renewal_date": renewal_date,
                        "manage_link": manage_link,
                        "cancel_link": cancel_link
                    },
                    priority=2
                )
                
                if result.get("id"):
                    emails_queued += 1
                    logger.info(f"✅ Renewal reminder queued for {customer_email} (renews {renewal_date_str})")
                else:
                    logger.error(f"❌ Failed to queue renewal reminder for {customer_email}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing subscription {subscription.get('id')}: {e}")
                continue
        
        logger.info(f"✅ Completed: {emails_queued} renewal reminder(s) queued")
        
    except Exception as e:
        logger.error(f"❌ Error in send_renewal_reminders: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def main():
    """Main entry point for the cron job"""
    logger.info("=" * 50)
    logger.info("🔔 Starting Subscription Renewal Reminder Job")
    logger.info("=" * 50)
    
    await send_renewal_reminders()
    
    logger.info("=" * 50)
    logger.info("✅ Subscription Renewal Reminder Job Complete")
    logger.info("=" * 50)


if __name__ == "__main__":
    # Run the cron job
    asyncio.run(main())

