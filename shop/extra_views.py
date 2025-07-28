from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from shop.models import ProductVariant, CartItem
from .utils import get_or_create_cart  # assuming your helper is in cart_utils.py
from django.utils.translation import gettext_lazy as _

def buy_now_view(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    if variant.stock_quantity < 1:
        messages.error(request, _("This product is currently out of stock."))
        return redirect('shop:product_detail', slug=variant.product.slug)
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_variant=variant,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity = 1
        cart_item.save()

    cart.update_totals()

    return redirect('shop:checkout')