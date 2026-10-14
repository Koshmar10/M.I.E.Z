from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    icon = models.CharField(max_length=40, default='Building2')
    created_at = models.DateTimeField(auto_now_add=True)

    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name
