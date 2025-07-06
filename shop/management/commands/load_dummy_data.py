import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from shop.models import (
    Category, SubCategory, FitType, Brand, Color, Size,
    Product, ProductImage, ProductColor, ProductSize, ProductVariant
)

class Command(BaseCommand):
    help = "Load dummy data into the store app"

    def handle(self, *args, **options):
        self.create_categories()
        self.create_fit_types()
        self.create_brands()
        self.create_colors()
        self.create_sizes()
        self.create_products()

        self.stdout.write(self.style.SUCCESS("Dummy data loaded successfully."))

    def create_categories(self):
        Category.objects.all().delete()
        self.categories = []
        for name in ['Men', 'Women', 'Kids']:
            category = Category.objects.create(name=name)
            for sub in ['T-Shirts', 'Jeans', 'Shoes']:
                self.categories.append(SubCategory.objects.create(
                    category=category,
                    name=sub
                ))

    def create_fit_types(self):
        FitType.objects.all().delete()
        self.fit_types = []
        for name in ['Slim', 'Regular', 'Loose']:
            self.fit_types.append(FitType.objects.create(name=name))

    def create_brands(self):
        Brand.objects.all().delete()
        self.brands = []
        for name in ['Nike', 'Adidas', 'Zara']:
            self.brands.append(Brand.objects.create(name=name))

    def create_colors(self):
        Color.objects.all().delete()
        self.colors = []
        color_defs = [
            ('Red', '#FF0000'),
            ('Green', '#00FF00'),
            ('Blue', '#0000FF'),
            ('Black', '#000000'),
            ('White', '#FFFFFF'),
        ]
        for name, hex_code in color_defs:
            self.colors.append(Color.objects.create(name=name, hex_code=hex_code))

    def create_sizes(self):
        Size.objects.all().delete()
        self.sizes = []
        size_map = {
            'clothing': ['S', 'M', 'L', 'XL'],
            'shoes': ['38', '39', '40', '41', '42'],
        }
        for size_type, names in size_map.items():
            for order, name in enumerate(names):
                self.sizes.append(Size.objects.create(name=name, size_type=size_type, order=order))

    def create_products(self):
        Product.objects.all().delete()
        for i in range(1, 11):
            sub = random.choice(self.categories)
            product = Product.objects.create(
                name=f"Product {i}",
                description="This is a dummy product.",
                short_description="Dummy short description.",
                category=sub.category,
                subcategory=sub,
                fit_type=random.choice(self.fit_types),
                brand=random.choice(self.brands),
                price=Decimal(random.randint(100, 300)),
                sale_price=Decimal(random.randint(80, 120)),
                stock_quantity=random.randint(10, 50),
                is_best_seller=bool(i % 2),
                is_new_arrival=bool(i % 3),
                is_featured=bool(i % 4),
            )
            selected_colors = random.sample(self.colors, k=2)
            selected_sizes = random.sample(self.sizes, k=2)
            for color in selected_colors:
                ProductColor.objects.create(
                    product=product,
                    color=color,
                    stock_quantity=random.randint(5, 20)
                )
            for size in selected_sizes:
                ProductSize.objects.create(
                    product=product,
                    size=size,
                    stock_quantity=random.randint(5, 20)
                )
            for color in selected_colors:
                for size in selected_sizes:
                    ProductVariant.objects.create(
                        product=product,
                        color=color,
                        size=size,
                        stock_quantity=random.randint(5, 15),
                        price_adjustment=Decimal("10.00")
                    )
                    # Add one main image per color
                    ProductImage.objects.create(
                        product=product,
                        alt_text=f"{product.name} - {color.name}",
                        is_main=True,
                        image="products/sample.jpg",  # You must upload a sample.jpg file
                        color=color
                    )
