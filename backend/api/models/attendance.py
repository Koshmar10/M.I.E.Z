from datetime import date

from django.db import models

from .user import User


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        REMOTE = 'REMOTE', 'Remote'
        LEAVE = 'LEAVE', 'Leave'

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PRESENT)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'date')]
        ordering = ['-date']

    def __str__(self) -> str:
        return f'{self.date} {self.status} (employee {self.employee_id})'
