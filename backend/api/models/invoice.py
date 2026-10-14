from datetime import date

from django.db import models

from .order import Order
from .user import User


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ISSUED = 'ISSUED', 'Issued'
        PAID = 'PAID', 'Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'

    invoice_number = models.CharField(max_length=32, unique=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='invoices')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoices_issued')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    amount_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.invoice_number
