from django.db import models

from .user import User


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.INFO)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default='')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
