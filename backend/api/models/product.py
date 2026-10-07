from django.db import models


class Product(models.Model):
    class Category(models.TextChoices):
        ELECTRONICS = 'Electronics', 'Electronics'
        FURNITURE = 'Furniture', 'Furniture'
        LIGHTING = 'Lighting', 'Lighting'
        ACCESSORIES = 'Accessories', 'Accessories'

    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.ELECTRONICS)
    unit_price_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_count = models.PositiveIntegerField(default=0)
    min_stock = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def availability(self):
        stock = int(self.stock_count or 0)
        if stock <= 0:
            return 'Out of Stock'
        if stock < int(self.min_stock or 0):
            return 'Low Stock'
        return 'In Stock'

    def __str__(self) -> str:
        return f'{self.name} ({self.sku})'
