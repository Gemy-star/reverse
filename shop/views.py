from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.db.models import Q, Min, Max, Sum
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
from .forms import RegisterForm, LoginForm, ShippingAddressForm, PaymentForm
from .models import (
    Category, SubCategory, FitType, Brand, Color, Size,
    Product, ProductVariant, Cart, CartItem, Wishlist, WishlistItem, HomeSlider,
    Order, OrderItem, ShippingAddress, Payment, ReverseUser
)
from decimal import Decimal
import uuid
import logging

# Set up logger
logger = logging.getLogger(__name__)


# --- Helper Functions for Filtering/Sorting ---
def _filter_and_sort_products(products_queryset, request_get_params):
    """
    Applies common filtering and sorting logic to a product queryset.
    """
    subcategory_filter = request_get_params.get('subcategory')
    fit_type_filter = request_get_params.get('fit_type')
    brand_filter = request_get_params.get('brand')
    color_filter = request_get_params.get('color')
    size_filter = request_get_params.get('size')
    min_price_str = request_get_params.get('min_price')
    max_price_str = request_get_params.get('max_price')
    sort_by = request_get_params.get('sort', 'name')

    if subcategory_filter:
        products_queryset = products_queryset.filter(subcategory__slug=subcategory_filter)

    if fit_type_filter:
        products_queryset = products_queryset.filter(fit_type__slug=fit_type_filter)

    if brand_filter:
        products_queryset = products_queryset.filter(brand__slug=brand_filter)

    if color_filter:
        # Filter products by color of their available variants
        products_queryset = products_queryset.filter(productvariant__color__slug=color_filter).distinct()

    if size_filter:
        # Filter products by size of their available variants
        products_queryset = products_queryset.filter(productvariant__size__name__iexact=size_filter).distinct()

    # Price filtering
    if min_price_str:
        try:
            min_price = Decimal(min_price_str)
            products_queryset = products_queryset.filter(price__gte=min_price)
        except (ValueError, TypeError):
            pass

    if max_price_str:
        try:
            max_price = Decimal(max_price_str)
            products_queryset = products_queryset.filter(price__lte=max_price)
        except (ValueError, TypeError):
            pass

    # Sorting
    if sort_by == 'price_low':
        products_queryset = products_queryset.order_by('price')
    elif sort_by == 'price_high':
        products_queryset = products_queryset.order_by('-price')
    elif sort_by == 'newest':
        products_queryset = products_queryset.order_by('-created_at')
    elif sort_by == 'popular':
        # Consider adding a sales count or view count to Product model for true popularity
        products_queryset = products_queryset.order_by('-is_best_seller', '-created_at')
    else:  # Default or invalid sort
        products_queryset = products_queryset.order_by('name')

    return products_queryset.distinct()  # Use distinct to avoid duplicates from many-to-many filters


# --- Core Product & Category Views ---
def home(request):
    """Homepage view"""
    # Optimized initial product queries to reduce database hits
    # Use prefetch_related for images and select_related for foreign keys
    base_products = Product.objects.filter(is_active=True, is_available=True).prefetch_related('images') \
        .select_related('category', 'subcategory', 'brand')

    featured_products = base_products.filter(is_featured=True).distinct()[:8]
    new_arrivals = base_products.filter(is_new_arrival=True).distinct()[:8]
    best_sellers = base_products.filter(is_best_seller=True).distinct()[:8]
    all_products_recent = base_products.order_by('-created_at').distinct()[:8]  # Most recent based on creation
    sale_products = base_products.filter(is_on_sale=True).distinct()[:8]

    categories = Category.objects.filter(is_active=True).order_by('name')
    sliders = HomeSlider.objects.filter(is_active=True).order_by('order')

    products_in_wishlist_ids = []
    if request.user.is_authenticated:
        try:
            # Efficiently get wishlist product IDs for the logged-in user
            wishlist = Wishlist.objects.only('id').get(user=request.user)
            products_in_wishlist_ids = list(wishlist.items.values_list('product_id', flat=True))
        except Wishlist.DoesNotExist:
            pass  # No wishlist yet for this user

    context = {
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
        'sale_products': sale_products,
        'categories': categories,
        'sliders': sliders,
        'all_products': all_products_recent,  # Renamed for clarity
        'products_in_wishlist_ids': products_in_wishlist_ids,
    }

    return render(request, 'shop/home.html', context)

