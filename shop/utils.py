from decimal import Decimal
from shop.models import Cart, ShippingAddress
from constance import config
from django.utils.translation import gettext_lazy as _

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
    if created or not cart.total_price_field or not cart.total_items_field:
        cart.update_totals()
    return cart

def get_user_shipping_city(request):
    if request.user.is_authenticated:
        default_address = ShippingAddress.objects.filter(user=request.user, is_default=True).first()
        if default_address:
            return default_address.city
    return None
def get_cart_totals(cart_instance, user_location_city=None, user_country_code=None):
    if not cart_instance:
        return {
            'cart_total_price': Decimal('0.00'),
            'cart_total_items': 0,
            'shipping_cost': Decimal('0.00'),
            'grand_total': Decimal('0.00'),
            'shipping_status_message': _("Free"),
        }
    cart_instance.refresh_from_db()
    cart_instance.update_totals()
    cart_total_price = cart_instance.total_price_field
    cart_total_items = cart_instance.total_items_field

    shipping_cost = Decimal('0.00')
    shipping_status_message = _("Free")

    SHIPPING_THRESHOLD = Decimal(str(config.SHIPPING_THRESHOLD))
    SHIPPING_RATE_CAIRO = Decimal(str(config.SHIPPING_RATE_CAIRO))
    SHIPPING_RATE_OUTSIDE_CAIRO = Decimal(str(config.SHIPPING_RATE_OUTSIDE_CAIRO))

    base_shipping_rate = SHIPPING_RATE_CAIRO

    if user_location_city:
        # Match the exact choice value
        if user_location_city == 'INSIDE_CAIRO':
            base_shipping_rate = SHIPPING_RATE_CAIRO
        elif user_location_city == 'OUTSIDE_CAIRO':
            base_shipping_rate = SHIPPING_RATE_OUTSIDE_CAIRO
        else:
            # fallback if city value is unexpected
            base_shipping_rate = SHIPPING_RATE_CAIRO
    else:
        # No location info; fallback message
        shipping_status_message = _("Shipping (Estimate)")

    # Apply shipping cost if cart has items
    if cart_total_items > 0:
        if cart_total_price < SHIPPING_THRESHOLD:
            shipping_cost = base_shipping_rate
            if shipping_cost > 0 and shipping_status_message == _("Free"):
                shipping_status_message = ""
        else:
            shipping_cost = Decimal('0.00')
            shipping_status_message = _("Free (Threshold Met)")
    else:
        shipping_cost = Decimal('0.00')
        shipping_status_message = _("Free (No Items)")

    grand_total = cart_total_price + shipping_cost

    return {
        'cart_total_price': cart_total_price,
        'cart_total_items': cart_total_items,
        'shipping_cost': shipping_cost,
        'grand_total': grand_total,
        'shipping_status_message': shipping_status_message,
    }
