# Generated by Django 5.2.4 on 2025-07-25 11:41

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_order_orderitem_payment_shippingaddress'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='total_items_field',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='cart',
            name='total_price_field',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
    ]
