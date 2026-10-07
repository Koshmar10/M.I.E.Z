from django.db import models


class Customer(models.Model):
    class Tier(models.TextChoices):
        GOLD = 'Gold', 'Gold'
        SILVER = 'Silver', 'Silver'
        BRONZE = 'Bronze', 'Bronze'
        INDIVIDUAL = 'Individual', 'Individual'

    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=160, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    location = models.CharField(max_length=160, blank=True, default='')
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.INDIVIDUAL)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
