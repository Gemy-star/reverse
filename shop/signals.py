from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from shop.models import ProductVariant, Cart, CartItem, Wishlist, Product, WishlistItem


@receiver(user_logged_in)
def merge_session_cart_wishlist(sender, user, request, **kwargs):
    # Cart
    session_cart = request.session.get('cart', {})
    if session_cart:
        cart, _ = Cart.objects.get_or_create(user=user)
        for variant_id, quantity in session_cart.items():
            variant = ProductVariant.objects.filter(id=variant_id).first()
            if variant:
                item, created = CartItem.objects.get_or_create(cart=cart, product_variant=variant)
                if not created:
                    item.quantity += quantity
                item.save()
        request.session.pop('cart')

    # Wishlist
    session_wishlist = request.session.get('wishlist', [])
    if session_wishlist:
        wishlist, _ = Wishlist.objects.get_or_create(user=user)
        for product_id in session_wishlist:
            product = Product.objects.filter(id=product_id).first()
            if product:
                WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
        request.session.pop('wishlist')
