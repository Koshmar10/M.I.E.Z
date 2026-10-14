from django.db import models

from .department import Department
from .user import User


class LeaveRequest(models.Model):
    class Type(models.TextChoices):
        VACATION = 'VACATION', 'Vacation'
        SICK = 'SICK', 'Sick'
        UNPAID = 'UNPAID', 'Unpaid'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests'
    )
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.VACATION)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests_approved'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.type} {self.from_date}–{self.to_date} ({self.status}, employee {self.employee_id})'
