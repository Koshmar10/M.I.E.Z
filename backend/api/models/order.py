from datetime import date

from django.db import models

from .customer import Customer
from .user import User


class Order(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Channel(models.TextChoices):
        EMAG = 'EMAG', 'eMAG'
        WEBSITE = 'WEBSITE', 'Website'
        DIRECT = 'DIRECT', 'Direct'

    order_number = models.CharField(max_length=32, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders_created')
    value_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.WEBSITE)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            last_order_number = (
                Order.objects.filter(order_number__startswith='#')
                .order_by('-id')
                .values_list('order_number', flat=True)
                .first()
            )

            next_number = 1
            if last_order_number:
                raw = last_order_number[1:]
                if raw.isdigit():
                    next_number = int(raw) + 1

            self.order_number = f'#{next_number:04d}'

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.order_number