def category_detail(request, slug):
    """Category detail view - supports 'all' to show all products"""
    category = None
    subcategories = []
    # Start with active and available products
    products_queryset = Product.objects.filter(is_active=True, is_available=True) \
        .prefetch_related('images') \
        .select_related('category', 'subcategory', 'brand')

    if slug and slug != 'all':
        category = get_object_or_404(Category, slug=slug, is_active=True)
        subcategories = category.subcategories.filter(is_active=True).order_by('name')
        products_queryset = products_queryset.filter(category=category)
    elif not slug or slug == 'all':
        # If slug is 'all', products_queryset remains unfiltered by category
        pass
    else:
        messages.error(request, _("Invalid category selected."))
        return redirect('shop:home')  # Redirect to home or all products view

    # Apply filters and sorting using helper. Pass request object to helper for messages
    products_queryset = _filter_and_sort_products(products_queryset, request.GET)

    # Price range calculation for the *entire* filtered set, before pagination
    price_range = products_queryset.aggregate(Min('price'), Max('price'))

    # Pagination
    paginator = Paginator(products_queryset, 12)  # 12 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Filter options: Only show options relevant to products in the current category/filter set
    # Use correct related names for reverse relations
    fit_types = FitType.objects.filter(is_active=True, products__in=products_queryset).distinct().order_by('name')
    brands = Brand.objects.filter(is_active=True, products__in=products_queryset).distinct().order_by('name')
    colors = Color.objects.filter(is_active=True, productvariant__product__in=products_queryset).distinct().order_by('name')
    sizes = Size.objects.filter(is_active=True, productvariant__product__in=products_queryset).distinct().order_by('name')

    all_categories = Category.objects.filter(is_active=True).order_by('name')  # For navbar/sidebar

    products_in_wishlist_ids = []
    if request.user.is_authenticated:
        try:
            wishlist = Wishlist.objects.only('id').get(user=request.user)
            products_in_wishlist_ids = list(wishlist.items.values_list('product_id', flat=True))
        except Wishlist.DoesNotExist:
            pass

    context = {
        'category': category,
        'subcategories': subcategories,
        'products': page_obj,  # This is the paginated queryset
        'fit_types': fit_types,
        'brands': brands,
        'colors': colors,
        'sizes': sizes,
        'price_range': price_range,
        'categories': all_categories,
        'products_in_wishlist_ids': products_in_wishlist_ids,
        'current_filters': {
            'subcategory': request.GET.get('subcategory'),
            'fit_type': request.GET.get('fit_type'),
            'brand': request.GET.get('brand'),
            'color': request.GET.get('color'),
            'size': request.GET.get('size'),
            'min_price': request.GET.get('min_price'),
            'max_price': request.GET.get('max_price'),
            'sort': request.GET.get('sort', 'name'),
        }
    }

    return render(request, 'shop/category_detail.html', context)
