from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from .models import ProductVariant, CartItem, Cart  # Assuming Cart and CartItem are in .models
from .utils import get_or_create_cart  # Assuming this is a utility function you have


def buy_now_view(request):
    if request.method == 'POST':
        # Get product_id, color_id, and size_id from the POST request
        product_id = request.POST.get('product_id')
        color_id = request.POST.get('color_id')
        size_id = request.POST.get('size_id')

        if not product_id or not color_id or not size_id:
            messages.error(request, _("Please select a product, color, and size."))
            # You might need to redirect to a product detail page based on the product_id
            # For now, let's assume you have a way to get the product slug
            # You'll need to fetch the Product based on product_id to get its slug
            # This is a placeholder, adjust according to your Product model structure
            from .models import Product  # Import Product model
            product = get_object_or_404(Product, id=product_id)
            return redirect('shop:product_detail', slug=product.slug)

        # Find the specific ProductVariant based on product_id, color_id, and size_id
        try:
            variant = get_object_or_404(
                ProductVariant,
                product_id=product_id,
                color_id=color_id,
                size_id=size_id
            )
        except ProductVariant.DoesNotExist:
            messages.error(request, _("The selected product variant does not exist."))
            product = get_object_or_404(Product, id=product_id)
            return redirect('shop:product_detail', slug=product.slug)

        if variant.stock_quantity < 1:
            messages.error(request, _("This product is currently out of stock."))
            return redirect('shop:product_detail', slug=variant.product.slug)

        cart = get_or_create_cart(request)
        cart.items.all().delete()  # Clear existing cart items for "Buy Now"

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
    else:
        # If someone tries to access it via GET, redirect them or show an error
        messages.error(request, _("Invalid request for buy now."))
        # Redirect to a sensible default, maybe the shop home or product list
        return redirect('shop:product_list')  # Assuming you have a product_list URL