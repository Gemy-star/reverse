"""
Django signals for automated email sending
File: shop/signals.py
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from shop.email import (
    send_order_confirmation_email,
    send_order_status_update_email,
    send_customer_welcome_email,
    send_admin_new_order_notification,
)

from shop.models import (
    ProductVariant, Cart, CartItem, Wishlist, Product, WishlistItem, Order, ReverseUser
)

logger = logging.getLogger(__name__)


# -------------------------------
# Order Related Signals
# -------------------------------

@receiver(pre_save, sender=Order)
def handle_order_status_change(sender, instance, **kwargs):
    """
    Detect status changes before saving (store old_status temporarily).
    """
    if instance.pk:
        try:
            original = Order.objects.get(pk=instance.pk)
            if original.status != instance.status:
                instance._old_status = original.status
        except Order.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=Order)
def handle_order_post_save(sender, instance, created, **kwargs):
    """
    Handle order creation and status update in a single signal.
    """
    if created:
        logger.info(f"New order created: {instance.order_number}")

        # Send confirmation email
        try:
            if send_order_confirmation_email(instance):
                logger.info(f"Order confirmation email sent for {instance.order_number}")
            else:
                logger.error(f"Failed to send confirmation email for {instance.order_number}")
        except Exception:
            logger.exception(f"Error sending confirmation email for {instance.order_number}")

        # Send admin notification
        try:
            if send_admin_new_order_notification(instance):
                logger.info(f"Admin notification sent for {instance.order_number}")
            else:
                logger.error(f"Failed to send admin notification for {instance.order_number}")
        except Exception:
            logger.exception(f"Error sending admin notification for {instance.order_number}")

    # Handle status updates
    elif hasattr(instance, "_old_status") and instance._old_status:
        old_status = instance._old_status
        new_status = instance.status
        try:
            if send_order_status_update_email(instance, old_status, new_status):
                logger.info(f"Status update email sent for order {instance.order_number}")
            else:
                logger.error(f"Failed to send status update email for {instance.order_number}")
        except Exception:
            logger.exception(f"Error sending status update email for {instance.order_number}")
        finally:
            delattr(instance, "_old_status")

    # Debug logging
    if settings.DEBUG:
        if created:
            logger.debug(f"DEBUG: New order signal fired for {instance.order_number}")
        else:
            logger.debug(f"DEBUG: Order update signal fired for {instance.order_number}")


# -------------------------------
# User Related Signals
# -------------------------------

@receiver(post_save, sender=ReverseUser)
def handle_user_registration(sender, instance, created, **kwargs):
    """
    Send welcome email for new customers.
    """
    if created and getattr(instance, "is_customer", False):
        logger.info(f"New customer registered: {instance.email}")
        try:
            if send_customer_welcome_email(instance):
                logger.info(f"Welcome email sent to {instance.email}")
            else:
                logger.error(f"Failed to send welcome email to {instance.email}")
        except Exception:
            logger.exception(f"Error sending welcome email to {instance.email}")


@receiver(user_logged_in)
def merge_session_cart_wishlist(sender, user, request, **kwargs):
    """
    Merge session cart & wishlist into DB on login.
    """
    # Cart
    session_cart = request.session.get("cart", {})
    if session_cart:
        cart, _ = Cart.objects.get_or_create(user=user)
        for variant_id, quantity in session_cart.items():
            variant = ProductVariant.objects.filter(id=variant_id).first()
            if variant:
                item, created = CartItem.objects.get_or_create(cart=cart, product_variant=variant)
                if not created:
                    item.quantity += quantity
                item.save()
        request.session.pop("cart", None)

    # Wishlist
    session_wishlist = request.session.get("wishlist", [])
    if session_wishlist:
        wishlist, _ = Wishlist.objects.get_or_create(user=user)
        for product_id in session_wishlist:
            product = Product.objects.filter(id=product_id).first()
            if product:
                WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
        request.session.pop("wishlist", None)
