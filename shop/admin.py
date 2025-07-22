from django.contrib import admin

from django.contrib import admin
from django.utils.html import format_html

from shop.models import (
    Category, SubCategory, FitType, Brand, Color, Size, 
    Product, ProductImage, ProductColor, ProductSize, ProductVariant,HomeSlider , Cart, CartItem, Wishlist, WishlistItem
)

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
            return format_html('<img src="{}" width="140" height="65" style="object-fit: cover;" />', obj.image_resized.url)
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
        })
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
