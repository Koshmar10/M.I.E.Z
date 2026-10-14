from django.db import models

from .department import Department
from .user import User


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    ticket_number = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=80, blank=True, default='')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tickets_requested')
    requested_for = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_requested_for'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_assigned'
    )
    location = models.CharField(max_length=160, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.ticket_number} {self.title}'

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        if self.status == self.Status.RESOLVED and self.resolved_at is None:
            from django.utils import timezone

            self.resolved_at = timezone.now()

        super().save(*args, **kwargs)

    @classmethod
    def _generate_ticket_number(cls):
        max_number = 0
        for ticket_number in cls.objects.values_list('ticket_number', flat=True):
            if not ticket_number or not ticket_number.startswith('TKT-'):
                continue

            numeric_part = ticket_number.split('TKT-', 1)[1]
            if numeric_part.isdigit():
                max_number = max(max_number, int(numeric_part))

        return f'TKT-{(max_number + 1):05d}'
