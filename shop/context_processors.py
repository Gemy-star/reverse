# shop/context_processors.py
from .models import Category

def categories_processor(request):
    return {
        'categories': Category.objects.filter(is_active=True).order_by('name'),
    }