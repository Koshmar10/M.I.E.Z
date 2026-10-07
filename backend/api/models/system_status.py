from django.db import models


class SystemStatus(models.Model):
    class StatusChoices(models.TextChoices):
        ONLINE = 'ONLINE', 'Online'
        DEGRADED = 'DEGRADED', 'Degraded'
        OFFLINE = 'OFFLINE', 'Offline'

    name = models.CharField(max_length=160, unique=True)
    uptime_pct = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    status = models.CharField(max_length=12, choices=StatusChoices.choices, default=StatusChoices.ONLINE)
    last_incident_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.status}'
