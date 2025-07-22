from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from shop.models import ProductVariant, Cart, CartItem, Product, Wishlist, WishlistItem

def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        _, created = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
        wishlist_count = wishlist.items.count()
        request.session['wishlist_count'] = wishlist_count
    else:
        wishlist = request.session.get('wishlist', [])
        product_id_str = str(product_id)
        if product_id_str not in wishlist:
            wishlist.append(product_id_str)
            request.session['wishlist'] = wishlist
            request.session.modified = True
            created = True
        else:
            created = False
        wishlist_count = len(wishlist)
        request.session['wishlist_count'] = wishlist_count

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "action": "added" if created else "exists",
            "product_id": product_id,
            "wishlist_count": wishlist_count,
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
        cart_count = cart.items.aggregate(total=models.Sum('quantity'))['total'] or 0
        request.session['cart_count'] = cart_count
    else:
        cart = request.session.get('cart', {})
        variant_id_str = str(variant_id)
        cart[variant_id_str] = cart.get(variant_id_str, 0) + 1
        request.session['cart'] = cart
        request.session.modified = True
        created = True
        cart_count = sum(cart.values())
        request.session['cart_count'] = cart_count

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "action": "added" if created else "updated",
            "variant_id": variant_id,
            "cart_count": cart_count,
        })

    return redirect('cart_view')
def cart_view(request):
    items = []
    total = 0

    if request.user.is_authenticated:
        cart = getattr(request.user, 'cart', None)
        if cart:
            cart_items = cart.items.select_related(
                'product_variant__product',
                'product_variant__color',
                'product_variant__size'
            )
            for item in cart_items:
                item_total = item.get_total_price()
                total += item_total
                items.append({
                    'variant': item.product_variant,
                    'quantity': item.quantity,
                    'total': item_total
                })
    else:
        cart_data = request.session.get('cart', {})
        for variant_id, quantity in cart_data.items():
            variant = get_object_or_404(ProductVariant, id=variant_id)
            item_total = variant.get_price * quantity
            total += item_total
            items.append({
                'variant': variant,
                'quantity': quantity,
                'total': item_total
            })

    return render(request, 'shop/cart_view.html', {
        'items': items,
        'total': total
    })


def remove_from_cart(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)

    if request.user.is_authenticated:
        cart = getattr(request.user, 'cart', None)
        if cart:
            CartItem.objects.filter(cart=cart, product_variant=variant).delete()
    else:
        cart = request.session.get('cart', {})
        if str(variant_id) in cart:
            del cart[str(variant_id)]
            request.session['cart'] = cart
            request.session.modified = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Optional: return updated counts if needed
        return JsonResponse({"status": "success", "removed": True})

    return redirect("cart_view")