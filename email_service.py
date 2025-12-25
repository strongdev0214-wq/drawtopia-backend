"""
Email Service for Drawtopia

This module provides email functionality for:
- Payment success confirmation
- Payment failure notification
- Subscription activation confirmation
- Subscription cancellation confirmation
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional
from datetime import datetime
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Email Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
FROM_NAME = os.getenv("FROM_NAME", "Drawtopia")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Check if email service is available
EMAIL_SERVICE_AVAILABLE = bool(SMTP_USER and SMTP_PASSWORD and FROM_EMAIL)

if EMAIL_SERVICE_AVAILABLE:
    logger.info("✅ Email service initialized successfully")
else:
    logger.warning("⚠️ Email service not configured. Email notifications will be disabled.")


def _get_base_html_template() -> str:
    """Base HTML template with styling"""
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            padding: 32px 24px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
        }}
        .header .logo {{
            font-size: 40px;
            margin-bottom: 12px;
        }}
        .content {{
            padding: 32px 24px;
        }}
        .greeting {{
            font-size: 18px;
            color: #1f2937;
            margin-bottom: 20px;
        }}
        .message {{
            color: #4b5563;
            margin-bottom: 24px;
        }}
        .details-box {{
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .details-box h3 {{
            margin: 0 0 16px 0;
            color: #374151;
            font-size: 16px;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            color: #6b7280;
        }}
        .detail-value {{
            color: #1f2937;
            font-weight: 500;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
        }}
        .status-success {{
            background-color: #dcfce7;
            color: #166534;
        }}
        .status-failed {{
            background-color: #fee2e2;
            color: #991b1b;
        }}
        .status-cancelled {{
            background-color: #fef3c7;
            color: #92400e;
        }}
        .button {{
            display: inline-block;
            padding: 14px 28px;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: #ffffff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-top: 16px;
        }}
        .button:hover {{
            opacity: 0.9;
        }}
        .button-secondary {{
            background: #6b7280;
        }}
        .footer {{
            background-color: #f9fafb;
            padding: 24px;
            text-align: center;
            border-top: 1px solid #e5e7eb;
        }}
        .footer p {{
            margin: 0;
            color: #6b7280;
            font-size: 14px;
        }}
        .footer a {{
            color: #6366f1;
            text-decoration: none;
        }}
        .alert-box {{
            background-color: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
        }}
        .alert-box.warning {{
            background-color: #fffbeb;
            border-color: #fde68a;
        }}
        .alert-box p {{
            margin: 0;
            color: #991b1b;
        }}
        .alert-box.warning p {{
            color: #92400e;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


def _send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_text: Optional[str] = None
) -> bool:
    """
    Send an email using SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        plain_text: Optional plain text version
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not EMAIL_SERVICE_AVAILABLE:
        logger.warning(f"Email service not available. Skipping email to {to_email}")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr((FROM_NAME, FROM_EMAIL))
        message["To"] = to_email
        
        # Add plain text version
        if plain_text:
            part1 = MIMEText(plain_text, "plain")
            message.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_content, "html")
        message.attach(part2)
        
        # Create secure connection and send
        context = ssl.create_default_context()
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, message.as_string())
        
        logger.info(f"✅ Email sent successfully to {to_email}: {subject}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication error: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return False


async def send_payment_success_email(
    to_email: str,
    customer_name: Optional[str] = None,
    amount: float = 0,
    currency: str = "USD",
    plan_type: str = "monthly",
    transaction_id: Optional[str] = None,
    subscription_end_date: Optional[str] = None
) -> bool:
    """
    Send payment success confirmation email.
    
    Args:
        to_email: Customer email address
        customer_name: Customer name (optional)
        amount: Payment amount
        currency: Currency code
        plan_type: Subscription plan type (monthly/yearly)
        transaction_id: Stripe transaction ID
        subscription_end_date: When the subscription period ends
    
    Returns:
        True if email sent successfully
    """
    name = customer_name or "Valued Customer"
    formatted_amount = f"${amount:.2f}" if currency.upper() == "USD" else f"{amount:.2f} {currency.upper()}"
    plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
    
    content = f"""
        <div class="header">
            <div class="logo">✨</div>
            <h1>Payment Successful!</h1>
        </div>
        <div class="content">
            <p class="greeting">Hi {name},</p>
            <p class="message">
                Great news! Your payment has been processed successfully. Your Drawtopia subscription is now active!
            </p>
            
            <div class="details-box">
                <h3>Payment Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge status-success">Successful</span></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amount</span>
                    <span class="detail-value">{formatted_amount}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Plan</span>
                    <span class="detail-value">{plan_display} Subscription</span>
                </div>
                {"<div class='detail-row'><span class='detail-label'>Transaction ID</span><span class='detail-value'>" + transaction_id + "</span></div>" if transaction_id else ""}
                {"<div class='detail-row'><span class='detail-label'>Next Billing Date</span><span class='detail-value'>" + subscription_end_date + "</span></div>" if subscription_end_date else ""}
            </div>
            
            <p class="message">
                You now have full access to all premium features. Start creating amazing illustrated stories for your children!
            </p>
            
            <center>
                <a href="{FRONTEND_URL}/account" class="button">Go to Dashboard</a>
            </center>
        </div>
        <div class="footer">
            <p>Thank you for choosing Drawtopia! 📚✨</p>
            <p style="margin-top: 12px;">
                <a href="{FRONTEND_URL}">Visit Drawtopia</a> | 
                <a href="{FRONTEND_URL}/account">Manage Account</a>
            </p>
        </div>
    """
    
    html = _get_base_html_template().format(title="Payment Successful - Drawtopia", content=content)
    
    plain_text = f"""
Hi {name},

Great news! Your payment has been processed successfully.

Payment Details:
- Status: Successful
- Amount: {formatted_amount}
- Plan: {plan_display} Subscription
{f"- Transaction ID: {transaction_id}" if transaction_id else ""}
{f"- Next Billing Date: {subscription_end_date}" if subscription_end_date else ""}

You now have full access to all premium features. Start creating amazing illustrated stories for your children!

Visit your dashboard: {FRONTEND_URL}/account

Thank you for choosing Drawtopia!
"""
    
    return _send_email(to_email, "🎉 Payment Successful - Your Drawtopia Subscription is Active!", html, plain_text)


async def send_payment_failed_email(
    to_email: str,
    customer_name: Optional[str] = None,
    amount: float = 0,
    currency: str = "USD",
    plan_type: str = "monthly",
    failure_reason: Optional[str] = None,
    retry_url: Optional[str] = None
) -> bool:
    """
    Send payment failure notification email.
    
    Args:
        to_email: Customer email address
        customer_name: Customer name (optional)
        amount: Payment amount attempted
        currency: Currency code
        plan_type: Subscription plan type
        failure_reason: Reason for payment failure
        retry_url: URL to retry payment
    
    Returns:
        True if email sent successfully
    """
    name = customer_name or "Valued Customer"
    formatted_amount = f"${amount:.2f}" if currency.upper() == "USD" else f"{amount:.2f} {currency.upper()}"
    plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
    update_payment_url = retry_url or f"{FRONTEND_URL}/account"
    
    failure_message = failure_reason or "Your payment could not be processed"
    
    content = f"""
        <div class="header" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
            <div class="logo">⚠️</div>
            <h1>Payment Failed</h1>
        </div>
        <div class="content">
            <p class="greeting">Hi {name},</p>
            
            <div class="alert-box">
                <p><strong>Payment Issue:</strong> {failure_message}</p>
            </div>
            
            <p class="message">
                We were unable to process your payment for your Drawtopia subscription. 
                Please update your payment method to continue enjoying premium features.
            </p>
            
            <div class="details-box">
                <h3>Payment Attempt Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge status-failed">Failed</span></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Amount</span>
                    <span class="detail-value">{formatted_amount}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Plan</span>
                    <span class="detail-value">{plan_display} Subscription</span>
                </div>
            </div>
            
            <p class="message">
                <strong>What to do next:</strong>
            </p>
            <ul style="color: #4b5563;">
                <li>Check that your card details are correct</li>
                <li>Ensure your card has sufficient funds</li>
                <li>Contact your bank if the issue persists</li>
            </ul>
            
            <center>
                <a href="{update_payment_url}" class="button">Update Payment Method</a>
            </center>
        </div>
        <div class="footer">
            <p>Need help? Reply to this email or visit our support page.</p>
            <p style="margin-top: 12px;">
                <a href="{FRONTEND_URL}">Visit Drawtopia</a> | 
                <a href="{FRONTEND_URL}/account">Manage Account</a>
            </p>
        </div>
    """
    
    html = _get_base_html_template().format(title="Payment Failed - Drawtopia", content=content)
    
    plain_text = f"""
Hi {name},

We were unable to process your payment for your Drawtopia subscription.

Payment Issue: {failure_message}

Payment Attempt Details:
- Status: Failed
- Amount: {formatted_amount}
- Plan: {plan_display} Subscription

What to do next:
- Check that your card details are correct
- Ensure your card has sufficient funds
- Contact your bank if the issue persists

Update your payment method: {update_payment_url}

Need help? Reply to this email or visit our support page.
"""
    
    return _send_email(to_email, "⚠️ Payment Failed - Action Required for Your Drawtopia Subscription", html, plain_text)


async def send_subscription_activation_email(
    to_email: str,
    customer_name: Optional[str] = None,
    plan_type: str = "monthly",
    subscription_start_date: Optional[str] = None,
    subscription_end_date: Optional[str] = None
) -> bool:
    """
    Send subscription activation confirmation email.
    
    Args:
        to_email: Customer email address
        customer_name: Customer name (optional)
        plan_type: Subscription plan type
        subscription_start_date: When subscription started
        subscription_end_date: When subscription period ends
    
    Returns:
        True if email sent successfully
    """
    name = customer_name or "Valued Customer"
    plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
    start_date = subscription_start_date or datetime.utcnow().strftime("%B %d, %Y")
    
    content = f"""
        <div class="header">
            <div class="logo">🎉</div>
            <h1>Welcome to Drawtopia Premium!</h1>
        </div>
        <div class="content">
            <p class="greeting">Hi {name},</p>
            <p class="message">
                Your subscription has been activated successfully! You now have access to all premium features.
            </p>
            
            <div class="details-box">
                <h3>Subscription Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge status-success">Active</span></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Plan</span>
                    <span class="detail-value">{plan_display} Subscription</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Started On</span>
                    <span class="detail-value">{start_date}</span>
                </div>
                {"<div class='detail-row'><span class='detail-label'>Next Billing</span><span class='detail-value'>" + subscription_end_date + "</span></div>" if subscription_end_date else ""}
            </div>
            
            <p class="message"><strong>What you can do now:</strong></p>
            <ul style="color: #4b5563;">
                <li>Create unlimited illustrated stories</li>
                <li>Access all premium characters and themes</li>
                <li>Download high-quality PDFs</li>
                <li>Generate audio narration for your stories</li>
            </ul>
            
            <center>
                <a href="{FRONTEND_URL}/create" class="button">Create Your First Story</a>
            </center>
        </div>
        <div class="footer">
            <p>Thank you for joining Drawtopia Premium! 📚✨</p>
            <p style="margin-top: 12px;">
                <a href="{FRONTEND_URL}">Visit Drawtopia</a> | 
                <a href="{FRONTEND_URL}/account">Manage Subscription</a>
            </p>
        </div>
    """
    
    html = _get_base_html_template().format(title="Subscription Activated - Drawtopia", content=content)
    
    plain_text = f"""
Hi {name},

Your subscription has been activated successfully!

Subscription Details:
- Status: Active
- Plan: {plan_display} Subscription
- Started On: {start_date}
{f"- Next Billing: {subscription_end_date}" if subscription_end_date else ""}

What you can do now:
- Create unlimited illustrated stories
- Access all premium characters and themes
- Download high-quality PDFs
- Generate audio narration for your stories

Start creating: {FRONTEND_URL}/create

Thank you for joining Drawtopia Premium!
"""
    
    return _send_email(to_email, "🎉 Welcome to Drawtopia Premium - Your Subscription is Active!", html, plain_text)


async def send_subscription_cancellation_email(
    to_email: str,
    customer_name: Optional[str] = None,
    plan_type: str = "monthly",
    cancellation_date: Optional[str] = None,
    access_end_date: Optional[str] = None,
    reason: Optional[str] = None
) -> bool:
    """
    Send subscription cancellation confirmation email.
    
    Args:
        to_email: Customer email address
        customer_name: Customer name (optional)
        plan_type: Subscription plan type that was cancelled
        cancellation_date: When the cancellation was processed
        access_end_date: When access will end (end of billing period)
        reason: Optional cancellation reason
    
    Returns:
        True if email sent successfully
    """
    name = customer_name or "Valued Customer"
    plan_display = "Monthly" if plan_type == "monthly" else "Yearly"
    cancel_date = cancellation_date or datetime.utcnow().strftime("%B %d, %Y")
    
    content = f"""
        <div class="header" style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);">
            <div class="logo">📭</div>
            <h1>Subscription Cancelled</h1>
        </div>
        <div class="content">
            <p class="greeting">Hi {name},</p>
            <p class="message">
                We're sorry to see you go. Your Drawtopia subscription has been cancelled as requested.
            </p>
            
            <div class="details-box">
                <h3>Cancellation Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge status-cancelled">Cancelled</span></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Plan</span>
                    <span class="detail-value">{plan_display} Subscription</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Cancelled On</span>
                    <span class="detail-value">{cancel_date}</span>
                </div>
                {"<div class='detail-row'><span class='detail-label'>Access Until</span><span class='detail-value'>" + access_end_date + "</span></div>" if access_end_date else ""}
            </div>
            
            <div class="alert-box warning">
                <p>{"<strong>Note:</strong> You can still access premium features until " + access_end_date + "." if access_end_date else "<strong>Note:</strong> Your premium access has ended."}</p>
            </div>
            
            <p class="message">
                We'd love to have you back! If you change your mind, you can resubscribe anytime.
            </p>
            
            <center>
                <a href="{FRONTEND_URL}/pricing" class="button">Resubscribe</a>
                <a href="{FRONTEND_URL}/account" class="button button-secondary" style="margin-left: 12px;">View Account</a>
            </center>
        </div>
        <div class="footer">
            <p>Thank you for being a Drawtopia member. We hope to see you again soon! 👋</p>
            <p style="margin-top: 12px;">
                <a href="{FRONTEND_URL}">Visit Drawtopia</a>
            </p>
        </div>
    """
    
    html = _get_base_html_template().format(title="Subscription Cancelled - Drawtopia", content=content)
    
    plain_text = f"""
Hi {name},

We're sorry to see you go. Your Drawtopia subscription has been cancelled as requested.

Cancellation Details:
- Status: Cancelled
- Plan: {plan_display} Subscription
- Cancelled On: {cancel_date}
{f"- Access Until: {access_end_date}" if access_end_date else ""}

{"You can still access premium features until " + access_end_date + "." if access_end_date else "Your premium access has ended."}

We'd love to have you back! If you change your mind, you can resubscribe anytime at: {FRONTEND_URL}/pricing

Thank you for being a Drawtopia member. We hope to see you again soon!
"""
    
    return _send_email(to_email, "📭 Your Drawtopia Subscription Has Been Cancelled", html, plain_text)


# Utility function to get customer email from Stripe customer ID
async def get_customer_email_from_stripe(customer_id: str) -> Optional[str]:
    """
    Get customer email from Stripe using customer ID.
    
    Args:
        customer_id: Stripe customer ID
    
    Returns:
        Customer email or None
    """
    try:
        import stripe
        customer = stripe.Customer.retrieve(customer_id)
        return customer.get("email")
    except Exception as e:
        logger.error(f"Error retrieving customer email from Stripe: {e}")
        return None


# Utility function to get customer info from database
async def get_customer_info_from_db(supabase_client, customer_id: str = None, user_id: str = None):
    """
    Get customer info from database.
    
    Args:
        supabase_client: Supabase client instance
        customer_id: Stripe customer ID
        user_id: User ID
    
    Returns:
        Dict with customer info (email, name) or None
    """
    try:
        if not supabase_client:
            return None
        
        query = supabase_client.table("users").select("email, full_name, username")
        
        if user_id:
            query = query.eq("id", user_id)
        elif customer_id:
            query = query.eq("stripe_customer_id", customer_id)
        else:
            return None
        
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            user = result.data[0]
            return {
                "email": user.get("email"),
                "name": user.get("full_name") or user.get("username")
            }
        
        return None
    except Exception as e:
        logger.error(f"Error retrieving customer info from database: {e}")
        return None