def subcategory_detail(request, category_slug, slug):
    """Subcategory detail view"""
    category = get_object_or_404(Category, slug=category_slug, is_active=True)
    subcategory = get_object_or_404(SubCategory, slug=slug, category=category, is_active=True)

    products_queryset = Product.objects.filter(
        subcategory=subcategory,
        is_active=True,
        is_available=True
    ).prefetch_related('images') \
     .select_related('category', 'subcategory', 'brand')

    # Apply filters and sorting using helper
    products_queryset = _filter_and_sort_products(products_queryset, request.GET)

    # Price range calculation for current filtered set
    price_range = products_queryset.aggregate(Min('price'), Max('price'))

    # Pagination
    paginator = Paginator(products_queryset, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get filter options relevant to this subcategory's products
    fit_types = FitType.objects.filter(is_active=True, products__in=products_queryset).distinct().order_by('name')
    brands = Brand.objects.filter(is_active=True, products__in=products_queryset).distinct().order_by('name')
    colors = Color.objects.filter(is_active=True, productvariant__product__in=products_queryset).distinct().order_by('name')
    sizes = Size.objects.filter(is_active=True, productvariant__product__in=products_queryset).distinct().order_by('name')

    all_categories = Category.objects.filter(is_active=True).order_by('name')  # For sidebar navigation

    products_in_wishlist_ids = []
    if request.user.is_authenticated:
        try:
            wishlist = Wishlist.objects.only('id').get(user=request.user)
            products_in_wishlist_ids = list(wishlist.items.values_list('product_id', flat=True))
        except Wishlist.DoesNotExist:
            pass

    context = {
        'category': category,
        'subcategory': subcategory,
        'products': page_obj,
        'fit_types': fit_types,
        'brands': brands,
        'colors': colors,
        'sizes': sizes,
        'price_range': price_range,
        'categories': all_categories,
        'subcategories': category.subcategories.filter(is_active=True).order_by('name'),
        'products_in_wishlist_ids': products_in_wishlist_ids,
        'current_filters': {
            'subcategory': request.GET.get('subcategory'),  # This will be the current subcategory
            'fit_type': request.GET.get('fit_type'),
            'brand': request.GET.get('brand'),
            'color': request.GET.get('color'),
            'size': request.GET.get('size'),
            'min_price': request.GET.get('min_price'),
            'max_price': request.GET.get('max_price'),
            'sort': request.GET.get('sort', 'name'),
        }
    }

    return render(request, 'shop/subcategory_detail.html', context)
def product_detail(request, slug):
    """Product detail view"""
    product = get_object_or_404(
        Product.objects.select_related('category', 'subcategory', 'brand', 'fit_type')
        .prefetch_related('images', 'variants__color', 'variants__size'),
        slug=slug,
        is_active=True,
        is_available=True
    )

    related_products = Product.objects.filter(
        Q(category=product.category) | Q(subcategory=product.subcategory),
        is_active=True,
        is_available=True
    ).exclude(id=product.id).distinct().prefetch_related('images') \
                           .select_related('category', 'subcategory', 'brand')[:8]

    variants = product.variants.filter(is_available=True, stock_quantity__gt=0)

    available_colors = Color.objects.filter(
        productvariant__in=variants,
        is_active=True
    ).distinct().order_by('name')

    available_sizes = Size.objects.filter(
        productvariant__in=variants,
        is_active=True
    ).distinct().order_by('name')

    product_images = product.images.all().order_by('order')

    categories = Category.objects.filter(is_active=True).order_by('name')

    is_in_wishlist = False
    if request.user.is_authenticated:
        is_in_wishlist = WishlistItem.objects.filter(
            wishlist__user=request.user, product=product
        ).exists()

    context = {
        'product': product,
        'related_products': related_products,
        'variants': variants,
        'available_colors': available_colors,
        'available_sizes': available_sizes,
        'product_images': product_images,
        'categories': categories,
        'is_in_wishlist': is_in_wishlist,
    }

    return render(request, 'shop/product_detail.html', context)
# --- Search & API Endpoints ---
@require_http_methods(["GET"])
def search_products(request):
    """AJAX search for products"""
    query = request.GET.get('q', '').strip()  # .strip() to remove leading/trailing whitespace

    if not query or len(query) < 2:
        return JsonResponse({'products': []})

    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(category__name__icontains=query),
        is_active=True,
        is_available=True
    ).select_related('category', 'subcategory', 'brand').prefetch_related('images')[
               :10]  # Limit results for performance

    results = []
    for product in products:
        main_image = product.get_main_image()  # Assuming this method gets the main image object
        results.append({
            'id': product.id,
            'name': product.name,
            'price': str(product.get_price()),  # Ensure price is a string for JSON serialization
            'url': product.get_absolute_url(),
            'image': main_image.image.url if main_image and main_image.image else '',  # Check if image file exists
            'category': product.category.name if product.category else '',
            'brand': product.brand.name if product.brand else '',
        })

    return JsonResponse({'products': results})


