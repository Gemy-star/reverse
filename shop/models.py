# shop/models.py

from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from django.utils.translation import gettext_lazy as _
from colorfield.fields import ColorField
from django.conf import settings
import uuid
from django_countries.fields import CountryField
from ckeditor.fields import RichTextField
from django.utils import timezone


class ReverseUser(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Includes additional fields for e-commerce functionality.
    """
    # Removed 'phone' to avoid redundancy with 'phone_number'.
    # If you prefer 'phone', rename 'phone_number' to 'phone'.
    phone_number = models.CharField(max_length=15, blank=True, null=True,
                                    verbose_name=_("Phone Number"))
    is_customer = models.BooleanField(default=True, verbose_name=_("Is Customer"))

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")


class Category(models.Model):
    """Represents a product category."""
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name=_("Image"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    image_resized = ImageSpecField(
        source='image',
        processors=[ResizeToFill(376, 477)],
        format='JPEG',
        options={'quality': 85}
    )

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:category_detail', kwargs={'slug': self.slug})


class SubCategory(models.Model):
    """Represents a product sub-category belonging to a main category."""
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE, verbose_name=_("Category"))
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, blank=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    image = models.ImageField(upload_to='subcategories/', blank=True, null=True, verbose_name=_("Image"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    image_resized = ImageSpecField(
        source='image',
        processors=[ResizeToFill(376, 477)],
        format='JPEG',
        options={'quality': 85}
    )

    class Meta:
        verbose_name = _("Sub Category")
        verbose_name_plural = _("Sub Categories")
        unique_together = ['category', 'slug']
        ordering = ['name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:subcategory_detail', kwargs={'category_slug': self.category.slug, 'slug': self.slug})


class FitType(models.Model):
    """Defines product fit types (e.g., Slim Fit, Regular Fit)."""
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(max_length=50, unique=True, blank=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name = _("Fit Type")
        verbose_name_plural = _("Fit Types")
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Brand(models.Model):
    """Represents a product brand."""
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name=_("Slug"))
    logo = models.ImageField(upload_to='brands/', blank=True, null=True, verbose_name=_("Logo"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    logo_resized = ImageSpecField(
        source='logo',
        processors=[ResizeToFill(376, 477)],
        format='JPEG',
        options={'quality': 85}
    )

    class Meta:
        verbose_name = _("Brand")
        verbose_name_plural = _("Brands")
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Color(models.Model):
    """Represents a product color."""
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Name"))
    hex_code = ColorField(default='#FFFFFF', verbose_name=_("Color Code"), help_text=_("Color hex code (e.g., #FF0000)"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name = _("Color")
        verbose_name_plural = _("Colors")
        ordering = ['name']

    def __str__(self):
        return self.name


class Size(models.Model):
    """Represents a product size."""
    SIZE_TYPES = [
        ('clothing', _('Clothing')),
        ('shoes', _('Shoes')),
        ('accessories', _('Accessories')),
    ]

    name = models.CharField(max_length=20, verbose_name=_("Name"))
    size_type = models.CharField(max_length=20, choices=SIZE_TYPES, default='clothing', verbose_name=_("Size Type"))
    order = models.IntegerField(default=0, verbose_name=_("Order"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name = _("Size")
        verbose_name_plural = _("Sizes")
        ordering = ['size_type', 'order', 'name']
        unique_together = ['name', 'size_type']

    def __str__(self):
        # The type: ignore comment is often used for MyPy or other type checkers
        # If your IDE gives a warning for get_size_type_display, this is fine.
        return f"{self.name} ({self.get_size_type_display()})"  # type: ignore


class Product(models.Model):
    """Represents a single product in the shop."""
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    slug = models.SlugField(max_length=200, unique=True, blank=True, verbose_name=_("Slug"))
    description = models.TextField(verbose_name=_("Description"))
    short_description = models.CharField(max_length=300, blank=True, verbose_name=_("Short Description"))

    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, verbose_name=_("Category"))
    subcategory = models.ForeignKey(SubCategory, related_name='products', on_delete=models.CASCADE, verbose_name=_("Subcategory"))
    fit_type = models.ForeignKey(FitType, related_name='products', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Fit Type"))
    brand = models.ForeignKey(Brand, related_name='products', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Brand"))

    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name=_("Price"))
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(Decimal('0.01'))], verbose_name=_("Sale Price"))

    # Flags
    is_best_seller = models.BooleanField(default=False, verbose_name=_("Is Best Seller"))
    is_new_arrival = models.BooleanField(default=False, verbose_name=_("Is New Arrival"))
    is_on_sale = models.BooleanField(default=False, verbose_name=_("Is On Sale"))  # Will be auto-set in save()
    is_featured = models.BooleanField(default=False, verbose_name=_("Is Featured"))

    # Stock status
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_("Stock Quantity")) # This might become less relevant with variants
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    is_available = models.BooleanField(default=True, verbose_name=_("Is Available"))

    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True, verbose_name=_("Meta Title"))
    meta_description = models.CharField(max_length=300, blank=True, verbose_name=_("Meta Description"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    # Many-to-many (through ProductColor/ProductSize/ProductVariant)
    colors = models.ManyToManyField(Color, through='ProductColor', blank=True, verbose_name=_("Colors"))
    sizes = models.ManyToManyField(Size, through='ProductSize', blank=True, verbose_name=_("Sizes"))
    size_chart = RichTextField(blank=True, null=True, help_text=_("Add size chart content here (HTML supported)"), verbose_name=_("Size Chart"))
    delivery_return = RichTextField(blank=True, null=True, help_text=_("Add Delivery and return policy (HTML supported)"), verbose_name=_("Delivery & Return"))

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', 'subcategory']),
            models.Index(fields=['is_active', 'is_available']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        # Automatically set is_on_sale
        if self.sale_price and self.sale_price < self.price:
            self.is_on_sale = True
        else:
            self.is_on_sale = False

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    @property
    def get_price(self):
        """Return current price (sale price if applicable)"""
        if self.is_on_sale and self.sale_price:
            return self.sale_price
        return self.price

    @property
    def get_discount_percentage(self):
        """Return discount percentage if on sale"""
        if self.is_on_sale and self.sale_price:
            # Avoid division by zero if price is 0 (though MinValueValidator prevents this)
            if self.price > 0:
                discount = (self.price - self.sale_price) / self.price
                return round(discount * 100)
        return 0

    @property
    def is_in_stock(self):
        """Return if total stock is above 0 from any variant"""
        return self.variants.filter(stock_quantity__gt=0, is_available=True).exists()

    def get_main_image(self):
        """Return the main image or fallback to first image for the product."""
        # Consider adding a default image if no images are found
        main_image = self.images.filter(is_main=True).first()
        return main_image or self.images.first()

    def get_hover_image(self):
        """Return the hover image or fallback to first image for the product."""
        hover_image = self.images.filter(is_hover=True).first()
        return hover_image or self.images.first()

    def get_available_colors(self):
        """Return distinct active colors that have at least one variant in stock."""
        return Color.objects.filter(
            is_active=True,
            productvariant__product=self,
            productvariant__stock_quantity__gt=0,
            productvariant__is_available=True
        ).distinct()

    def get_available_sizes(self, color_id=None):
        """
        Return distinct active sizes that have at least one variant in stock.
        Optionally filter by a specific color.
        """
        filters = Q(is_active=True) & Q(productvariant__product=self) & \
                  Q(productvariant__stock_quantity__gt=0) & Q(productvariant__is_available=True)

        if color_id:
            filters &= Q(productvariant__color_id=color_id)

        return Size.objects.filter(filters).distinct().order_by('size_type', 'order', 'name')

    @property
    def get_all_product_sizes_by_type(self):
        """
        Return all active sizes relevant to the product.
        Since Category doesn't have a 'size_type' field, this method needs a clear logic
        to determine what 'size_type' to filter by.
        Possibilities:
        1. Add a `size_type` field to Category or SubCategory.
        2. Infer `size_type` from a related attribute (e.g., if a category is "T-shirts", its size_type is 'clothing').
        3. Simply return all active sizes if a type-specific filter isn't truly necessary.

        For now, this will default to returning all active sizes if a category-specific type isn't defined.
        Consider how you intend to associate size types with categories or products.
        """
        # Example of inferring size_type (you'd need to implement this logic)
        # For instance, if your Category model has a `size_type` field:
        # if hasattr(self.category, 'size_type') and self.category.size_type:
        #     return Size.objects.filter(is_active=True, size_type=self.category.size_type).order_by('size_type', 'order', 'name')
        # else:
        # Fallback if no specific size_type can be determined or assigned
        return Size.objects.filter(is_active=True).order_by('size_type', 'order', 'name')


class ProductImage(models.Model):
    """Stores images for a product, optionally linked to a specific color."""
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE, verbose_name=_("Product"))
    image = models.ImageField(upload_to='products/', verbose_name=_("Image"))
    alt_text = models.CharField(max_length=200, blank=True, verbose_name=_("Alt Text"))
    is_main = models.BooleanField(default=False, verbose_name=_("Is Main Image"))
    is_hover = models.BooleanField(default=False, verbose_name=_("Is Hover Image"))
    order = models.IntegerField(default=0, verbose_name=_("Order"))
    color = models.ForeignKey(Color, related_name='product_images', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Color"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    image_resized = ImageSpecField(
        source='image',
        processors=[ResizeToFill(376, 477)],
        format='JPEG',
        options={'quality': 85}
    )
    thumb_resized = ImageSpecField(
        source='image',
        processors=[ResizeToFill(709, 920)],
        format='JPEG',
        options={'quality': 70}
    )

    class Meta:
        verbose_name = _("Product Image")
        verbose_name_plural = _("Product Images")
        ordering = ['order', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'color'],
                condition=Q(is_main=True),
                name='unique_main_image_per_product_color'
            ),
            models.UniqueConstraint(
                fields=['product', 'color'],
                condition=Q(is_hover=True),
                name='unique_hover_image_per_product_color'
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"

    def save(self, *args, **kwargs):
        if self.is_main:
            # Ensure only one main image per product and color
            ProductImage.objects.filter(
                product=self.product,
                color=self.color,
                is_main=True
            ).exclude(pk=self.pk).update(is_main=False)
        if self.is_hover:
            # Ensure only one hover image per product and color
            ProductImage.objects.filter(
                product=self.product,
                color=self.color,
                is_hover=True
            ).exclude(pk=self.pk).update(is_hover=False)
        super().save(*args, **kwargs)


class ProductColor(models.Model):
    """Intermediate model for Product-Color Many-to-Many relationship."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Product"))
    color = models.ForeignKey(Color, on_delete=models.CASCADE, verbose_name=_("Color"))
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_("Stock Quantity"))
    is_available = models.BooleanField(default=True, verbose_name=_("Is Available"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Product Color")
        verbose_name_plural = _("Product Colors")
        unique_together = ['product', 'color']

    def __str__(self):
        return f"{self.product.name} - {self.color.name}"


class ProductSize(models.Model):
    """Intermediate model for Product-Size Many-to-Many relationship."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Product"))
    size = models.ForeignKey(Size, on_delete=models.CASCADE, verbose_name=_("Size"))
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_("Stock Quantity"))
    is_available = models.BooleanField(default=True, verbose_name=_("Is Available"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Product Size")
        verbose_name_plural = _("Product Sizes")
        unique_together = ['product', 'size']

    def __str__(self):
        return f"{self.product.name} - {self.size.name}"


class ProductVariant(models.Model):
    """Represents a specific combination of product, color, and size."""
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE, verbose_name=_("Product"))
    color = models.ForeignKey(Color, on_delete=models.CASCADE, verbose_name=_("Color"))
    size = models.ForeignKey(Size, on_delete=models.CASCADE, verbose_name=_("Size"))
    sku = models.CharField(max_length=100, unique=True, blank=True, verbose_name=_("SKU"))
    stock_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name=_("Stock Quantity"))
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name=_("Price Adjustment"))
    is_available = models.BooleanField(default=True, verbose_name=_("Is Available"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Product Variant")
        verbose_name_plural = _("Product Variants")
        unique_together = ['product', 'color', 'size']

    def __str__(self):
        return f"{self.product.name} - {self.color.name} - {self.size.name}"

    @property
    def get_price(self):
        """Get the effective price for this variant (base product price + adjustment)."""
        base_price = self.product.get_price
        return base_price + self.price_adjustment

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"{self.product.slug}-{self.color.name.lower()}-{self.size.name.lower()}".replace(' ', '-')
        super().save(*args, **kwargs)

# --- Cart Models ---
class Cart(models.Model):
    """Represents a shopping cart, linked to a user or session."""
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True, verbose_name=_("Session Key"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name=_("User")
    )

    total_items_field = models.PositiveIntegerField(default=0, verbose_name=_("Total Items (Cached)"))
    total_price_field = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Total Price (Cached)"))

    class Meta:
        verbose_name = _("Shopping Cart")
        verbose_name_plural = _("Shopping Carts")

    def __str__(self):
        if self.user:
            return f"Cart of {self.user.username}"
        return f"Anonymous Cart ({self.session_key})"

    @property
    def total_items(self):
        """Returns the number of items in the cart (cached value)."""
        return self.total_items_field

    @property
    def total_price(self):
        """Returns the total price of all items in the cart (cached value)."""
        return self.total_price_field

    def get_subtotal(self):
        """
        Returns the total price of items in the cart (the subtotal).
        This method is added to resolve AttributeError for existing code that
        might call cart.get_subtotal(). It returns the cached total_price_field.
        """
        return self.total_price_field

    def update_totals(self):
        """
        Calculates and updates the cached total_items_field and total_price_field.
        """
        total_quantity = self.items.aggregate(total_quantity=models.Sum('quantity'))['total_quantity'] or 0
        total_price = sum(item.get_total_price() for item in self.items.all())
        self.total_items_field = total_quantity
        self.total_price_field = total_price
        self.save()
        return total_quantity, total_price


class CartItem(models.Model):
    """Represents a single item within a shopping cart."""
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE, verbose_name=_("Cart"))
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, verbose_name=_("Product Variant"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name=_("Quantity"))
    added_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Added At"))

    class Meta:
        verbose_name = _("Cart Item")
        verbose_name_plural = _("Cart Items")
        unique_together = ('cart', 'product_variant')

    def __str__(self):
        product_name = self.product_variant.product.name if hasattr(self.product_variant, 'product') and self.product_variant.product else 'N/A'
        color_name = self.product_variant.color.name if hasattr(self.product_variant, 'color') and self.product_variant.color else 'N/A'
        size_name = self.product_variant.size.name if hasattr(self.product_variant, 'size') and self.product_variant.size else 'N/A'
        return f"{self.quantity} x {product_name} ({color_name}, {size_name})"

    def get_total_price(self):
        """
        Calculates the total price for this cart item (quantity * variant price).
        Assumes product_variant has a 'get_price' property.
        """
        return self.quantity * self.product_variant.get_price


# --- Wishlist Models ---
class Wishlist(models.Model):
    """Represents a user's wishlist."""
    user = models.OneToOneField(ReverseUser, on_delete=models.CASCADE, related_name='wishlist', verbose_name=_("User"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Wishlist")
        verbose_name_plural = _("Wishlists")

    def __str__(self):
        return f"Wishlist of {self.user.username}"


class WishlistItem(models.Model):
    """Represents a single product in a wishlist."""
    wishlist = models.ForeignKey(Wishlist, related_name='items', on_delete=models.CASCADE, verbose_name=_("Wishlist"))
    product = models.ForeignKey(Product,
                                on_delete=models.CASCADE, verbose_name=_("Product")) # Wishlist can be for a product, not necessarily a variant
    added_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Added At"))

    class Meta:
        verbose_name = _("Wishlist Item")
        verbose_name_plural = _("Wishlist Items")
        unique_together = ('wishlist', 'product')  # A product can only be in a wishlist once

    def __str__(self):
        return f"{self.product.name} in {self.wishlist.user.username}'s Wishlist"


class HomeSlider(models.Model):
    """Model for managing home page slider images and content."""
    image = models.ImageField(upload_to='slider/', verbose_name=_("Slider Image"))
    image_resized = ImageSpecField(
        source='image',
        processors=[ResizeToFill(1400, 650)], # Adjusted from 1920x600 comment
        format='JPEG',
        options={'quality': 85}
    )

    alt_text = models.CharField(max_length=255, verbose_name=_("Alt Text"))
    heading = models.CharField(max_length=255, verbose_name=_("Heading"))
    subheading = models.TextField(verbose_name=_("Subheading"))
    button_text = models.CharField(max_length=100, verbose_name=_("Button Text"))
    button_url_name = models.URLField(
        max_length=100,
        verbose_name=_("URL Address"),
        help_text=_("Enter the URL Address")
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Home Slider")
        verbose_name_plural = _("Home Sliders")
        ordering = ['order']

    def __str__(self):
        return self.heading


class Coupon(models.Model):
    """Represents a discount coupon."""
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Coupon Code"))
    discount_type = models.CharField(
        max_length=20,
        choices=[('percentage', _('Percentage')), ('fixed', _('Fixed Amount'))],
        default='fixed',
        verbose_name=_("Discount Type")
    )
    value = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text=_("If percentage, enter 0-100. If fixed, enter the amount."),
        verbose_name=_("Discount Value")
    )
    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_("Minimum Order Amount")
    )
    valid_from = models.DateTimeField(verbose_name=_("Valid From"))
    valid_to = models.DateTimeField(verbose_name=_("Valid To"))
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    usage_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Usage Limit"))
    used_count = models.PositiveIntegerField(default=0, verbose_name=_("Used Count"))

    class Meta:
        verbose_name = _("Coupon")
        verbose_name_plural = _("Coupons")
        ordering = ['-valid_from']

    def __str__(self):
        return self.code

    def is_valid(self, cart_subtotal, user=None):
        """Checks if the coupon is currently valid for the given subtotal and user."""
        now = timezone.now()
        if not self.active:
            return False, _("Coupon is not active.")
        if now < self.valid_from:
            return False, _("Coupon is not yet valid.")
        if now > self.valid_to:
            return False, _("Coupon has expired.")
        if cart_subtotal < self.minimum_order_amount:
            # Using f-string for translatable message with a variable
            return False, _("Minimum order amount of %(amount)s required.") % {'amount': self.minimum_order_amount}
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, _("Coupon usage limit exceeded.")

        # Optionally add per-user usage limit here if needed
        # e.g., if self.user_coupon_uses.filter(user=user).count() >= 1: return False, _("Coupon already used by this user.")

        return True, _("Coupon is valid.")

    def get_discount_amount(self, subtotal):
        """Calculates the discount amount based on the coupon type and value."""
        if self.discount_type == 'percentage':
            discount = subtotal * (self.value / 100)
        else: # fixed amount
            discount = self.value
        # Ensure discount does not exceed subtotal (e.g., a $10 fixed discount on a $5 item)
        return min(discount, subtotal)


class Order(models.Model):
    """Represents a customer order."""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('shipped', _('Shipped')),
        ('delivered', _('Delivered')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('paid', _('Paid')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
    ]

    order_number = models.CharField(max_length=32, null=False, editable=False, unique=True, verbose_name=_("Order Number"))
    user = models.ForeignKey(ReverseUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name=_("User"))
    anonymous_access_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True, verbose_name=_("Anonymous Access Token"))

    # Billing Information (copied from shipping for historical record)
    full_name = models.CharField(max_length=255, verbose_name=_("Full Name"))
    email = models.EmailField(max_length=255, verbose_name=_("Email"))
    phone_number = models.CharField(max_length=20, verbose_name=_("Phone Number"))

    # Order Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                   validators=[MinValueValidator(Decimal('0.00'))], verbose_name=_("Subtotal"))
    shipping_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0.00,
                                        validators=[MinValueValidator(Decimal('0.00'))], verbose_name=_("Shipping Cost"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                          validators=[MinValueValidator(Decimal('0.00'))], verbose_name=_("Discount Amount"))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                      validators=[MinValueValidator(Decimal('0.00'))], verbose_name=_("Grand Total"))

    # Coupon relation
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Applied Coupon"))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_("Status"))
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name=_("Payment Status"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    # Stripe Payment Intent ID (for processing payments)
    stripe_pid = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Stripe Payment ID"))

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ['-created_at']

    def _generate_order_number(self):
        """Generates a unique order number using UUID."""
        return uuid.uuid4().hex.upper()

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        # Ensure grand_total is always calculated based on subtotal, shipping, and discount
        self.grand_total = (self.subtotal + self.shipping_cost) - self.discount_amount
        if self.grand_total < 0: # Ensure grand_total doesn't go negative
            self.grand_total = Decimal('0.00')
        if not self.user and not self.anonymous_access_token:
            # Only generate an anonymous token if no user is linked and no token exists
            self.anonymous_access_token = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number

    def get_absolute_url(self):
        return reverse('shop:order_detail', args=[self.order_number])


class OrderItem(models.Model):
    """Represents a single item within an order."""
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name=_("Order"))
    product_variant = models.ForeignKey(ProductVariant,
                                        on_delete=models.PROTECT, verbose_name=_("Product Variant"))
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name=_("Quantity"))
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Price at Purchase"))

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")

    def __str__(self):
        product_name = self.product_variant.product.name if hasattr(self.product_variant, 'product') else 'N/A'
        color_name = self.product_variant.color.name if hasattr(self.product_variant, 'color') and self.product_variant.color else 'N/A'
        size_name = self.product_variant.size.name if hasattr(self.product_variant, 'size') and self.product_variant.size else 'N/A'
        return f"{self.quantity} x {product_name} ({color_name}, {size_name}) in Order {self.order.order_number}"

    def get_total_price(self):
        """Calculates the total price for this order item."""
        return self.quantity * self.price_at_purchase


class ShippingAddress(models.Model):
    """Stores shipping address details, optionally linked to an order or user."""
    CITY_CHOICE = (
        ('OUTSIDE_CAIRO', _('Outside Cairo')),
        ('INSIDE_CAIRO', _('Inside Cairo')),
    )

    order = models.OneToOneField(
        'Order',  # Use string if Order is defined later or import it
        related_name='shipping_address',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Order")
    )
    user = models.ForeignKey(
        'ReverseUser',  # Use string if ReverseUser is defined later or import it
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='shipping_addresses',
        verbose_name=_("User")
    )
    full_name = models.CharField(max_length=255, verbose_name=_("Full Name"))
    email = models.EmailField(null=True,blank=True, verbose_name=_("Email"))
    address_line1 = models.TextField(verbose_name=_("Address Line 1"))
    address_line2 = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Address Line 2"))
    city = models.CharField(max_length=100, choices=CITY_CHOICE, verbose_name=_("City"))
    phone_number = models.CharField(max_length=20, verbose_name=_("Phone Number"))
    is_default = models.BooleanField(default=False, verbose_name=_("Is Default Address"))

    class Meta:
        verbose_name = _("Shipping Address")
        verbose_name_plural = _("Shipping Addresses")
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_user'
            )
        ]

    def __str__(self):
        return f"Shipping Address for {self.full_name}, {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default and self.user:
            # Unset other default addresses for this user
            ShippingAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

class Payment(models.Model):
    """Records payment details for an order."""
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', _('Credit Card')),
        ('paypal', _('PayPal')),
        ('bank_transfer', _('Bank Transfer')),
        ('cash_on_delivery', _('Cash on Delivery')),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment', verbose_name=_("Order"))
    transaction_id = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name=_("Transaction ID"))
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, verbose_name=_("Payment Method"))
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name=_("Amount"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    is_success = models.BooleanField(default=False, verbose_name=_("Is Success"))
    payment_details = models.JSONField(blank=True, null=True, verbose_name=_("Payment Details"))

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ['-timestamp']

    def __str__(self):
        return f"Payment for Order {self.order.order_number} - {self.payment_method}"