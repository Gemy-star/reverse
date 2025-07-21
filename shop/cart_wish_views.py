from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from shop.models import ProductVariant, Cart, CartItem, Product, Wishlist, WishlistItem

# --- Add to Wishlist ---
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        _, created = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
    else:
        wishlist = request.session.get('wishlist', [])
        if product_id not in wishlist:
            wishlist.append(product_id)
            request.session['wishlist'] = wishlist
            request.session.modified = True
        created = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "action": "added" if created else "exists",
            "product_id": product_id
        })

    return redirect('wishlist_view')

# --- Wishlist View ---
def wishlist_view(request):
    products = []

    if request.user.is_authenticated:
        wishlist = getattr(request.user, 'wishlist', None)
        if wishlist:
            products = [item.product for item in wishlist.items.select_related('product')]
    else:
        wishlist_ids = request.session.get('wishlist', [])
        products = Product.objects.filter(id__in=wishlist_ids)

    return render(request, 'shop/wishlist_view.html', {'products': products})


# --- Add to Cart ---
def add_to_cart(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product_variant=variant)
        if not created:
            cart_item.quantity += 1
            cart_item.save()
    else:
        cart = request.session.get('cart', {})
        cart[str(variant_id)] = cart.get(str(variant_id), 0) + 1
        request.session['cart'] = cart
        request.session.modified = True
        created = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "action": "added" if created else "updated",
            "variant_id": variant_id
        })

    return redirect('cart_view')


# --- Cart View ---
def cart_view(request):
    items = []
    total = 0

    if request.user.is_authenticated:
        cart = getattr(request.user, 'cart', None)
        if cart:
            items = cart.items.select_related(
                'product_variant__product',
                'product_variant__color',
                'product_variant__size'
            )
            total = cart.total_price
    else:
        cart = request.session.get('cart', {})
        for variant_id, quantity in cart.items():
            variant = get_object_or_404(ProductVariant, id=variant_id)
            total += variant.get_price * quantity
            items.append({
                'variant': variant,
                'quantity': quantity,
                'total': variant.get_price * quantity
            })

    return render(request, 'shop/cart_view.html', {'items': items, 'total': total})