@require_http_methods(["GET"])
def get_product_variants(request, product_id):
    """
    AJAX endpoint to get product variants based on color and size filters.
    Returns a list of matching variants with stock info.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
    except ValueError:
        return JsonResponse({'variants': [], 'message': _("Invalid product ID.")}, status=400)

    color_id = request.GET.get('color')
    size_id = request.GET.get('size')

    variants_queryset = ProductVariant.objects.filter(
        product=product,
        is_available=True,
        stock_quantity__gt=0  # Only show variants that are in stock
    ).select_related('color', 'size')  # Efficiently fetch related color and size objects

    if color_id:
        try:
            variants_queryset = variants_queryset.filter(color__id=int(color_id))
        except (ValueError, TypeError):
            # If color_id is invalid, return empty results (or all if that's desired behavior)
            return JsonResponse({'variants': [], 'message': _("Invalid color ID.")}, status=400)

    if size_id:
        try:
            variants_queryset = variants_queryset.filter(size__id=int(size_id))
        except (ValueError, TypeError):
            # If size_id is invalid, return empty results
            return JsonResponse({'variants': [], 'message': _("Invalid size ID.")}, status=400)

    results = []
    for variant in variants_queryset:
        results.append({
            'id': variant.id,
            'color_id': variant.color.id if variant.color else None,
            'color_name': variant.color.name if variant.color else _('N/A'),
            'size_id': variant.size.id if variant.size else None,
            'size_name': variant.size.name if variant.size else _('N/A'),
            'price': str(variant.get_price()),  # Ensure Decimal is serialized as string
            'stock': variant.stock_quantity,
            'sku': variant.sku,
        })

    return JsonResponse({'variants': results})



@require_GET
def get_cart_and_wishlist_counts(request):
    """
    Returns JSON with counts of items in cart and wishlist.
    Supports logged-in users and anonymous users (session).
    """
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        cart_count = cart.total_items if cart else 0
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        cart = Cart.objects.filter(session_key=session_key).first()
        cart_count = cart.total_items if cart else 0

    if request.user.is_authenticated:
        wishlist = Wishlist.objects.filter(user=request.user).first()
        wishlist_count = wishlist.items.count() if wishlist else 0
    else:
        wishlist_session = request.session.get('wishlist', [])
        wishlist_count = len(wishlist_session)

    return JsonResponse({
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
    })



# --- Account & Authentication ---
def account_view(request):
    """Handles user login and registration."""
    login_form = LoginForm(request, data=request.POST or None)
    register_form = RegisterForm(request.POST or None)

    if request.method == 'POST':
        if 'login' in request.POST:
            if login_form.is_valid():
                user = authenticate(
                    request,
                    username=login_form.cleaned_data['username'],
                    password=login_form.cleaned_data['password']
                )
                if user:
                    login(request, user)
                    messages.success(request, _(f"Welcome back, {user.username}!"))
                    # Merge anonymous cart if it exists
                    session_key = request.session.session_key
                    if session_key:
                        try:
                            # Use select_for_update to lock carts during merge
                            with transaction.atomic():
                                anon_cart = Cart.objects.select_for_update().get(session_key=session_key)
                                user_cart, _ = Cart.objects.select_for_update().get_or_create(user=user)

                                for item in anon_cart.items.all():
                                    existing_item, created = CartItem.objects.get_or_create(
                                        cart=user_cart,
                                        product_variant=item.product_variant,
                                        defaults={'quantity': item.quantity}
                                    )
                                    if not created:
                                        existing_item.quantity += item.quantity
                                        # Ensure quantity doesn't exceed stock if merging
                                        if existing_item.quantity > existing_item.product_variant.stock_quantity:
                                            existing_item.quantity = existing_item.product_variant.stock_quantity
                                            messages.warning(request,
                                                             _(f"Reduced quantity for {existing_item.product_variant.product.name} due to stock limits during merge."))
                                        existing_item.save()
                                    item.delete()  # Delete original anonymous cart item

                                anon_cart.delete()  # Delete anonymous cart after all items are merged/moved
                                user_cart.update_totals()  # Recalculate totals for the user's cart

                            request.session.pop('cart_count', None)  # Clear session cart count
                            request.session['cart_count'] = user_cart.total_items  # Update with merged count
                        except Cart.DoesNotExist:
                            pass  # No anonymous cart to merge
                        except Exception as e:
                            print(f"Error merging carts: {e}")
                            messages.error(request,
                                           _("An error occurred while merging your cart. Please check your cart."))

                    return redirect('shop:home')
                else:
                    messages.error(request, _("Invalid username or password."))
            else:
                messages.error(request, _("Please correct the errors in the login form."))

        elif 'register' in request.POST:
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)  # Automatically log in the new user
                messages.success(request, _(f"Account created successfully! Welcome, {user.username}!"))
                return redirect('shop:home')
            else:
                messages.error(request, _("Please correct the errors in the registration form."))

    return render(request, 'shop/account.html', {
        'login_form': login_form,
        'register_form': register_form
    })


@login_required
def user_logout(request):
    """Logs out the current user."""
    logout(request)
    messages.info(request, _("You have been logged out."))
    request.session.pop('cart_count', None)  # Clear cart count on logout
    request.session.pop('wishlist_count', None)  # Clear wishlist count on logout
    return redirect('shop:home')


# --- Wishlist Views ---
def wishlist_view(request):
    """Displays the user's wishlist with pagination."""
    products_qs = Product.objects.none()
    products_in_wishlist_ids = set()

    if request.user.is_authenticated:
        # Try to get wishlist and products in it
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            products_qs = Product.objects.filter(
                wishlistitem__wishlist=wishlist
            ).select_related(
                'category', 'subcategory', 'brand'
            ).prefetch_related(
                'images'
            ).order_by('name')
            # Get product IDs in wishlist from wishlist items
            products_in_wishlist_ids = set(
                request.user.wishlist_items.values_list('product_id', flat=True)
            )
        except Wishlist.DoesNotExist:
            products_qs = Product.objects.none()
            products_in_wishlist_ids = set()
    else:
        wishlist_session = request.session.get('wishlist', [])
        if wishlist_session:
            products_qs = Product.objects.filter(
                id__in=wishlist_session
            ).select_related(
                'category', 'subcategory', 'brand'
            ).prefetch_related(
                'images'
            ).order_by('name')
            products_in_wishlist_ids = set(wishlist_session)
        else:
            products_qs = Product.objects.none()
            products_in_wishlist_ids = set()

    # Pagination: 8 products per page
    paginator = Paginator(products_qs, 8)
    page = request.GET.get('page', 1)

    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    # Update wishlist count in session
    request.session['wishlist_count'] = products_qs.count()

    context = {
        'products': products,
        'products_in_wishlist_ids': products_in_wishlist_ids,
    }

    return render(request, 'shop/wishlist_view.html', context)

