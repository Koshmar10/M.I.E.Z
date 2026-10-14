from django.db import models


class SystemStatistic(models.Model):
    name = models.CharField(max_length=160, unique=True)
    value = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
