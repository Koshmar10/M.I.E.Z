from django.db import models

from .user import User


class Asset(models.Model):
    class Category(models.TextChoices):
        LAPTOP = 'LAPTOP', 'Laptop'
        MONITOR = 'MONITOR', 'Monitor'
        PHONE = 'PHONE', 'Phone'
        PERIPHERAL = 'PERIPHERAL', 'Peripheral'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        RETIRED = 'RETIRED', 'Retired'

    name = models.CharField(max_length=160)
    serial_number = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.name} ({self.serial_number})'
