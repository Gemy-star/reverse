from datetime import datetime

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404
from django.db.models import Q, Min, Max
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
from .forms import RegisterForm, LoginForm, ShippingAddressForm, PaymentForm , CouponForm
from .models import (
    Category, SubCategory, FitType, Brand, Color, Size,
    Product, ProductVariant, Cart, CartItem, Wishlist, WishlistItem, HomeSlider,
    Order, OrderItem, ShippingAddress, Payment, Coupon
)
from .utils import get_or_create_cart, get_cart_totals , get_user_shipping_city

from decimal import Decimal
import logging
from django.utils.translation import gettext as _

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
    all_products_recent = base_products.order_by('-created_at').distinct()[:8]
    sale_products = base_products.filter(is_on_sale=True).distinct()[:8]

    categories = Category.objects.filter(is_active=True).order_by('name')
    sliders = HomeSlider.objects.filter(is_active=True).order_by('order')
    context = {
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'best_sellers': best_sellers,
        'sale_products': sale_products,
        'categories': categories,
        'sliders': sliders,
        'all_products': all_products_recent,  # Renamed for clarity
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
    from django.utils.translation import gettext as _
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
        try:
            wishlist = request.user.wishlist
            products_qs = Product.objects.filter(
                wishlistitem__wishlist=wishlist
            ).select_related(
                'category', 'subcategory', 'brand'
            ).prefetch_related('images').order_by('name')
            products_in_wishlist_ids = set(
                wishlist.items.values_list('product_id', flat=True)
            )
        except Wishlist.DoesNotExist:
            products_qs = Product.objects.none()
            products_in_wishlist_ids = set()
    else:
        wishlist_session = request.session.get('wishlist', [])
        if wishlist_session:
            products_qs = Product.objects.filter(id__in=wishlist_session).select_related(
                'category', 'subcategory', 'brand'
            ).prefetch_related('images').order_by('name')
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
    # Determine current language
    lang = getattr(request, 'LANGUAGE_CODE', 'en')

    # Parse incoming data
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        product_variant_id = data.get('product_variant_id')
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        message = 'Invalid data provided.' if lang == 'en' else 'بيانات غير صالحة.'
        return JsonResponse({'success': False, 'message': message}, status=400)

    # Fetch product and variant
    product_variant = None
    product = None
    if product_variant_id:
        try:
            product_variant = ProductVariant.objects.get(id=product_variant_id, is_available=True)
            product = product_variant.product
        except ProductVariant.DoesNotExist:
            message = 'Product variant not found or not available.' if lang == 'en' else 'النسخة المحددة من المنتج غير موجودة أو غير متوفرة.'
            return JsonResponse({'success': False, 'message': message}, status=404)
    elif product_id:
        try:
            product = Product.objects.get(id=product_id, is_active=True, is_available=True)
            product_variant = ProductVariant.objects.filter(
                product=product, is_available=True, stock_quantity__gt=0
            ).order_by('pk').first()
            if not product_variant:
                message = f'No available variants for {product.name} or out of stock.' if lang == 'en' else f'لا توجد نسخ متاحة لـ {product.name} أو نفدت الكمية.'
                return JsonResponse({'success': False, 'message': message}, status=400)
        except Product.DoesNotExist:
            message = 'Product not found or not available.' if lang == 'en' else 'المنتج غير موجود أو غير متوفر.'
            return JsonResponse({'success': False, 'message': message}, status=404)
    else:
        message = 'Product or variant not provided.' if lang == 'en' else 'لم يتم تقديم منتج أو نسخة.'
        return JsonResponse({'success': False, 'message': message}, status=400)

    # Validate quantity
    if quantity <= 0:
        message = 'Quantity must be at least 1.' if lang == 'en' else 'يجب أن تكون الكمية على الأقل 1.'
        return JsonResponse({'success': False, 'message': message}, status=400)

    # Check stock availability
    if product_variant.stock_quantity < quantity:
        message = (
            f'Not enough stock for {product.name} ({product_variant.color.name if product_variant.color else "N/A"}, '
            f'{product_variant.size.name if product_variant.size else "N/A"}). Available: {product_variant.stock_quantity}.'
        ) if lang == 'en' else (
            f'الكمية غير كافية للمنتج {product.name} ({product_variant.color.name if product_variant.color else "غير متوفر"}, '
            f'{product_variant.size.name if product_variant.size else "غير متوفر"}). المتوفر: {product_variant.stock_quantity}.'
        )
        return JsonResponse({'success': False, 'message': message}, status=400)

    # Atomic transaction to update cart
    with transaction.atomic():
        # Get or create cart
        if request.user.is_authenticated:
            cart, _ = Cart.objects.select_for_update().get_or_create(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key
            cart, _ = Cart.objects.select_for_update().get_or_create(session_key=session_key)

        # Add or update cart item
        cart_item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart,
            product_variant=product_variant,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        # Update session data
        request.session['cart_item_ids'] = list(cart.items.values_list('product_variant_id', flat=True))
        request.session['cart_count'] = cart.total_items

        message = 'Item added to cart successfully!' if lang == 'en' else 'تمت إضافة العنصر إلى السلة بنجاح!'
        return JsonResponse({'success': True, 'message': message, 'cart_total_items': cart.total_items})

@require_POST
def add_to_wishlist(request):
    lang = getattr(request, 'LANGUAGE_CODE', 'en')
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.' if lang == 'en' else 'نص غير صالح.'}, status=400)
        product_id = data.get('product_id')
        if not product_id:
            return JsonResponse({'success': False, 'message': 'Product ID not provided.' if lang == 'en' else 'معرف المنتج غير موجود.'}, status=400)
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found.' if lang == 'en' else 'المنتج غير موجود.'}, status=404)

        if request.user.is_authenticated:
            with transaction.atomic():
                wishlist, created = Wishlist.objects.select_for_update().get_or_create(user=request.user)
                wishlist_item, item_created = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
                if item_created:
                    message = 'Item added to wishlist successfully!' if lang == 'en' else 'تمت إضافة العنصر إلى قائمة الرغبات بنجاح!'
                    status = 'added'
                else:
                    message = 'Item is already in your wishlist.' if lang == 'en' else 'العنصر موجود بالفعل في قائمة رغباتك.'
                    status = 'exists'
                wishlist_count = wishlist.items.count()
        else:
            wishlist_session = request.session.get('wishlist', [])
            if str(product_id) in wishlist_session:
                message = 'Item is already in your wishlist.' if lang == 'en' else 'العنصر موجود بالفعل في قائمة رغباتك.'
                status = 'exists'
            else:
                wishlist_session.append(str(product_id))
                request.session['wishlist'] = wishlist_session
                message = 'Item added to wishlist successfully!' if lang == 'en' else 'تمت إضافة العنصر إلى قائمة الرغبات بنجاح!'
                status = 'added'
            wishlist_count = len(wishlist_session)

        request.session['wishlist_count'] = wishlist_count
        return JsonResponse({'success': True, 'message': message, 'status': status, 'wishlist_total_items': wishlist_count})
    except Exception:
        message = 'An error occurred.' if lang == 'en' else 'حدث خطأ.'
        return JsonResponse({'success': False, 'message': message}, status=500)

@require_POST
def remove_from_wishlist(request):
    lang = getattr(request, 'LANGUAGE_CODE', 'en')
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON.' if lang == 'en' else 'نص غير صالح.'}, status=400)
        product_id = data.get('product_id')
        if not product_id:
            return JsonResponse({'success': False, 'message': 'Product ID not provided.' if lang == 'en' else 'معرف المنتج غير موجود.'}, status=400)
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found.' if lang == 'en' else 'المنتج غير موجود.'}, status=404)

        if request.user.is_authenticated:
            try:
                wishlist = Wishlist.objects.get(user=request.user)
            except Wishlist.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Wishlist not found for user.', 'status': 'wishlist_missing'}, status=404)
            with transaction.atomic():
                deleted_count, _ = WishlistItem.objects.filter(wishlist=wishlist, product=product).delete()
                if deleted_count > 0:
                    wishlist_count = wishlist.items.count()
                    request.session['wishlist_count'] = wishlist_count
                    message = 'Item removed successfully!' if lang == 'en' else 'تمت إزالة العنصر بنجاح!'
                    return JsonResponse({'success': True, 'message': message, 'wishlist_total_items': wishlist_count, 'status': 'removed'})
                else:
                    message = 'Item not found in wishlist.' if lang == 'en' else 'العنصر غير موجود في قائمة الرغبات.'
                    return JsonResponse({'success': False, 'message': message, 'status': 'not_found'}, status=404)
        else:
            wishlist_session = request.session.get('wishlist', [])
            if str(product_id) in wishlist_session:
                wishlist_session.remove(str(product_id))
                request.session['wishlist'] = wishlist_session
                wishlist_count = len(wishlist_session)
                request.session['wishlist_count'] = wishlist_count
                message = 'Item removed successfully!' if lang == 'en' else 'تمت إزالة العنصر بنجاح!'
                return JsonResponse({'success': True, 'message': message, 'wishlist_total_items': wishlist_count, 'status': 'removed'})
            else:
                message = 'Item not found in wishlist.' if lang == 'en' else 'العنصر غير موجود في قائمة الرغبات.'
                return JsonResponse({'success': False, 'message': message, 'status': 'not_found'}, status=404)
    except Exception:
        message = 'An error occurred.' if lang == 'en' else 'حدث خطأ.'
        return JsonResponse({'success': False, 'message': message}, status=500)




# --- Cart Views ---
def cart_view(request):
    cart = get_or_create_cart(request)

    # Process stock adjustments and removals
    items_to_remove = []
    quantities_to_update = {}

    if cart:
        # Fetch cart items efficiently for processing
        cart_items_queryset = cart.items.select_related(
            'product_variant__product',
            'product_variant__color',
            'product_variant__size'
        ).order_by('pk')

        for item in cart_items_queryset:
            # If product_variant is somehow None (e.g., deleted), or stock is 0
            if not item.product_variant or item.product_variant.stock_quantity == 0:
                items_to_remove.append(item.id)
                messages.error(request,
                               _(f"{item.product_variant.product.name if item.product_variant else 'An item'} was removed from your cart as it is out of stock."))
            elif item.quantity > item.product_variant.stock_quantity:
                adjusted_quantity = item.product_variant.stock_quantity
                quantities_to_update[item.id] = adjusted_quantity
                messages.warning(request,
                                 _(f"Quantity for {item.product_variant.product.name} was adjusted to {adjusted_quantity} due to limited stock."))

        # Perform actual database modifications in an atomic block
        with transaction.atomic():
            if items_to_remove:
                CartItem.objects.filter(id__in=items_to_remove).delete()
            for item_id, new_quantity in quantities_to_update.items():
                CartItem.objects.filter(id=item_id).update(quantity=new_quantity)

        # --- Get user's location city for shipping calculation ---
        user_location_city = get_user_shipping_city(request)
        cart_data = get_cart_totals(cart, user_location_city=user_location_city)
        cart_items = cart.items.all()  # Get the actual CartItem objects for the template
    else:
        # If no cart exists, initialize data as empty
        user_location_city = get_user_shipping_city(request)  # Still try to get city even if cart is empty
        cart_data = get_cart_totals(None, user_location_city=user_location_city)  # Pass None to get default zeros
        cart_items = []

    request.session['cart_count'] = cart_data['cart_total_items']

    return render(request, 'shop/cart_view.html', {  # Corrected template name to cart.html
        'items': cart_items,  # Pass the actual CartItem objects (queryset)
        'cart_total_items': cart_data['cart_total_items'],
        'cart_total_price': cart_data['cart_total_price'],
        'shipping_cost': cart_data['shipping_cost'],
        'grand_total': cart_data['grand_total'],
        'shipping_status_message': cart_data['shipping_status_message'],  # Pass the status message
        'cart': cart  # Still useful to pass the cart object itself
    })

@require_POST
def remove_from_cart(request):
    lang = getattr(request, 'LANGUAGE_CODE', 'en')

    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse(
            {'success': False, 'message': 'Invalid request type.' if lang == 'en' else 'نوع الطلب غير صالح.'},
            status=HttpResponseBadRequest.status_code
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.error("remove_from_cart: Invalid JSON data received.")
        return JsonResponse(
            {'success': False, 'message': 'Invalid JSON data.' if lang == 'en' else 'بيانات JSON غير صالحة.'},
            status=HttpResponseBadRequest.status_code
        )

    cart_item_id_str = data.get('cart_item_id')

    if not cart_item_id_str:
        logger.warning(f"remove_from_cart: Cart item ID not provided or empty. Received: '{cart_item_id_str}'")
        return JsonResponse(
            {'success': False, 'message': 'Cart item ID not provided.' if lang == 'en' else 'معرف عنصر السلة غير موجود.'},
            status=HttpResponseBadRequest.status_code
        )

    try:
        cart_item_id = int(cart_item_id_str)
    except ValueError:
        logger.warning(f"remove_from_cart: Invalid cart item ID format. Could not convert to int. Received: '{cart_item_id_str}'")
        return JsonResponse(
            {'success': False, 'message': 'Invalid cart item ID format.' if lang == 'en' else 'تنسيق معرف عنصر السلة غير صالح.'},
            status=HttpResponseBadRequest.status_code
        )

    try:
        cart = get_or_create_cart(request)
        # Catch Http404 specifically here, as get_object_or_404 raises it
        cart_item = get_object_or_404(CartItem, id=cart_item_id, cart=cart)

        with transaction.atomic():
            cart_item.delete()

            user_location_city = get_user_shipping_city(request)
            cart_data = get_cart_totals(cart, user_location_city=user_location_city)

            request.session['cart_count'] = cart_data['cart_total_items']

            message = 'Item removed from cart.' if lang == 'en' else 'تمت إزالة العنصر من السلة.'

            return JsonResponse({
                'success': True,
                'message': message,
                'cart_item_id': cart_item_id,
                'cart_total_items': cart_data['cart_total_items'],
                'cart_total_price': float(cart_data['cart_total_price']),
                'shipping_cost': float(cart_data['shipping_cost']),
                'grand_total': float(cart_data['grand_total']),
                'shipping_status_message': cart_data['shipping_status_message'],
            })

    # CHANGE: Catch Http404 directly, as get_object_or_404 raises this
    except Http404:
        logger.warning(f"remove_from_cart: Cart item with ID {cart_item_id} not found or does not belong to cart for session/user.")
        return JsonResponse(
            {'success': False, 'message': 'Cart item not found or does not belong to your cart.' if lang == 'en' else 'لم يتم العثور على عنصر السلة أو لا ينتمي إلى سلتك.'},
            status=404 # Return 404 for Not Found
        )
    except Exception as e:
        logger.exception(f"Unexpected error in remove_from_cart for cart_item_id {cart_item_id}: {e}")
        return JsonResponse(
            {'success': False, 'message': 'An unexpected error occurred.' if lang == 'en' else 'حدث خطأ غير متوقع.'},
            status=500
        )

@require_POST
def update_cart_quantity(request):
    lang = getattr(request, 'LANGUAGE_CODE', 'en')  # Get current language for messages

    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(
            {'success': False, 'message': 'Invalid request type.' if lang == 'en' else 'نوع الطلب غير صالح.'},
            status=HttpResponseBadRequest.status_code)

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            message = 'Invalid JSON data.' if lang == 'en' else 'بيانات JSON غير صالحة.'
            return JsonResponse({'success': False, 'message': message}, status=HttpResponseBadRequest.status_code)

        cart_item_id = data.get('cart_item_id')
        new_quantity = data.get('quantity')

        if not cart_item_id or new_quantity is None:
            message = 'Cart item ID or quantity not provided.' if lang == 'en' else 'معرف عنصر السلة أو الكمية غير موجودة.'
            return JsonResponse({'success': False, 'message': message}, status=HttpResponseBadRequest.status_code)

        try:
            cart_item_id = int(cart_item_id)
            new_quantity = int(new_quantity)
        except ValueError:
            message = 'Invalid quantity or item ID format.' if lang == 'en' else 'تنسيق معرف العنصر أو الكمية غير صالح.'
            return JsonResponse({'success': False, 'message': message}, status=HttpResponseBadRequest.status_code)

        try:
            cart = get_or_create_cart(request)  # Get or create cart, handles user/session
            cart_item = get_object_or_404(CartItem.objects.select_related('cart', 'product_variant'), id=cart_item_id,
                                          cart=cart)
            # get_object_or_404 with cart=cart checks ownership implicitly

            if new_quantity <= 0:
                with transaction.atomic():
                    cart_item.delete()
                message = 'Item removed from cart.' if lang == 'en' else 'تمت إزالة العنصر من السلة.'
                status = 'removed'
                item_total_price = Decimal('0.00')  # Item total is 0 if removed
            else:
                current_stock = cart_item.product_variant.stock_quantity if cart_item.product_variant else 0
                if new_quantity > current_stock:
                    messages.warning(request,
                                     _(f"Quantity for {cart_item.product_variant.product.name if cart_item.product_variant else 'An item'} was adjusted to {current_stock} due to limited stock."))
                    new_quantity = current_stock  # Adjust to max available stock

                if new_quantity == 0:
                    with transaction.atomic():
                        cart_item.delete()
                    message = 'Item removed from cart as it is out of stock.' if lang == 'en' else 'تمت إزالة العنصر من السلة لأنه نفد من المخزون.'
                    status = 'removed'
                    item_total_price = Decimal('0.00')
                else:
                    with transaction.atomic():
                        cart_item.quantity = new_quantity
                        cart_item.save()
                    message = 'Cart quantity updated.' if lang == 'en' else 'تم تحديث كمية السلة.'
                    status = 'updated'
                    item_total_price = cart_item.get_total_price()  # Get total based on new quantity

            # After any modification, update cart totals and get fresh data
            user_location_city = get_user_shipping_city(request)
            cart_data = get_cart_totals(cart, user_location_city=user_location_city)

            request.session['cart_count'] = cart_data['cart_total_items']

            return JsonResponse({
                'success': True,
                'message': message,
                'status': status,
                'cart_item_id': cart_item_id,
                'new_quantity': cart_item.quantity if status == 'updated' else 0,
                'item_total_price': float(item_total_price),
                'cart_total_items': cart_data['cart_total_items'],
                'cart_total_price': float(cart_data['cart_total_price']),
                'shipping_cost': float(cart_data['shipping_cost']),
                'grand_total': float(cart_data['grand_total']),
                'shipping_status_message': cart_data['shipping_status_message'],  # Pass the status message
            })

        except CartItem.DoesNotExist:
            message = 'Cart item not found.' if lang == 'en' else 'لم يتم العثور على عنصر في السلة.'
            return JsonResponse({'success': False, 'message': message}, status=404)
        except ProductVariant.DoesNotExist:
            message = 'Product variant not found for this cart item.' if lang == 'en' else 'لم يتم العثور على متغير المنتج لعنصر السلة هذا.'
            return JsonResponse({'success': False, 'message': message}, status=404)
        except Exception as e:
            print(f"Error updating cart quantity: {e}")
            message = f'An unexpected error occurred: {str(e)}' if lang == 'en' else f'حدث خطأ غير متوقع: {str(e)}'
            return JsonResponse({'success': False, 'message': message}, status=500)

    except Exception as e:
        print(f"Critical error in update_cart_quantity request processing: {e}")
        message = 'An error occurred during request processing.' if lang == 'en' else 'حدث خطأ أثناء معالجة الطلب.'
        return JsonResponse({'success': False, 'message': message}, status=500)


# --- Checkout & Order Views ---
SHIPPING_COSTS = {
    'INSIDE_CAIRO': Decimal('50.00'), # Example: 50 EGP
    'OUTSIDE_CAIRO': Decimal('100.00'), # Example: 100 EGP
    'INTERNATIONAL': Decimal('250.00'), # Example: For other countries
}
CAIRO_CITIES = ['cairo', 'giza', 'heliopolis', 'nasr city', 'maadi', 'el shorouk', 'new cairo', '6th of october']# Add more common spellings if necessary for robustness

def get_cart_for_request(request):
    """
    Helper function to retrieve the current user's or session's cart.
    """
    if request.user.is_authenticated:
        return Cart.objects.filter(user=request.user).first() # Use .first() to avoid DoesNotExist
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        return Cart.objects.filter(session_key=session_key).first()

def calculate_shipping_cost(country_code, city_name):
    """
    Calculates shipping cost based on country and city.
    """
    city_name_lower = city_name.lower().strip()

    if country_code == 'EG': # Egypt
        if city_name_lower in CAIRO_CITIES:
            return SHIPPING_COSTS['INSIDE_CAIRO']
        else:
            return SHIPPING_COSTS['OUTSIDE_CAIRO']
    else:
        # For international shipping, you might have more complex logic
        # For simplicity, returning a fixed international rate for any non-EG country
        return SHIPPING_COSTS['INTERNATIONAL']

@require_POST
def apply_coupon(request):
    """
    AJAX endpoint to apply a coupon and recalculate totals.
    """
    coupon_form = CouponForm(request.POST)
    if coupon_form.is_valid():
        code = coupon_form.cleaned_data['code']
        cart = get_cart_for_request(request)

        if not cart or not cart.items.exists():
            return JsonResponse({'success': False, 'message': _("Your cart is empty.")})

        try:
            coupon = Coupon.objects.get(code__iexact=code)
            is_valid, message = coupon.is_valid(cart.get_subtotal(), request.user) # Assuming get_subtotal() on Cart

            if is_valid:
                # Store coupon code in session
                request.session['applied_coupon_code'] = coupon.code
                # Recalculate totals (could be done in client-side or by calling another AJAX endpoint)
                # For simplicity, we'll return message and let checkout_view re-render or re-fetch on success
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'coupon_code': coupon.code,
                    # You might want to return updated subtotal, discount, grand total here
                })
            else:
                if 'applied_coupon_code' in request.session:
                    del request.session['applied_coupon_code'] # Remove invalid coupon from session
                return JsonResponse({'success': False, 'message': message})
        except Coupon.DoesNotExist:
            if 'applied_coupon_code' in request.session:
                del request.session['applied_coupon_code'] # Ensure it's removed if not found
            return JsonResponse({'success': False, 'message': _("Invalid coupon code.")})
    else:
        return JsonResponse({'success': False, 'message': _("Invalid form submission.")})


# --- Your existing checkout_view (with minor adjustments for clarity and flow) ---
@transaction.atomic
def checkout_view(request):
    logger.info("--- Starting checkout_view ---")
    cart = get_or_create_cart(request)
    if not cart or not cart.items.exists():
        messages.warning(request, _("Your cart is empty. Please add items before checking out."))
        return redirect('shop:cart_view')

    # Update totals and check stock
    cart.update_totals()
    if cart.total_items == 0:
        messages.warning(request, _("Your cart is empty after stock adjustments. Please add items before checking out."))
        return redirect('shop:cart_view')

    # Prepare initial data and address selection
    initial_shipping_data = {}
    user_addresses = (
        ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-id')
        if request.user.is_authenticated else ShippingAddress.objects.none()
    )
    selected_address_id = request.POST.get('selected_address') if request.method == 'POST' else None

    # Determine default address
    if request.user.is_authenticated:
        if request.method == 'GET' or selected_address_id is None:
            if user_addresses.exists():
                default_addr = user_addresses.filter(is_default=True).first() or user_addresses.first()
                selected_address_id = str(default_addr.id)
            else:
                selected_address_id = 'new'
        if selected_address_id == 'new' and not request.POST:
            initial_shipping_data['full_name'] = request.user.get_full_name() or request.user.username
            initial_shipping_data['email'] = request.user.email
    else:
        selected_address_id = 'new'

    # Load existing address if selected
    selected_address_obj = None
    if selected_address_id and selected_address_id != 'new':
        if request.user.is_authenticated:
            try:
                selected_address_obj = get_object_or_404(ShippingAddress, id=selected_address_id, user=request.user)
                shipping_form = ShippingAddressForm(initial={
                    'full_name': selected_address_obj.full_name,
                    'email': selected_address_obj.email,
                    'phone_number': selected_address_obj.phone_number,
                    'address_line1': selected_address_obj.address_line1,
                    'address_line2': selected_address_obj.address_line2,
                    'city': selected_address_obj.city,
                })
            except Http404:
                messages.error(request, _("Selected address not found or not yours."))
                selected_address_id = 'new'
        else:
            messages.error(request, _("You must be logged in to select an existing address."))
            selected_address_id = 'new'

    # Instantiate shipping form
    if 'shipping_form' not in locals():
        shipping_form = ShippingAddressForm(
            request.POST if request.method == 'POST' and selected_address_id == 'new' else None,
            initial=initial_shipping_data
        )

    payment_form = PaymentForm(request.POST or None)
    coupon_form = CouponForm(request.POST or None)

    # Determine shipping calculation parameters
    user_city_for_shipping_calc = None
    if selected_address_obj:
        user_city_for_shipping_calc = selected_address_obj.city
    elif shipping_form.is_valid():
        user_city_for_shipping_calc = shipping_form.cleaned_data.get('city')

    # Handle AJAX requests (coupon, order summary)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Implementation omitted for brevity
        pass

    # --- Final totals calculation ---
    # (Implementation omitted for brevity)
    # e.g., recalculate totals and prepare context

    # Handle order placement
    if request.method == 'POST' and 'place_order_action' in request.POST:
        # Validate forms and call process_order
        # (Implementation omitted for brevity)
        pass

    context = {
        'cart': cart,
        'shipping_form': shipping_form,
        'payment_form': payment_form,
        'coupon_form': coupon_form,
        'user_shipping_addresses': user_addresses,
        # other context variables
    }
    return render(request, 'shop/checkout.html', context)

@transaction.atomic
def process_order(request, cart, shipping_form=None, payment_form=None, existing_address=None,
                  calculated_shipping_cost=Decimal('0.00'), applied_coupon=None, discount_amount=Decimal('0.00')):
    logger.info("--- Starting process_order ---")
    try:
        # Validate payment form
        if not payment_form or not payment_form.is_valid():
            messages.error(request, _("Payment information is required and must be valid."))
            return redirect('shop:checkout')

        # Create or copy shipping address
        if existing_address:
            final_shipping_address = ShippingAddress.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=existing_address.full_name,
                email=existing_address.email,
                phone_number=existing_address.phone_number,
                address_line1=existing_address.address_line1,
                address_line2=existing_address.address_line2,
                city=existing_address.city,
                is_default=False
            )
        elif shipping_form and shipping_form.is_valid():
            shipping_address_instance = shipping_form.save(commit=False)
            # No country field
            if request.user.is_authenticated:
                shipping_address_instance.user = request.user
                if shipping_form.cleaned_data.get('save_as_default'):
                    ShippingAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
                    shipping_address_instance.is_default = True
            shipping_address_instance.save()
            final_shipping_address = shipping_address_instance
        else:
            messages.error(request, _("Shipping information is required and must be valid."))
            return redirect('shop:checkout')

        # Calculate totals
        order_subtotal = Decimal('0.00')
        for cart_item in cart.items.select_related('product_variant').all():
            variant = cart_item.product_variant
            if variant.stock_quantity < cart_item.quantity:
                messages.error(request, _("Not enough stock for {}").format(variant.product.name))
                return redirect('shop:cart_view')
            price = variant.get_price()
            if not isinstance(price, Decimal):
                price = Decimal(str(price))
            order_subtotal += price * cart_item.quantity

        # Re-validate coupon
        if applied_coupon:
            is_valid, message = applied_coupon.is_valid(order_subtotal, request.user)
            if not is_valid:
                messages.error(request, _(f"Coupon invalid: {message}"))
                if 'applied_coupon_code' in request.session:
                    del request.session['applied_coupon_code']
                return redirect('shop:checkout')
            discount_amount = applied_coupon.get_discount_amount(order_subtotal)

        # Final total
        grand_total = (order_subtotal + calculated_shipping_cost) - discount_amount
        if grand_total < 0:
            grand_total = Decimal('0.00')

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            shipping_address=final_shipping_address,
            full_name=final_shipping_address.full_name,
            email=final_shipping_address.email,
            phone_number=final_shipping_address.phone_number,
            subtotal=order_subtotal,
            shipping_cost=calculated_shipping_cost,
            discount_amount=discount_amount,
            grand_total=grand_total,
            coupon=applied_coupon,
            status='pending',
            payment_status='pending'
        )

        # Create order items and update stock
        for cart_item in cart.items.select_related('product_variant').all():
            variant = cart_item.product_variant
            price = variant.get_price()
            OrderItem.objects.create(
                order=order,
                product_variant=variant,
                quantity=cart_item.quantity,
                price_at_purchase=price
            )
            variant.stock_quantity -= cart_item.quantity
            variant.save()

        # Process payment (simulate or integrate gateway)
        payment_method = payment_form.cleaned_data['payment_method']
        transaction_id = f"COD-{order.order_number}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        Payment.objects.create(
            order=order,
            payment_method=payment_method,
            amount=grand_total,
            transaction_id=transaction_id,
            status='completed' if payment_method == 'cash_on_delivery' else 'pending'
        )

        # Update order status
        if payment_method == 'cash_on_delivery':
            order.status = 'processing'
            order.payment_status = 'completed'
        else:
            order.status = 'pending_payment'
            order.payment_status = 'pending'
        order.save()

        # Clear cart/session
        cart.items.all().delete()
        cart.delete()
        request.session.pop('cart_id', None)
        request.session.pop('cart_count', None)
        if 'applied_coupon_code' in request.session:
            del request.session['applied_coupon_code']

        # Increment coupon usage
        if applied_coupon:
            applied_coupon.used_count += 1
            applied_coupon.save()

        # Send confirmation email (optional)
        # send_order_confirmation_email(order)

        messages.success(request, _("Your order has been successfully placed!"))
        return redirect(reverse('shop:order_confirmation', args=[order.order_number]))

    except Exception as e:
        logger.exception(f"Error during order processing: {e}")
        messages.error(request, _("An unexpected error occurred during checkout. Please try again."))
        return redirect('shop:checkout')
