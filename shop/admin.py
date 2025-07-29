from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from shop.models import (
    Category, SubCategory, FitType, Brand, Color, Size,
    Product, ProductImage, ProductColor, ProductSize, ProductVariant,
    HomeSlider, Cart, CartItem, Wishlist, WishlistItem,
    Order, OrderItem, ShippingAddress, Payment, ReverseUser  # Import new models
)


@admin.register(ReverseUser)
class ReverseUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'phone', 'is_customer', 'is_staff', 'date_joined']
    list_filter = ['is_customer', 'is_staff', 'is_active']
    search_fields = ['username', 'email', 'phone']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_or_session', 'total_items', 'total_price', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'session_key']

    def user_or_session(self, obj):
        return obj.user.username if obj.user else f"Session: {obj.session_key}"

    user_or_session.short_description = 'Owner'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product_name', 'variant_color', 'variant_size', 'quantity', 'added_at']
    list_filter = ['added_at']
    search_fields = ['cart__user__username', 'product_variant__product__name']

    def product_name(self, obj):
        return obj.product_variant.product.name

    def variant_color(self, obj):
        return obj.product_variant.color.name

    def variant_size(self, obj):
        return obj.product_variant.size.name


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username']


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['wishlist', 'product_name', 'added_at']
    list_filter = ['added_at']
    search_fields = ['wishlist__user__username', 'product__name']

    def product_name(self, obj):
        return obj.product.name


@admin.register(HomeSlider)
class HomeSliderAdmin(admin.ModelAdmin):
    list_display = (
        'heading',
        'subheading',
        'order',
        'is_active',
        'preview_image',
    )
    list_editable = ('order', 'is_active')
    search_fields = ('heading', 'subheading', 'alt_text')
    list_filter = ('is_active',)
    ordering = ('order',)

    def preview_image(self, obj):
        if obj.image_resized:
            return format_html('<img src="{}" width="140" height="65" style="object-fit: cover;" />',
                               obj.image_resized.url)
        return "-"

    preview_image.short_description = "Preview"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(FitType)
class FitTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['name', 'hex_code', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'hex_code']


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ['name', 'size_type', 'order', 'is_active']
    list_filter = ['size_type', 'is_active']
    search_fields = ['name']
    ordering = ['size_type', 'order']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductColorInline(admin.TabularInline):
    model = ProductColor
    extra = 1


class ProductSizeInline(admin.TabularInline):
    model = ProductSize
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'subcategory', 'brand', 'price',
        'is_best_seller', 'is_new_arrival', 'is_on_sale',
        'is_active', 'created_at'
    ]
    list_filter = [
        'category', 'subcategory', 'brand', 'fit_type',
        'is_best_seller', 'is_new_arrival', 'is_on_sale',
        'is_featured', 'is_active', 'created_at'
    ]
    search_fields = ['name', 'description', 'brand__name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProductImageInline, ProductColorInline, ProductSizeInline, ProductVariantInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'short_description')
        }),
        ('Categorization', {
            'fields': ('category', 'subcategory', 'fit_type', 'brand')
        }),
        ('Pricing', {
            'fields': ('price', 'sale_price')
        }),
        ('Flags', {
            'fields': ('is_best_seller', 'is_new_arrival', 'is_on_sale', 'is_featured')
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'is_active', 'is_available')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Size Chart', {
            'fields': ('size_chart','delivery_return',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'alt_text', 'is_main', 'order', 'color', 'created_at']
    list_filter = ['is_main', 'color', 'created_at']
    search_fields = ['product__name', 'alt_text']


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'color', 'size', 'sku', 'stock_quantity', 'is_available']
    list_filter = ['color', 'size', 'is_available']
    search_fields = ['product__name', 'sku']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Make these fields read-only for existing items, but allow them to be set for new ones via JavaScript
    # For initial creation, we need to allow price_at_purchase to be set
    readonly_fields = ['get_total_price'] # Keep get_total_price readonly as it's a calculated property
    fields = ['product_variant', 'quantity', 'price_at_purchase'] # Explicitly list fields for adding/editing
    can_delete = False

    def get_total_price(self, obj):
        # Ensure quantity and price_at_purchase are not None before multiplication
        quantity = obj.quantity if obj.quantity is not None else Decimal('0.00')
        price_at_purchase = obj.price_at_purchase if obj.price_at_purchase is not None else Decimal('0.00')
        return quantity * price_at_purchase
    get_total_price.short_description = "Total Price"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user', 'full_name', 'grand_total',
        'status', 'payment_status', 'created_at'
    ]
    list_filter = ['status', 'payment_status', 'created_at', 'updated_at']
    search_fields = ['order_number', 'user__username', 'full_name', 'email', 'phone_number']
    readonly_fields = [
        'order_number', 'created_at', 'updated_at',
        'subtotal', 'shipping_cost', 'grand_total', 'stripe_pid'
    ]
    inlines = [OrderItemInline]

    fieldsets = (
        ('Order Details', {
            'fields': ('order_number', 'user', 'status', 'payment_status', 'stripe_pid')
        }),
        ('Customer Information', {
            'fields': ('full_name', 'email', 'phone_number')
        }),
        ('Financials', {
            'fields': ('subtotal', 'shipping_cost', 'grand_total')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_variant', 'quantity', 'price_at_purchase', 'get_total']
    list_filter = ['order__status', 'product_variant__product__name']
    search_fields = ['order__order_number', 'product_variant__product__name']
    readonly_fields = ['get_total']

    def get_total(self, obj):
        return obj.get_total_price()

    get_total.short_description = 'Total'



@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = [
        'user_display', 'full_name', 'address_line1', 'city', 'phone_number', 'is_default'
    ]
    list_filter = ['city', 'is_default']
    search_fields = [
        'user__username', 'full_name', 'address_line1', 'city', 'phone_number'
    ]
    readonly_fields = ['user']

    def user_display(self, obj):
        return obj.user.username if obj.user else _("N/A")
    user_display.short_description = _("User")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'transaction_id', 'payment_method', 'amount',
        'is_success', 'timestamp'
    ]
    list_filter = ['payment_method', 'is_success', 'timestamp']
    search_fields = ['order__order_number', 'transaction_id']
    readonly_fields = ['order', 'transaction_id', 'payment_method', 'amount', 'timestamp', 'payment_details']

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make transaction_id, payment_method, amount, timestamp, payment_details read-only
        # as these should ideally be set by the payment gateway integration.
        # This is already covered by readonly_fields, but a reminder if you customize forms.
        return form