"""Serializers for IT assets, tickets and system status."""

from rest_framework import serializers

from ..models import (
    Asset,
    SystemStatus,
    Ticket,
    User,
)
from ..services import BusinessRuleError
from ..services.it import change_ticket_status, check_ticket_transition


class AssetSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True, required=False)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id',
            'name',
            'serial_number',
            'category',
            'assigned_to',
            'assigned_to_username',
            'assigned_to_name',
            'status',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'assigned_to_username', 'assigned_to_name']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to is None:
            return None

        full_name = obj.assigned_to.get_full_name().strip()
        return full_name or obj.assigned_to.username


class TicketSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    requested_for_username = serializers.CharField(source='requested_for.username', read_only=True, allow_null=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_number',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'department',
            'department_name',
            'requested_by',
            'requested_by_username',
            'requested_for',
            'requested_for_username',
            'assigned_to',
            'assigned_to_username',
            'location',
            'created_at',
            'updated_at',
            'resolved_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at', 'resolved_at']


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_number',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'department',
            'requested_for',
            'assigned_to',
            'location',
            'requested_by',
            'created_at',
            'updated_at',
            'resolved_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'status', 'requested_by', 'created_at', 'updated_at', 'resolved_at']
        extra_kwargs = {
            'title': {'required': True, 'allow_blank': False},
            'description': {'required': True, 'allow_blank': False},
            'category': {'required': False},
            'priority': {'required': False},
            'department': {'required': False},
            'requested_for': {'required': False, 'allow_null': True},
            'assigned_to': {'required': False, 'allow_null': True},
            'location': {'required': False},
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['requested_by'] = request.user
        validated_data['status'] = Ticket.Status.OPEN
        return super().create(validated_data)


class TicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'status', 'assigned_to', 'resolved_at']
        read_only_fields = ['id', 'resolved_at']

    def validate_status(self, value):
        if self.instance is not None:
            try:
                check_ticket_transition(self.instance.status, value)
            except BusinessRuleError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return value

    def update(self, instance, validated_data):
        if 'status' not in validated_data:
            return super().update(instance, validated_data)

        request = self.context.get('request')
        actor = request.user if request and request.user.is_authenticated else None
        return change_ticket_status(
            instance,
            validated_data['status'],
            actor=actor,
            assigned_to=validated_data.get('assigned_to'),
        )


class SystemStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemStatus
        fields = ['id', 'name', 'uptime_pct', 'status', 'last_incident_date', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
