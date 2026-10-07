"""Serializers for reports."""

from rest_framework import serializers

from ..models import (
    Report,
)


class ReportSerializer(serializers.ModelSerializer):
    file_available = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'period',
            'file_size_kb',
            'generated_at',
            'file_available',
            'digest_data',
        ]

    def get_file_available(self, obj):
        return bool(obj.file_path)