# --- Example order confirmation view for authenticated users (ensure this exists) ---
def order_confirmation_view(request, order_id):  # <--- Changed parameter to order_id
    order = get_object_or_404(Order, id=order_id)  # <--- Use id to retrieve
    # Ensure only the owner or staff can view their order
    if not request.user.is_authenticated or (order.user != request.user and not request.user.is_staff):
        messages.error(request, _("You are not authorized to view this order."))
        return redirect('shop:home')

    context = {
        'order': order,
        'is_anonymous_access': False,
    }
    return render(request, 'shop/order_confirmation.html', context)


# --- NEW: Order confirmation view for anonymous users (ensure this exists) ---
def order_confirmation_anonymous_view(request, order_id, token):  # <--- Changed parameters
    try:
        # Use both order_id AND the token for security
        order = get_object_or_404(Order, id=order_id, anonymous_access_token=token, user__isnull=True)
    except Order.DoesNotExist:
        messages.error(request, _("Order not found or access denied."))
        return redirect('shop:home')

    # If the order is linked to a user, and the current request is authenticated,
    # and it's not the correct user, deny access. This prevents authenticated users
    # from using anonymous links for other users' orders.
    if order.user and request.user.is_authenticated and order.user != request.user:
        messages.error(request, _("You are not authorized to view this order."))
        return redirect('shop:home')
    # If the order is linked to a user, and the current request is anonymous,
    # it still should be accessible via the anonymous token.

    context = {
        'order': order,
        'is_anonymous_access': True,  # Useful for conditional display in template
    }
    return render(request, 'shop/order_confirmation.html', context)


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

def get_available_sizes_ajax(request):
    """
    AJAX endpoint to get available sizes based on product and selected color.
    """
    if request.method == 'GET' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        product_id = request.GET.get('product_id')
        color_id = request.GET.get('color_id')

        product = get_object_or_404(Product, id=product_id)
        available_sizes_query = product.get_available_sizes(color_id=color_id)

        # Convert queryset to a list of dictionaries for JSON response
        available_sizes_data = list(available_sizes_query.values('id', 'name'))

        return JsonResponse({'success': True, 'available_sizes': available_sizes_data})
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
