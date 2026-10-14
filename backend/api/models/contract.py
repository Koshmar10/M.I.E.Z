from django.db import models

from .department import Department
from .user import User


class Contract(models.Model):
    class Type(models.TextChoices):
        EMPLOYMENT = 'EMPLOYMENT', 'Employment'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'

    contract_number = models.CharField(max_length=40, unique=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contracts')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts'
    )
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.EMPLOYMENT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.contract_number
