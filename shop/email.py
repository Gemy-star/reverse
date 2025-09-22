"""
Enhanced Email service functions for comprehensive email handling using SendGrid
File: main/utils.py
"""
import logging
import os
from django.template import loader, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from constance import config
import re

logger = logging.getLogger(__name__)


# -------------------------------
# Utility Functions
# -------------------------------

def get_config_value(key, default=None, fallback_env=None):
    """
    Get configuration value with multiple fallbacks
    """
    try:
        # Try constance config first
        if hasattr(config, key):
            value = getattr(config, key, None)
            if value:
                return value
    except:
        pass

    # Try Django settings
    try:
        if hasattr(settings, key):
            value = getattr(settings, key, None)
            if value:
                return value
    except:
        pass

    # Try environment variables
    if fallback_env:
        value = os.environ.get(fallback_env)
        if value:
            return value

    # Try direct environment with key name
    value = os.environ.get(key)
    if value:
        return value

    return default


def validate_email(email):
    """
    Validate email format
    """
    if not email:
        return False

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email.strip()) is not None


def get_fallback_content(subject, template_name):
    """
    Generate fallback content when templates are not available
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{subject}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #fff; color: #000; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .content {{ line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{subject}</h1>
            </div>
            <div class="content">
                <p>This email was sent from {get_config_value('SITE_NAME', 'Mnory Store')}.</p>
                <p>If you're seeing this message, it means our email template system encountered an issue.</p>
                <p>Please contact support if you need assistance.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    {subject}
    
    This email was sent from {get_config_value('SITE_NAME', 'Mnory Store')}.
    
    If you're seeing this message, it means our email template system encountered an issue.
    Please contact support if you need assistance.
    """

    return html_content, text_content


# -------------------------------
# Core SendGrid Email Function
# -------------------------------

def send_email_with_sendgrid(to_email, subject, template_name=None, context=None, html_content=None, text_content=None):
    """
    Send an email using the SendGrid API with comprehensive error handling and fallbacks.

    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Template name (without .html/.txt extension)
        context: Template context dict
        html_content: Direct HTML content (overrides template)
        text_content: Direct text content (overrides template)
    """
    logger.info(f"SendGrid: Starting email send to {to_email}")

    if not to_email or not subject:
        logger.error("SendGrid: Missing required parameters (to_email or subject)")
        return False

    try:
        # Validate email
        if not validate_email(to_email):
            logger.error(f"SendGrid: Invalid email format: {to_email}")
            return False

        # Get API key with multiple fallbacks
        api_key = get_config_value('SENDGRID_API_KEY', fallback_env='SENDGRID_API_KEY')
        if not api_key:
            logger.error("SendGrid: No API key found")
            return False

        # Get from email with multiple fallbacks
        from_email = get_config_value('ADMIN_EMAIL', fallback_env='ADMIN_EMAIL')
        if not from_email:
            from_email = get_config_value('FROM_EMAIL', fallback_env='FROM_EMAIL')
        if not from_email:
            from_email = get_config_value('DEFAULT_FROM_EMAIL', fallback_env='DEFAULT_FROM_EMAIL')

        if not from_email:
            logger.error("SendGrid: No from email configured")
            return False

        # Validate from email
        if not validate_email(from_email):
            logger.error(f"SendGrid: Invalid from email format: {from_email}")
            return False

        # Set default context
        if context is None:
            context = {}

        # Add default context variables
        context.update({
            'site_name': get_config_value('SITE_NAME', 'Mnory Store'),
            'site_url': get_config_value('SITE_URL', 'https://example.com'),
            'support_email': from_email,
            'year': 2024,
        })

        # Get email content
        final_html_content = html_content
        final_text_content = text_content

        if not final_html_content and template_name:
            # Try to load HTML template
            try:
                html_template_path = f"email/{template_name}.html"
                final_html_content = render_to_string(html_template_path, context)
                logger.info(f"SendGrid: HTML template loaded successfully")
            except TemplateDoesNotExist:
                logger.warning(f"SendGrid: HTML template not found: {html_template_path}")
                final_html_content, fallback_text = get_fallback_content(subject, template_name)
                if not final_text_content:
                    final_text_content = fallback_text
            except Exception as e:
                logger.error(f"SendGrid: Error loading HTML template: {str(e)}")
                final_html_content, fallback_text = get_fallback_content(subject, template_name)
                if not final_text_content:
                    final_text_content = fallback_text

        if not final_text_content and template_name:
            # Try to load text template
            try:
                text_template_path = f"email/{template_name}.txt"
                final_text_content = render_to_string(text_template_path, context)
                logger.info(f"SendGrid: Text template loaded successfully")
            except TemplateDoesNotExist:
                logger.info(f"SendGrid: Text template not found, generating from HTML or using fallback")
                if not final_text_content:
                    final_text_content = f"{subject}\n\nPlease enable HTML to view this email properly."
            except Exception as e:
                logger.warning(f"SendGrid: Error loading text template: {str(e)}")
                if not final_text_content:
                    final_text_content = f"{subject}\n\nPlease enable HTML to view this email properly."

        # Ensure we have content
        if not final_html_content:
            logger.warning("SendGrid: No HTML content available, using fallback")
            final_html_content, final_text_content = get_fallback_content(subject, template_name)

        if not final_text_content:
            final_text_content = f"{subject}\n\nPlease enable HTML to view this email properly."

        # Create SendGrid Mail object
        try:
            message = Mail(
                from_email=from_email,
                to_emails=to_email.strip(),
                subject=subject,
                html_content=final_html_content,
                plain_text_content=final_text_content
            )
            logger.info("SendGrid: Mail object created successfully")
        except Exception as e:
            logger.error(f"SendGrid: Failed to create Mail object: {str(e)}")
            return False

        # Send email
        try:
            sg = SendGridAPIClient(api_key=api_key)
            response = sg.send(message)

            logger.info(f"SendGrid: Response status: {response.status_code}")

            if response.status_code in [200, 201, 202]:
                logger.info(f"SendGrid: Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"SendGrid: Unexpected status code: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"SendGrid: API error: {str(e)}")

            # Log additional error details if available
            if hasattr(e, 'status_code'):
                logger.error(f"SendGrid: Status code: {e.status_code}")
            if hasattr(e, 'body'):
                logger.error(f"SendGrid: Error body: {e.body}")

            return False

    except Exception as e:
        logger.exception(f"SendGrid: Unexpected error: {str(e)}")
        return False


