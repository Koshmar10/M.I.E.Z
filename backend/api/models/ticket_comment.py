from django.db import models

from .ticket import Ticket
from .user import User


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ticket_comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