@require_POST
def add_to_cart(request):
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST

        product_variant_id = data.get('product_variant_id')
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': _('Invalid data provided.')}, status=400)

    product_variant = None
    product = None

    if product_variant_id:
        try:
            product_variant = ProductVariant.objects.get(id=product_variant_id, is_available=True)
            product = product_variant.product
        except ProductVariant.DoesNotExist:
            return JsonResponse({'success': False, 'message': _('Product variant not found or not available.')}, status=404)
    elif product_id:
        try:
            product = Product.objects.get(id=product_id, is_active=True, is_available=True)
            product_variant = ProductVariant.objects.filter(
                product=product,
                is_available=True,
                stock_quantity__gt=0
            ).order_by('pk').first()
            if not product_variant:
                return JsonResponse({'success': False, 'message': _(f'No available variants for {product.name} or out of stock.')}, status=400)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': _('Product not found or not available.')}, status=404)
    else:
        return JsonResponse({'success': False, 'message': _('Product or variant not provided.')}, status=400)

    if quantity <= 0:
        return JsonResponse({'success': False, 'message': _('Quantity must be at least 1.')}, status=400)

    if product_variant.stock_quantity < quantity:
        return JsonResponse({'success': False, 'message': _(
            f'Not enough stock for {product.name} ({product_variant.color.name if product_variant.color else "N/A"}, {product_variant.size.name if product_variant.size else "N/A"}). Available: {product_variant.stock_quantity}.')}, status=400)

    with transaction.atomic():
        if request.user.is_authenticated:
            cart, created = Cart.objects.select_for_update().get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key
            cart, created = Cart.objects.select_for_update().get_or_create(session_key=session_key)

        cart_item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            product_variant=product_variant,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

    request.session['cart_count'] = cart.total_items

    return JsonResponse({'success': True, 'message': _('Item added to cart successfully!'), 'cart_total_items': cart.total_items})


