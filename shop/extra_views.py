from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from .models import ProductVariant, CartItem, Cart, Product  # Assuming Cart and CartItem are in .models
from .utils import get_or_create_cart  # Assuming this is a utility function you have
from django.db import transaction


def buy_now_view(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        color_id = request.POST.get('color_id')
        size_id = request.POST.get('size_id')
        quantity_str = request.POST.get('quantity', '1') # Get quantity from POST, default to '1'

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                messages.error(request, _("Quantity must be a positive number."))
                # Attempt to redirect back to the product detail page
                if product_id:
                    product = get_object_or_404(Product, id=product_id)
                    return redirect('shop:product_detail', slug=product.slug)
                return redirect('shop:product_list') # Fallback
        except ValueError:
            messages.error(request, _("Invalid quantity provided."))
            # Attempt to redirect back to the product detail page
            if product_id:
                product = get_object_or_404(Product, id=product_id)
                return redirect('shop:product_detail', slug=product.slug)
            return redirect('shop:product_list') # Fallback

        if not product_id or not color_id or not size_id:
            messages.error(request, _("Please select a product, color, and size."))
            # Attempt to redirect back to the product detail page if product_id is known
            if product_id:
                product = get_object_or_404(Product, id=product_id)
                return redirect('shop:product_detail', slug=product.slug)
            return redirect('shop:product_list') # Fallback if product_id is missing

        try:
            variant = get_object_or_404(
                ProductVariant,
                product_id=product_id,
                color_id=color_id,
                size_id=size_id
            )
        except ProductVariant.DoesNotExist:
            messages.error(request, _("The selected product variant does not exist."))
            # Redirect to the product detail if the variant is invalid
            product = get_object_or_404(Product, id=product_id)
            return redirect('shop:product_detail', slug=product.slug)

        # Check stock for the requested quantity
        if variant.stock_quantity < quantity:
            messages.error(request, _(f"Not enough stock. Only {variant.stock_quantity} available for {variant.product.name} ({variant.color.name}, {variant.size.name})."))
            return redirect('shop:product_detail', slug=variant.product.slug)

        cart = get_or_create_cart(request)

        # Use a transaction for critical cart operations
        with transaction.atomic():
            # IMPORTANT: Clear existing cart items for "Buy Now" flow.
            # This ensures only the 'buy now' item is in the cart for checkout.
            cart.items.all().delete()

            # Add the single item with the selected quantity
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_variant=variant,
                defaults={'quantity': quantity} # Set the quantity from the POST request
            )
            if not created:
                # If item already existed (shouldn't if cart was just cleared, but for robustness)
                cart_item.quantity = quantity
                cart_item.save()

            cart.update_totals() # Recalculate cart totals after modification

        messages.success(request, _(f"{quantity} x {variant.product.name} ({variant.color.name}, {variant.size.name}) added to cart for direct purchase."))
        return redirect('shop:checkout')
    else:
        messages.error(request, _("Invalid request for buy now."))
        return redirect('shop:product_list')