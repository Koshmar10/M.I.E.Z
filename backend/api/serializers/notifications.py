"""Serializers for in-app notifications."""

from rest_framework import serializers

from ..models import (
    Notification,
)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'body', 'is_read', 'link', 'created_at']
        read_only_fields = ['id', 'type', 'title', 'body', 'link', 'created_at']
