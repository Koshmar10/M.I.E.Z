from django.db import models

from .user import User


class Report(models.Model):
    class Category(models.TextChoices):
        SALES = 'Sales', 'Sales'
        FINANCE = 'Finance', 'Finance'
        INVENTORY = 'Inventory', 'Inventory'
        HR = 'HR', 'HR'
        IT = 'IT', 'IT'

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=100, unique=True, default='')
    category = models.CharField(max_length=20, choices=Category.choices, blank=True, default='')
    period = models.CharField(max_length=80, blank=True, default='')
    file_path = models.CharField(max_length=255, blank=True, default='')
    file_size_kb = models.IntegerField(default=0)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_generated'
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    # Store digest data as JSON (for HR digest or similar structured reports)
    digest_data = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return self.name
