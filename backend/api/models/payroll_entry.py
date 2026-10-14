from django.db import models

from .user import User


class PayrollEntry(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_entries')
    month = models.DateField(help_text='Any date within the payroll month')
    gross_salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'month')]

    def __str__(self) -> str:
        return f'Payroll {self.month} (employee {self.employee_id})'
