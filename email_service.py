"""
Email Service Module using Resend

Handles sending transactional emails for:
- Payment success confirmation
- Payment failure notification
- Subscription cancellation confirmation
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("⚠️ resend package not installed. Email functionality will be disabled.")

# Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "Drawtopia <notifications@drawtopia.com>")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@drawtopia.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Initialize Resend
if RESEND_AVAILABLE and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    logger.info("✅ Resend email service initialized successfully")
else:
    if not RESEND_API_KEY:
        logger.warning("⚠️ RESEND_API_KEY not found. Email functionality will be disabled.")


class EmailService:
    """Email service for sending transactional emails via Resend"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if email service is available"""
        return RESEND_AVAILABLE and bool(RESEND_API_KEY)
    
    @staticmethod
    def _format_amount(amount_cents: int, currency: str = "usd") -> str:
        """Format amount from cents to display string"""
        amount = amount_cents / 100
        currency_symbols = {
            "usd": "$",
            "eur": "€",
            "gbp": "£",
            "jpy": "¥",
        }
        symbol = currency_symbols.get(currency.lower(), "$")
        return f"{symbol}{amount:.2f}"
    
    @staticmethod
    def _format_date(date_str: Optional[str] = None) -> str:
        """Format date for display"""
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.strftime("%B %d, %Y")
            except:
                pass
        return datetime.utcnow().strftime("%B %d, %Y")
    
    @staticmethod
    async def send_payment_success_email(
        to_email: str,
        customer_name: Optional[str] = None,
        amount: int = 0,
        currency: str = "usd",
        plan_type: str = "monthly",
        subscription_id: Optional[str] = None,
        invoice_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send payment success confirmation email
        
        Args:
            to_email: Recipient email address
            customer_name: Customer's name (optional)
            amount: Amount paid in cents
            currency: Currency code (default: usd)
            plan_type: Subscription plan type (monthly/yearly)
            subscription_id: Stripe subscription ID
            invoice_id: Stripe invoice ID
        
        Returns:
            Dict with success status and message/error
        """
        if not EmailService.is_available():
            logger.warning("Email service not available, skipping payment success email")
            return {"success": False, "error": "Email service not configured"}
        
        try:
            formatted_amount = EmailService._format_amount(amount, currency)
            formatted_date = EmailService._format_date()
            greeting = f"Hi {customer_name}," if customer_name else "Hi there,"
            
            # Create beautiful HTML email
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #10b981; font-size: 28px; margin: 0;">✨ Payment Successful!</h1>
        </div>
        
        <!-- Main Card -->
        <div style="background-color: #ffffff; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin-top: 0;">
                {greeting}
            </p>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                Thank you for subscribing to Drawtopia! Your payment has been processed successfully.
            </p>
            
            <!-- Payment Details -->
            <div style="background-color: #f0fdf4; border-radius: 12px; padding: 24px; margin: 24px 0;">
                <h3 style="color: #166534; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 16px 0;">
                    Payment Details
                </h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Plan</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            Premium ({plan_type.capitalize()})
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Amount</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {formatted_amount}
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Date</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {formatted_date}
                        </td>
                    </tr>
                    {f'''<tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Invoice ID</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {invoice_id[:20]}...
                        </td>
                    </tr>''' if invoice_id else ''}
                </table>
            </div>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                You now have access to all premium features including unlimited story generation, 
                advanced AI art styles, and priority support!
            </p>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{FRONTEND_URL}/dashboard" 
                   style="display: inline-block; background-color: #10b981; color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 32px; border-radius: 8px;">
                    Go to Dashboard →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; margin-top: 32px; color: #9ca3af; font-size: 14px;">
            <p style="margin: 0 0 8px 0;">Need help? Contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color: #10b981;">{SUPPORT_EMAIL}</a></p>
            <p style="margin: 0;">© {datetime.utcnow().year} Drawtopia. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email via Resend
            response = resend.Emails.send({
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "✨ Payment Successful - Welcome to Drawtopia Premium!",
                "html": html_content
            })
            
            logger.info(f"Payment success email sent to {to_email}")
            return {"success": True, "message": "Payment success email sent", "id": response.get("id")}
            
        except Exception as e:
            logger.error(f"Failed to send payment success email to {to_email}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_payment_failed_email(
        to_email: str,
        customer_name: Optional[str] = None,
        amount: int = 0,
        currency: str = "usd",
        failure_reason: Optional[str] = None,
        next_retry_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send payment failure notification email
        
        Args:
            to_email: Recipient email address
            customer_name: Customer's name (optional)
            amount: Amount that failed in cents
            currency: Currency code
            failure_reason: Reason for payment failure
            next_retry_date: Date of next retry attempt
        
        Returns:
            Dict with success status and message/error
        """
        if not EmailService.is_available():
            logger.warning("Email service not available, skipping payment failed email")
            return {"success": False, "error": "Email service not configured"}
        
        try:
            formatted_amount = EmailService._format_amount(amount, currency)
            formatted_date = EmailService._format_date()
            greeting = f"Hi {customer_name}," if customer_name else "Hi there,"
            
            failure_message = failure_reason or "Your card was declined or there were insufficient funds."
            
            # Create HTML email for payment failure
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #ef4444; font-size: 28px; margin: 0;">⚠️ Payment Failed</h1>
        </div>
        
        <!-- Main Card -->
        <div style="background-color: #ffffff; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin-top: 0;">
                {greeting}
            </p>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                We were unable to process your payment for your Drawtopia subscription. 
                Don't worry - your access is still active while we retry.
            </p>
            
            <!-- Payment Details -->
            <div style="background-color: #fef2f2; border-radius: 12px; padding: 24px; margin: 24px 0; border-left: 4px solid #ef4444;">
                <h3 style="color: #991b1b; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 16px 0;">
                    Payment Details
                </h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Amount</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {formatted_amount}
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Date</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {formatted_date}
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Reason</td>
                        <td style="color: #ef4444; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {failure_message}
                        </td>
                    </tr>
                </table>
            </div>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                <strong>What you can do:</strong>
            </p>
            <ul style="color: #374151; font-size: 16px; line-height: 1.8; padding-left: 20px;">
                <li>Update your payment method in your account settings</li>
                <li>Ensure your card has sufficient funds</li>
                <li>Check if your card is not expired</li>
                <li>Contact your bank if the issue persists</li>
            </ul>
            
            {f'''<p style="color: #6b7280; font-size: 14px; line-height: 1.6;">
                We will automatically retry the payment on <strong>{next_retry_date}</strong>.
            </p>''' if next_retry_date else ''}
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{FRONTEND_URL}/account" 
                   style="display: inline-block; background-color: #ef4444; color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 32px; border-radius: 8px;">
                    Update Payment Method →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; margin-top: 32px; color: #9ca3af; font-size: 14px;">
            <p style="margin: 0 0 8px 0;">Need help? Contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color: #ef4444;">{SUPPORT_EMAIL}</a></p>
            <p style="margin: 0;">© {datetime.utcnow().year} Drawtopia. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email via Resend
            response = resend.Emails.send({
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "⚠️ Action Required: Payment Failed for Your Drawtopia Subscription",
                "html": html_content
            })
            
            logger.info(f"Payment failed email sent to {to_email}")
            return {"success": True, "message": "Payment failed email sent", "id": response.get("id")}
            
        except Exception as e:
            logger.error(f"Failed to send payment failed email to {to_email}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_subscription_cancelled_email(
        to_email: str,
        customer_name: Optional[str] = None,
        plan_type: str = "monthly",
        end_date: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send subscription cancellation confirmation email
        
        Args:
            to_email: Recipient email address
            customer_name: Customer's name (optional)
            plan_type: The plan that was cancelled
            end_date: When the subscription access ends
            reason: Cancellation reason (optional)
        
        Returns:
            Dict with success status and message/error
        """
        if not EmailService.is_available():
            logger.warning("Email service not available, skipping cancellation email")
            return {"success": False, "error": "Email service not configured"}
        
        try:
            formatted_end_date = EmailService._format_date(end_date) if end_date else "immediately"
            greeting = f"Hi {customer_name}," if customer_name else "Hi there,"
            
            # Create HTML email for cancellation
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #6366f1; font-size: 28px; margin: 0;">Subscription Cancelled</h1>
        </div>
        
        <!-- Main Card -->
        <div style="background-color: #ffffff; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <p style="color: #374151; font-size: 16px; line-height: 1.6; margin-top: 0;">
                {greeting}
            </p>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                Your Drawtopia Premium subscription has been cancelled as requested. 
                We're sorry to see you go!
            </p>
            
            <!-- Cancellation Details -->
            <div style="background-color: #eef2ff; border-radius: 12px; padding: 24px; margin: 24px 0;">
                <h3 style="color: #3730a3; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 16px 0;">
                    Cancellation Details
                </h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Plan Cancelled</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            Premium ({plan_type.capitalize()})
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Status</td>
                        <td style="color: #ef4444; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            Cancelled
                        </td>
                    </tr>
                    <tr>
                        <td style="color: #6b7280; font-size: 14px; padding: 8px 0;">Access Until</td>
                        <td style="color: #111827; font-size: 14px; padding: 8px 0; text-align: right; font-weight: 600;">
                            {formatted_end_date}
                        </td>
                    </tr>
                </table>
            </div>
            
            <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                <strong>What happens next:</strong>
            </p>
            <ul style="color: #374151; font-size: 16px; line-height: 1.8; padding-left: 20px;">
                <li>You'll retain access to premium features until {formatted_end_date}</li>
                <li>After that, your account will switch to the free plan</li>
                <li>Your stories and creations will always be saved</li>
                <li>You can resubscribe anytime to regain premium access</li>
            </ul>
            
            <!-- Feedback Section -->
            <div style="background-color: #fefce8; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: center;">
                <p style="color: #713f12; font-size: 14px; margin: 0;">
                    💡 We'd love to hear your feedback! Reply to this email and let us know how we can improve.
                </p>
            </div>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <p style="color: #6b7280; font-size: 14px; margin-bottom: 16px;">Changed your mind?</p>
                <a href="{FRONTEND_URL}/pricing" 
                   style="display: inline-block; background-color: #6366f1; color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 32px; border-radius: 8px;">
                    Resubscribe →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; margin-top: 32px; color: #9ca3af; font-size: 14px;">
            <p style="margin: 0 0 8px 0;">Questions? Contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color: #6366f1;">{SUPPORT_EMAIL}</a></p>
            <p style="margin: 0;">© {datetime.utcnow().year} Drawtopia. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email via Resend
            response = resend.Emails.send({
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "Your Drawtopia Premium Subscription Has Been Cancelled",
                "html": html_content
            })
            
            logger.info(f"Subscription cancelled email sent to {to_email}")
            return {"success": True, "message": "Cancellation email sent", "id": response.get("id")}
            
        except Exception as e:
            logger.error(f"Failed to send cancellation email to {to_email}: {e}")
            return {"success": False, "error": str(e)}


# Create a singleton instance for easy access
email_service = EmailService()

