# shop/context_processors.py (or wherever your processor is located)

from .models import Category, Wishlist, Cart, CartItem # Ensure CartItem is imported
import logging

logger = logging.getLogger(__name__)

def categories_processor(request):
    products_in_wishlist_ids = []
    # Initialize as an empty dictionary, not a list
    cart_items_data = {} 

    if request.user.is_authenticated:
        logger.debug("categories_processor: User is authenticated.")
        # Wishlist IDs
        try:
            wishlist = Wishlist.objects.only('id').get(user=request.user)
            products_in_wishlist_ids = list(wishlist.items.values_list('product_id', flat=True))
            logger.debug(f"categories_processor: Authenticated user wishlist IDs: {products_in_wishlist_ids}")
        except Wishlist.DoesNotExist:
            logger.debug("categories_processor: Authenticated user has no wishlist.")
            pass

        # Cart IDs and CartItem IDs for authenticated user
        try:
            cart = Cart.objects.get(user=request.user)
            # Fetch CartItems and build a dictionary: {product_id: {'cart_item_id': id, 'quantity': qty}}
            # We use product_variant.product.id to map to the top-level product,
            # which is typically what product listing pages display.
            for item in cart.items.select_related('product_variant__product').all():
                product_id = item.product_variant.product.id
                cart_items_data[product_id] = {
                    'cart_item_id': item.id,
                    'quantity': item.quantity
                }
            logger.debug(f"categories_processor: Authenticated user cart data: {cart_items_data}")
        except Cart.DoesNotExist:
            logger.debug("categories_processor: Authenticated user has no cart.")
            pass
    else:
        logger.debug("categories_processor: User is anonymous.")
        # For anonymous users, get cart IDs from session
        session_key = request.session.session_key
        if not session_key:
            # Create a session if it doesn't exist
            request.session.save()
            session_key = request.session.session_key
            logger.debug(f"categories_processor: New session created: {session_key}")

        try:
            cart = Cart.objects.get(session_key=session_key)
            # Fetch CartItems and build a dictionary: {product_id: {'cart_item_id': id, 'quantity': qty}}
            for item in cart.items.select_related('product_variant__product').all():
                product_id = item.product_variant.product.id
                cart_items_data[product_id] = {
                    'cart_item_id': item.id,
                    'quantity': item.quantity
                }
            logger.debug(f"categories_processor: Anonymous user cart data: {cart_items_data}")
        except Cart.DoesNotExist:
            logger.debug("categories_processor: Anonymous user has no cart.")
            pass

    return {
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'products_in_wishlist_ids': products_in_wishlist_ids,
        'cart_items_data': cart_items_data, # <--- Renamed and now a dictionary
    }