@require_POST
def add_to_wishlist(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': _('Invalid JSON.')}, status=400)

    product_id = data.get('product_id')
    if not product_id:
        return JsonResponse({'success': False, 'message': _('Product ID not provided.')}, status=400)

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': _('Product not found.')}, status=404)

    if request.user.is_authenticated:
        with transaction.atomic():
            wishlist, created = Wishlist.objects.select_for_update().get_or_create(user=request.user)
            wishlist_item, item_created = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
            if item_created:
                message = _('Item added to wishlist successfully!')
                status = 'added'
            else:
                message = _('Item is already in your wishlist.')
                status = 'exists'
            wishlist_count = wishlist.items.count()
    else:
        wishlist_session = request.session.get('wishlist', [])
        if str(product_id) in wishlist_session:
            message = _('Item is already in your wishlist.')
            status = 'exists'
        else:
            wishlist_session.append(str(product_id))
            request.session['wishlist'] = wishlist_session
            message = _('Item added to wishlist successfully!')
            status = 'added'
        wishlist_count = len(wishlist_session)

    request.session['wishlist_count'] = wishlist_count

    return JsonResponse({'success': True, 'message': message, 'status': status, 'wishlist_total_items': wishlist_count})


@require_POST
def remove_from_wishlist(request):
    from django.utils.translation import gettext as _
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': _('Invalid JSON.')}, status=400)

    product_id = data.get('product_id')
    if not product_id:
        return JsonResponse({'success': False, 'message': _('Product ID not provided.')}, status=400)

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': _('Product not found.')}, status=404)

    if request.user.is_authenticated:
        try:
            wishlist = Wishlist.objects.get(user=request.user)
        except Wishlist.DoesNotExist:
            return JsonResponse({'success': False, 'message': _('Wishlist not found for user.'), 'status': 'wishlist_missing'}, status=404)

        with transaction.atomic():
            deleted_count, _ = WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()

            if deleted_count > 0:
                wishlist_count = wishlist.items.count()
                request.session['wishlist_count'] = wishlist_count
                return JsonResponse({'success': True, 'message': _('Item removed successfully!'), 'wishlist_total_items': wishlist_count, 'status': 'removed'})
            else:
                return JsonResponse({'success': False, 'message': _('Item not found in wishlist.'), 'status': 'not_found'}, status=404)
    else:
        wishlist_session = request.session.get('wishlist', [])
        if str(product_id) in wishlist_session:
            wishlist_session.remove(str(product_id))
            request.session['wishlist'] = wishlist_session
            wishlist_count = len(wishlist_session)
            request.session['wishlist_count'] = wishlist_count
            return JsonResponse({'success': True, 'message': _('Item removed successfully!'), 'wishlist_total_items': wishlist_count, 'status': 'removed'})
        else:
            return JsonResponse({'success': False, 'message': _('Item not found in wishlist.'), 'status': 'not_found'}, status=404)


@require_POST
def remove_from_cart(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': _('Invalid JSON.')}, status=HttpResponseBadRequest.status_code)

    cart_item_id = data.get('cart_item_id')
    if not cart_item_id:
        return JsonResponse({'success': False, 'message': _('Cart item ID not provided.')}, status=HttpResponseBadRequest.status_code)

    try:
        cart_item_id = int(cart_item_id)
    except ValueError:
        return JsonResponse({'success': False, 'message': _('Invalid cart item ID format.')}, status=HttpResponseBadRequest.status_code)

    try:
        cart_item = get_object_or_404(CartItem.objects.select_related('cart'), id=cart_item_id)

        if request.user.is_authenticated:
            if cart_item.cart.user != request.user:
                return JsonResponse({'success': False, 'message': _('Unauthorized action.')}, status=HttpResponseForbidden.status_code)
        else:
            if cart_item.cart.session_key != request.session.session_key:
                return JsonResponse({'success': False, 'message': _('Unauthorized action.')}, status=HttpResponseForbidden.status_code)

        cart = cart_item.cart

        with transaction.atomic():
            cart_item.delete()

        request.session['cart_count'] = cart.total_items

        return JsonResponse({
            'success': True,
            'message': _('Item removed from cart.'),
            'cart_item_id': cart_item_id,
            'cart_total_items': cart.total_items,
            'cart_total_price': str(cart.total_price)
        })

    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': _('Cart item not found.')}, status=404)
    except Exception as e:
        logger.error(f"Error removing from cart: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': _(f'An unexpected error occurred: {str(e)}')}, status=500)

@require_POST
def update_cart_quantity(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': _('Invalid JSON.')}, status=HttpResponseBadRequest.status_code)

    cart_item_id = data.get('cart_item_id')
    new_quantity = data.get('quantity')

    if not cart_item_id or new_quantity is None:
        return JsonResponse({'success': False, 'message': _('Cart item ID or quantity not provided.')}, status=HttpResponseBadRequest.status_code)

    try:
        cart_item_id = int(cart_item_id)
        new_quantity = int(new_quantity)
    except ValueError:
        return JsonResponse({'success': False, 'message': _('Invalid quantity or item ID format.')}, status=HttpResponseBadRequest.status_code)

    try:
        cart_item = get_object_or_404(CartItem.objects.select_related('cart', 'product_variant'), id=cart_item_id)

        if request.user.is_authenticated:
            if cart_item.cart.user != request.user:
                return JsonResponse({'success': False, 'message': _('Unauthorized action.')}, status=HttpResponseForbidden.status_code)
        else:
            if cart_item.cart.session_key != request.session.session_key:
                return JsonResponse({'success': False, 'message': _('Unauthorized action.')}, status=HttpResponseForbidden.status_code)

        if new_quantity <= 0:
            with transaction.atomic():
                cart_item.delete()
            message = _('Item removed from cart.')
            status = 'removed'
            item_total_price = Decimal('0.00')
        else:
            if cart_item.product_variant.stock_quantity < new_quantity:
                new_quantity = cart_item.product_variant.stock_quantity

            with transaction.atomic():
                cart_item.quantity = new_quantity
                cart_item.save()

            message = _('Cart quantity updated.')
            status = 'updated'
            item_total_price = cart_item.get_total_price()

        request.session['cart_count'] = cart_item.cart.total_items

        return JsonResponse({
            'success': True,
            'message': message,
            'status': status,
            'cart_item_id': cart_item_id,
            'new_quantity': cart_item.quantity if status == 'updated' else 0,
            'item_total_price': str(item_total_price),
            'cart_total_items': cart_item.cart.total_items,
            'cart_total_price': str(cart_item.cart.total_price)
        })

    except CartItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': _('Cart item not found.')}, status=404)
    except Exception as e:
        print(f"Error updating cart quantity: {e}")
        return JsonResponse({'success': False, 'message': _(f'An unexpected error occurred: {str(e)}')}, status=500)

# --- Cart Views ---
def cart_view(request):
    cart_items_data = []
    total_cart_price = Decimal('0.00')
    cart = None

    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            pass
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
            except Cart.DoesNotExist:
                pass

    if cart:
        cart_items = cart.items.select_related(
            'product_variant__product',
            'product_variant__color',
            'product_variant__size'
        ).order_by('pk')

        for item in cart_items:
            current_stock = item.product_variant.stock_quantity if item.product_variant else 0
            display_quantity = min(item.quantity, current_stock)

            if item.quantity > current_stock:
                item.quantity = current_stock
                item.save()
                messages.warning(request,
                                 _(f"Quantity for {item.product_variant.product.name} was adjusted to {current_stock} due to limited stock."))
                if current_stock == 0:
                    item.delete()
                    messages.error(request,
                                   _(f"{item.product_variant.product.name} removed from cart as it is out of stock."))
                    continue

            item_total = item.get_total_price()
            total_cart_price += item_total
            cart_items_data.append({
                'id': item.id,
                'variant': item.product_variant,
                'quantity': item.quantity,
                'total': item_total,
                'stock_available': current_stock
            })

        cart.update_totals()
        total_cart_price = cart.total_price_field

    request.session['cart_count'] = cart.total_items_field if cart else 0

    return render(request, 'shop/cart_view.html', {
        'items': cart_items_data,
        'total': total_cart_price,
        'cart': cart
    })


# --- Checkout & Order Views ---
def get_cart_for_request(request):
    if request.user.is_authenticated:
        try:
            return Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return None
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        try:
            return Cart.objects.get(session_key=session_key)
        except Cart.DoesNotExist:
            return None
def checkout_view(request):
    cart = get_cart_for_request(request)

    if not cart or not cart.items.exists():
        messages.warning(request, _("Your cart is empty. Please add items before checking out."))
        return redirect('shop:cart_view')

    cart.update_totals()
    if cart.total_items == 0:
        messages.warning(request, _("Your cart is empty after stock adjustments. Please add items before checking out."))
        return redirect('shop:cart_view')

    initial_shipping_data = {}
    user_shipping_addresses = ShippingAddress.objects.none()
    if request.user.is_authenticated:
        user_shipping_addresses = ShippingAddress.objects.filter(user=request.user)
        if user_shipping_addresses.exists():
            default_address = user_shipping_addresses.filter(is_default=True).first() or user_shipping_addresses.order_by('-created_at').first()
            if default_address:
                initial_shipping_data = {
                    'full_name': default_address.full_name,
                    'address_line1': default_address.address_line1,
                    'address_line2': default_address.address_line2,
                    'city': default_address.city,
                    'state_province_region': default_address.state_province_region,
                    'postal_code': default_address.postal_code,
                    'country': default_address.country,
                    'phone_number': default_address.phone_number,
                }

    shipping_form = ShippingAddressForm(request.POST or None, initial=initial_shipping_data)
    payment_form = PaymentForm(request.POST or None)

    if request.method == 'POST':
        selected_address_id = request.POST.get('selected_address')
        if selected_address_id == 'new' or not user_shipping_addresses.exists():
            if shipping_form.is_valid() and payment_form.is_valid():
                return process_order(request, cart, shipping_form, payment_form)
            else:
                messages.error(request, _("Please correct the errors in your shipping and/or payment details."))
        else:
            if not request.user.is_authenticated:
                messages.error(request, _("You must be logged in to use an existing address."))
                return redirect('shop:checkout')
            try:
                selected_address = get_object_or_404(ShippingAddress, id=selected_address_id, user=request.user)
            except ShippingAddress.DoesNotExist:
                messages.error(request, _("Selected shipping address not found or does not belong to you."))
                return redirect('shop:checkout')

            if payment_form.is_valid():
                return process_order(request, cart, payment_form=payment_form, existing_address=selected_address)
            else:
                messages.error(request, _("Please correct the errors in your payment details."))

    context = {
        'cart': cart,
        'shipping_form': shipping_form,
        'payment_form': payment_form,
        'user_shipping_addresses': user_shipping_addresses,
    }
    return render(request, 'shop/checkout.html', context)
@transaction.atomic
def process_order(request, cart, shipping_form=None, payment_form=None, existing_address=None):
    try:
        if not shipping_form and not existing_address:
            messages.error(request, _("Shipping information is required."))
            return redirect('shop:checkout')

        if not payment_form:
            messages.error(request, _("Payment information is required."))
            return redirect('shop:checkout')

        # Create order first (without shipping address)
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=shipping_form.cleaned_data['full_name'] if shipping_form else existing_address.full_name,
            email=request.user.email if request.user.is_authenticated else '',  # Adjust as needed
            phone_number=shipping_form.cleaned_data['phone_number'] if shipping_form else existing_address.phone_number,
            subtotal=Decimal('0.00'),
            shipping_cost=Decimal('0.00'),  # Adjust if you calculate shipping cost
            grand_total=Decimal('0.00'),
            status='pending',
            payment_status='pending',
        )

        # Create or use existing shipping address, assign order, then save
        if existing_address:
            shipping_address = existing_address
            shipping_address.order = order
            shipping_address.save()
        else:
            shipping_address = shipping_form.save(commit=False)
            if hasattr(shipping_address, 'user') and request.user.is_authenticated:
                shipping_address.user = request.user  # If you have user field in ShippingAddress
            shipping_address.order = order
            shipping_address.save()

        # Update order with shipping address info if needed
        order.shipping_address = shipping_address
        order.save()

        # Create payment linked to order manually from payment_form.cleaned_data
        payment_data = payment_form.cleaned_data
        payment = Payment.objects.create(
            order=order,
            payment_method=payment_data.get('payment_method'),
            amount=Decimal('0.00'),  # Will update later
            transaction_id=f"TXN-{uuid.uuid4().hex[:10]}",
            is_success=False,
        )

        # Process cart items
        subtotal = Decimal('0.00')
        for cart_item in cart.items.select_related('product_variant').all():
            variant = cart_item.product_variant
            if variant.stock_quantity < cart_item.quantity:
                raise ValueError(
                    f"Not enough stock for {variant.product.name} "
                    f"({variant.color.name if variant.color else 'N/A'}, "
                    f"{variant.size.name if variant.size else 'N/A'}). "
                    f"Available: {variant.stock_quantity}, Requested: {cart_item.quantity}"
                )
            price = variant.get_price  # Access property, not method
            OrderItem.objects.create(
                order=order,
                product_variant=variant,
                quantity=cart_item.quantity,
                price_at_purchase=price
            )
            variant.stock_quantity -= cart_item.quantity
            variant.save()
            subtotal += price * cart_item.quantity

        # Update order totals
        order.subtotal = subtotal
        # Add shipping cost if you have it, e.g. order.shipping_cost = Decimal('10.00')
        order.grand_total = order.subtotal + order.shipping_cost
        order.save()

        # Update payment amount and mark as success (simulate)
        payment.amount = order.grand_total
        payment.is_success = True
        payment.save()

        # Update order status
        order.status = 'processing'
        order.payment_status = 'paid'
        order.save()

        # Clear cart
        cart.items.all().delete()
        cart.update_totals()
        if not request.user.is_authenticated:
            cart.delete()
        request.session['cart_count'] = 0

        messages.success(request, _(f"Your order {order.order_number} has been placed successfully!"))
        return redirect('shop:order_confirmation', order_number=order.order_number)

    except ValueError as e:
        messages.error(request, _(f"Order failed: {e}"))
        return redirect('shop:checkout')
    except Exception as e:
        logger.exception(f"Order processing failed for user {request.user}: {e}")
        messages.error(request, _(f"An unexpected error occurred during checkout: {e}"))
        return redirect('shop:checkout')
def order_confirmation(request, order_number):
    if request.user.is_authenticated:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)
    else:
        order = get_object_or_404(Order, order_number=order_number, user=None)
    order_items = order.items.select_related(
        'product_variant__product', 'product_variant__color', 'product_variant__size'
    ).all()
    return render(request, 'shop/order_confirmation.html', {'order': order, 'order_items': order_items})


def order_detail(request, order_number):
    if request.user.is_authenticated:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)
    else:
        order = get_object_or_404(Order, order_number=order_number, user=None)
    order_items = order.items.select_related(
        'product_variant__product', 'product_variant__color', 'product_variant__size'
    ).all()
    return render(request, 'shop/order_detail.html', {'order': order, 'order_items': order_items})


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'shop/order_history.html', {'orders': page_obj})