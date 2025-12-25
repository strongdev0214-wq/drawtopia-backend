"""
Email Service for Drawtopia
Uses Resend for sending transactional emails (free tier: 100 emails/day)

Supported email types:
- Payment success confirmation
- Payment failure notification
- Subscription cancellation confirmation
- Subscription activation confirmation

Setup:
1. Create account at https://resend.com
2. Get API key from dashboard
3. Add RESEND_API_KEY to .env
4. (Optional) Add custom domain later for branded emails
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import resend, gracefully handle if not installed
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend package not installed. Run: pip install resend")

# Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")  # Use resend.dev for testing
FROM_NAME = os.getenv("FROM_NAME", "Drawtopia")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Initialize Resend
if RESEND_API_KEY and RESEND_AVAILABLE:
    resend.api_key = RESEND_API_KEY
    logger.info("✅ Email service (Resend) initialized successfully")
else:
    if not RESEND_AVAILABLE:
        logger.warning("⚠️ Resend package not available. Email notifications disabled.")
    else:
        logger.warning("⚠️ RESEND_API_KEY not found. Email notifications disabled.")


class EmailService:
    """Email service for sending transactional emails"""
    
    def __init__(self):
        self.enabled = bool(RESEND_API_KEY and RESEND_AVAILABLE)
        self.from_email = f"{FROM_NAME} <{FROM_EMAIL}>"
    
    def is_enabled(self) -> bool:
        """Check if email service is enabled"""
        return self.enabled
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email using Resend
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body of the email
            text_content: Plain text body (optional, for email clients that don't support HTML)
        
        Returns:
            Dict with 'success' boolean and 'id' or 'error'
        """
        if not self.enabled:
            logger.warning("Email service not enabled, skipping email send")
            return {"success": False, "error": "Email service not configured"}
        
        try:
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            
            if text_content:
                params["text"] = text_content
            
            email = resend.Emails.send(params)
            
            logger.info(f"✅ Email sent successfully to {to_email}: {email.get('id', 'unknown')}")
            return {"success": True, "id": email.get("id")}
            
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== EMAIL TEMPLATES ====================
    
    async def send_payment_success_email(
        self,
        to_email: str,
        customer_name: Optional[str] = None,
        plan_type: str = "monthly",
        amount: Optional[str] = None,
        next_billing_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send payment success confirmation email
        
        Args:
            to_email: Customer email address
            customer_name: Customer name (optional)
            plan_type: Subscription plan type (monthly/yearly)
            amount: Payment amount (e.g., "$9.99")
            next_billing_date: Next billing date
        """
        name = customer_name or "there"
        plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
        amount_display = amount or ("$9.99" if plan_type == "monthly" else "$99.99")
        
        subject = "🎉 Payment Successful - Welcome to Drawtopia Premium!"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7fa;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px 16px 0 0; padding: 40px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🎨 Drawtopia</h1>
            <p style="color: rgba(255,255,255,0.9); margin-top: 8px;">Your Creative AI Companion</p>
        </div>
        
        <!-- Content -->
        <div style="background: white; padding: 40px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background: #10b981; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;">
                    <span style="font-size: 30px;">✓</span>
                </div>
            </div>
            
            <h2 style="color: #1a1a2e; margin: 0 0 20px 0; text-align: center;">Payment Successful!</h2>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                Hi {name},
            </p>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                Thank you for subscribing to Drawtopia Premium! Your payment has been processed successfully.
            </p>
            
            <!-- Payment Details Box -->
            <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #667eea;">
                <h3 style="color: #1a1a2e; margin: 0 0 16px 0; font-size: 16px;">Payment Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Plan</td>
                        <td style="color: #1a1a2e; text-align: right; font-weight: 600;">{plan_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Amount</td>
                        <td style="color: #1a1a2e; text-align: right; font-weight: 600;">{amount_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Status</td>
                        <td style="color: #10b981; text-align: right; font-weight: 600;">✓ Paid</td>
                    </tr>
                    {f'<tr><td style="color: #718096; padding: 8px 0;">Next billing</td><td style="color: #1a1a2e; text-align: right;">{next_billing_date}</td></tr>' if next_billing_date else ''}
                </table>
            </div>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                Your premium features are now active! You have unlimited access to:
            </p>
            
            <ul style="color: #4a5568; line-height: 1.8; padding-left: 20px;">
                <li>Unlimited AI image generations</li>
                <li>Priority processing</li>
                <li>Advanced story creation tools</li>
                <li>Premium templates and styles</li>
            </ul>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{FRONTEND_URL}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                    Start Creating
                </a>
            </div>
            
            <p style="color: #718096; font-size: 14px; text-align: center; margin-top: 32px;">
                Questions? Just reply to this email and we'll help you out!
            </p>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; padding: 24px; color: #718096; font-size: 12px;">
            <p style="margin: 0;">© {datetime.now().year} Drawtopia. All rights reserved.</p>
            <p style="margin: 8px 0 0 0;">
                <a href="{FRONTEND_URL}/account" style="color: #667eea; text-decoration: none;">Manage Subscription</a>
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        text_content = f"""
Payment Successful - Welcome to Drawtopia Premium!

Hi {name},

Thank you for subscribing to Drawtopia Premium! Your payment has been processed successfully.

Payment Details:
- Plan: {plan_display}
- Amount: {amount_display}
- Status: Paid
{f'- Next billing: {next_billing_date}' if next_billing_date else ''}

Your premium features are now active! You have unlimited access to:
• Unlimited AI image generations
• Priority processing
• Advanced story creation tools
• Premium templates and styles

Start creating: {FRONTEND_URL}

Questions? Just reply to this email!

© {datetime.now().year} Drawtopia
"""
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_payment_failed_email(
        self,
        to_email: str,
        customer_name: Optional[str] = None,
        plan_type: str = "monthly",
        amount: Optional[str] = None,
        retry_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send payment failure notification email
        
        Args:
            to_email: Customer email address
            customer_name: Customer name (optional)
            plan_type: Subscription plan type (monthly/yearly)
            amount: Payment amount that failed
            retry_url: URL to retry payment
        """
        name = customer_name or "there"
        plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
        amount_display = amount or ("$9.99" if plan_type == "monthly" else "$99.99")
        update_url = retry_url or f"{FRONTEND_URL}/account"
        
        subject = "⚠️ Payment Failed - Action Required"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7fa;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px 16px 0 0; padding: 40px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🎨 Drawtopia</h1>
            <p style="color: rgba(255,255,255,0.9); margin-top: 8px;">Your Creative AI Companion</p>
        </div>
        
        <!-- Content -->
        <div style="background: white; padding: 40px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="background: #ef4444; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;">
                    <span style="font-size: 30px;">!</span>
                </div>
            </div>
            
            <h2 style="color: #1a1a2e; margin: 0 0 20px 0; text-align: center;">Payment Failed</h2>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                Hi {name},
            </p>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                We were unable to process your payment for your Drawtopia subscription. This could be due to:
            </p>
            
            <ul style="color: #4a5568; line-height: 1.8; padding-left: 20px; margin-bottom: 20px;">
                <li>Insufficient funds</li>
                <li>Expired card</li>
                <li>Card declined by your bank</li>
            </ul>
            
            <!-- Payment Details Box -->
            <div style="background: #fef2f2; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #ef4444;">
                <h3 style="color: #1a1a2e; margin: 0 0 16px 0; font-size: 16px;">Payment Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Plan</td>
                        <td style="color: #1a1a2e; text-align: right; font-weight: 600;">{plan_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Amount</td>
                        <td style="color: #1a1a2e; text-align: right; font-weight: 600;">{amount_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #718096; padding: 8px 0;">Status</td>
                        <td style="color: #ef4444; text-align: right; font-weight: 600;">✗ Failed</td>
                    </tr>
                </table>
            </div>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                <strong>To keep your premium access</strong>, please update your payment method within the next 7 days.
            </p>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{update_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                    Update Payment Method
                </a>
            </div>
            
            <p style="color: #718096; font-size: 14px; text-align: center; margin-top: 32px;">
                Need help? Reply to this email and we'll assist you right away.
            </p>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; padding: 24px; color: #718096; font-size: 12px;">
            <p style="margin: 0;">© {datetime.now().year} Drawtopia. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
        
        text_content = f"""
Payment Failed - Action Required

Hi {name},

We were unable to process your payment for your Drawtopia subscription.

This could be due to:
• Insufficient funds
• Expired card
• Card declined by your bank

Payment Details:
- Plan: {plan_display}
- Amount: {amount_display}
- Status: Failed

To keep your premium access, please update your payment method within the next 7 days.

Update payment: {update_url}

Need help? Reply to this email!

© {datetime.now().year} Drawtopia
"""
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_subscription_cancelled_email(
        self,
        to_email: str,
        customer_name: Optional[str] = None,
        plan_type: str = "monthly",
        access_until: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send subscription cancellation confirmation email
        
        Args:
            to_email: Customer email address
            customer_name: Customer name (optional)
            plan_type: Subscription plan type that was cancelled
            access_until: Date until which access remains
        """
        name = customer_name or "there"
        plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
        access_info = f"Your premium access will remain active until <strong>{access_until}</strong>." if access_until else "Your premium access has been deactivated."
        
        subject = "Your Drawtopia Subscription Has Been Cancelled"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7fa;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px 16px 0 0; padding: 40px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🎨 Drawtopia</h1>
            <p style="color: rgba(255,255,255,0.9); margin-top: 8px;">Your Creative AI Companion</p>
        </div>
        
        <!-- Content -->
        <div style="background: white; padding: 40px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <h2 style="color: #1a1a2e; margin: 0 0 20px 0; text-align: center;">Subscription Cancelled</h2>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                Hi {name},
            </p>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                We're sorry to see you go! Your <strong>{plan_display}</strong> subscription to Drawtopia has been cancelled.
            </p>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                {access_info}
            </p>
            
            <!-- Info Box -->
            <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #718096;">
                <h3 style="color: #1a1a2e; margin: 0 0 12px 0; font-size: 16px;">What happens next?</h3>
                <ul style="color: #4a5568; line-height: 1.8; padding-left: 20px; margin: 0;">
                    <li>You can continue using free features</li>
                    <li>Your created content remains accessible</li>
                    <li>You can resubscribe anytime</li>
                </ul>
            </div>
            
            <p style="color: #4a5568; line-height: 1.6; margin-bottom: 20px;">
                We'd love to have you back! If you change your mind, you can resubscribe at any time.
            </p>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{FRONTEND_URL}/pricing" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                    Resubscribe
                </a>
            </div>
            
            <p style="color: #718096; font-size: 14px; text-align: center; margin-top: 32px;">
                Was this a mistake? Reply to this email and we'll help sort it out.
            </p>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; padding: 24px; color: #718096; font-size: 12px;">
            <p style="margin: 0;">© {datetime.now().year} Drawtopia. All rights reserved.</p>
            <p style="margin: 8px 0 0 0;">
                We hope to see you again soon! 💜
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        text_content = f"""
Your Drawtopia Subscription Has Been Cancelled

Hi {name},

We're sorry to see you go! Your {plan_display} subscription to Drawtopia has been cancelled.

{access_info.replace('<strong>', '').replace('</strong>', '')}

What happens next?
• You can continue using free features
• Your created content remains accessible
• You can resubscribe anytime

We'd love to have you back! If you change your mind, resubscribe at:
{FRONTEND_URL}/pricing

Was this a mistake? Reply to this email and we'll help!

© {datetime.now().year} Drawtopia
"""
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_subscription_activated_email(
        self,
        to_email: str,
        customer_name: Optional[str] = None,
        plan_type: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Send subscription activation confirmation email (for new subscriptions)
        
        Args:
            to_email: Customer email address
            customer_name: Customer name (optional)
            plan_type: Subscription plan type
        """
        # This uses the same template as payment success for new subscriptions
        return await self.send_payment_success_email(
            to_email=to_email,
            customer_name=customer_name,
            plan_type=plan_type
        )


# Create a singleton instance
email_service = EmailService()


# Convenience functions for direct use
async def send_payment_success(to_email: str, **kwargs) -> Dict[str, Any]:
    """Send payment success email"""
    return await email_service.send_payment_success_email(to_email, **kwargs)


async def send_payment_failed(to_email: str, **kwargs) -> Dict[str, Any]:
    """Send payment failed email"""
    return await email_service.send_payment_failed_email(to_email, **kwargs)


async def send_subscription_cancelled(to_email: str, **kwargs) -> Dict[str, Any]:
    """Send subscription cancelled email"""
    return await email_service.send_subscription_cancelled_email(to_email, **kwargs)


async def send_subscription_activated(to_email: str, **kwargs) -> Dict[str, Any]:
    """Send subscription activated email"""
    return await email_service.send_subscription_activated_email(to_email, **kwargs)