# -------------------------------
# Order Email Functions
# -------------------------------

def send_order_confirmation_email(order):
    """Send order confirmation email to customer"""
    logger.info(f"Sending order confirmation for order: {order.order_number}")

    try:
        context = {
            'order': order,
            'customer_name': order.full_name,
            'order_number': order.order_number,
            'order_items': order.items.all(),
            'subtotal': order.subtotal,
            'shipping_cost': order.shipping_cost,
            'grand_total': order.grand_total,
            'shipping_address': getattr(order, 'shipping_address', None),
            'order_date': order.created_at,
        }

        subject = f"Order Confirmation - #{order.order_number}"

        return send_email_with_sendgrid(
            to_email=order.email,
            subject=subject,
            template_name='order_confirmation',
            context=context
        )

    except Exception as e:
        logger.exception(f"Error in send_order_confirmation_email: {str(e)}")
        return False


def send_order_status_update_email(order, old_status, new_status):
    """Send order status update email to customer"""
    logger.info(f"Sending order status update for order: {order.order_number}")

    try:
        context = {
            'order': order,
            'customer_name': order.full_name,
            'order_number': order.order_number,
            'old_status': old_status,
            'new_status': new_status,
            'status_display': order.get_status_display(),
        }

        subject = f"Order Update - #{order.order_number}"

        return send_email_with_sendgrid(
            to_email=order.email,
            subject=subject,
            template_name='order_status_update',
            context=context
        )

    except Exception as e:
        logger.exception(f"Error in send_order_status_update_email: {str(e)}")
        return False


# -------------------------------
# Customer Email Functions
# -------------------------------

def send_customer_welcome_email(user):
    """Send welcome email to new customer"""
    logger.info(f"Sending welcome email to: {user.email}")

    try:
        context = {
            'user': user,
            'customer_name': user.get_full_name() or user.email.split('@')[0],
        }

        subject = f"Welcome to {get_config_value('SITE_NAME', 'Mnory Store')}!"

        return send_email_with_sendgrid(
            to_email=user.email,
            subject=subject,
            template_name='customer_welcome',
            context=context
        )

    except Exception as e:
        logger.exception(f"Error in send_customer_welcome_email: {str(e)}")
        return False


# -------------------------------
# Admin Notification Functions
# -------------------------------

def send_admin_new_order_notification(order):
    """Send new order notification to admin"""
    logger.info(f"Sending admin notification for order: {order.order_number}")

    try:
        admin_email = get_config_value('ADMIN_EMAIL', fallback_env='ADMIN_EMAIL')
        if not admin_email:
            logger.error("No admin email configured")
            return False

        context = {
            'order': order,
            'order_number': order.order_number,
            'customer_name': order.full_name,
            'customer_email': order.email,
            'order_items': order.items.all(),
            'grand_total': order.grand_total,
            'order_date': order.created_at,
        }

        subject = f"New Order - #{order.order_number}"

        return send_email_with_sendgrid(
            to_email=admin_email,
            subject=subject,
            template_name='admin_new_order',
            context=context
        )

    except Exception as e:
        logger.exception(f"Error in send_admin_new_order_notification: {str(e)}")
        return False


# -------------------------------
# Generic Email Function
# -------------------------------

def send_notification_email(to_email, subject, message, email_type='notification'):
    """
    Send a generic notification email
    """
    logger.info(f"Sending {email_type} email to: {to_email}")

    try:
        context = {
            'subject': subject,
            'message': message,
            'email_type': email_type,
        }

        return send_email_with_sendgrid(
            to_email=to_email,
            subject=subject,
            template_name='generic_notification',
            context=context
        )

    except Exception as e:
        logger.exception(f"Error in send_notification_email: {str(e)}")
        return False


# -------------------------------
# Test Functions
# -------------------------------

def test_email_configuration():
    """Test email configuration"""
    logger.info("Testing email configuration...")

    config_status = {
        'sendgrid_api_key': bool(get_config_value('SENDGRID_API_KEY', fallback_env='SENDGRID_API_KEY')),
        'admin_email': bool(get_config_value('ADMIN_EMAIL', fallback_env='ADMIN_EMAIL')),
        'site_name': bool(get_config_value('SITE_NAME')),
        'site_url': bool(get_config_value('SITE_URL')),
    }

    logger.info(f"Configuration status: {config_status}")
    return all(config_status.values())


def send_test_email(to_email=None):
    """Send a test email"""
    if not to_email:
        to_email = get_config_value('ADMIN_EMAIL', fallback_env='ADMIN_EMAIL')

    if not to_email:
        logger.error("No email address provided for test")
        return False

    context = {
        'test_message': 'This is a test email from the email system.',
        'timestamp': logger.info,
    }

    return send_email_with_sendgrid(
        to_email=to_email,
        subject="Test Email - Email System Check",
        template_name='test_email',
        context=context
    )