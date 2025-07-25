 #apps.py
from django.apps import AppConfig

class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'
    verbose_name = 'Ecommerce Shop'
    def ready(self):
        import shop.signals  # noqa: F401