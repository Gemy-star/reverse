import os
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from django.utils.text import slugify
from shop.models import HomeSlider

class Command(BaseCommand):
    help = 'Create dummy HomeSlider entries using existing media/slider images.'

    def handle(self, *args, **kwargs):
        dummy_data = [
            {
                'heading': 'Summer Collection',
                'subheading': 'Refresh your style with our new summer arrivals.',
                'button_text': 'Shop Now',
                'button_url_name': 'shop:category_detail',
                'image_filename': 'slide1.jpg',
            },
            {
                'heading': 'Winter Essentials',
                'subheading': 'Stay warm with our cozy winter picks.',
                'button_text': 'Explore',
                'button_url_name': 'shop:category_detail',
                'image_filename': 'slide2.jpg',
            },
            {
                'heading': 'Clearance Sale',
                'subheading': 'Up to 50% off selected items. Limited time only!',
                'button_text': 'Grab Deal',
                'button_url_name': 'shop:category_detail',
                'image_filename': 'slide3.jpg',
            },
        ]
        #Clear sildes
        HomeSlider.objects.all().delete()
        media_slider_path = os.path.join(settings.MEDIA_ROOT, 'slider')

        for i, data in enumerate(dummy_data, start=1):
            image_path = os.path.join(media_slider_path, data['image_filename'])

            if os.path.exists(image_path):
                with open(image_path, 'rb') as image_file:
                    slider = HomeSlider(
                        heading=data['heading'],
                        subheading=data['subheading'],
                        button_text=data['button_text'],
                        button_url_name=data['button_url_name'],
                        order=i,
                        is_active=True,
                        alt_text=data['heading'],
                    )
                    slider.image.save(data['image_filename'], File(image_file), save=True)
                    self.stdout.write(self.style.SUCCESS(f"Slider '{slider.heading}' created."))
            else:
                self.stdout.write(self.style.ERROR(f"Image not found: {image_path}"))
