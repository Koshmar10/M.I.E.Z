from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CEO = 'CEO', 'CEO'
        HR = 'HR', 'HR'
        SALES = 'SALES', 'Sales Rep'
        IT = 'IT', 'IT Technician'
        INVENTORY = 'INVENTORY', 'Inventory Manager'

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-time'
        PART_TIME = 'PART_TIME', 'Part-time'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CEO,
    )
    department = models.ForeignKey(
        'Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    phone = models.CharField(max_length=20, default='')
    position = models.CharField(max_length=120, default='')
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    start_date = models.DateField(default=date.today)
    salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(default='')
    full_time = models.BooleanField(default=True)

    class Meta:
        db_table = 'users'
