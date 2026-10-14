from django.db import models

from .order import Order
from .product import Product


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [('order', 'product')]

    def __str__(self) -> str:
        return f'{self.quantity} × product {self.product_id} (order {self.order_id})'
