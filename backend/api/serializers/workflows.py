"""Serializers for workflows and their execution log."""

from rest_framework import serializers

from ..models import (
    Workflow,
    WorkflowLog,
)


class WorkflowSerializer(serializers.ModelSerializer):
    trigger_label = serializers.SerializerMethodField()
    action_labels = serializers.SerializerMethodField()

    class Meta:
        model = Workflow
        fields = [
            'id',
            'name',
            'trigger_type',
            'trigger_label',
            'trigger_config',
            'actions',
            'action_labels',
            'is_active',
            'last_triggered_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'last_triggered_at', 'created_at', 'updated_at']

    def get_trigger_label(self, obj):
        return dict(Workflow.TriggerType.choices).get(obj.trigger_type, obj.trigger_type)

    def get_action_labels(self, obj):
        label_map = dict(Workflow.ActionType.choices)
        result = []
        for a in obj.actions or []:
            if isinstance(a, str):
                result.append(label_map.get(a, a))
            elif isinstance(a, dict):
                key = a.get('type') or a.get('action') or ''
                result.append(label_map.get(key, key))
        return result


class WorkflowWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = ['name', 'trigger_type', 'trigger_config', 'actions', 'is_active']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_trigger_type(self, value):
        valid = [c[0] for c in Workflow.TriggerType.choices]
        if value not in valid:
            raise serializers.ValidationError(f'Must be one of: {", ".join(valid)}')
        return value

    def validate_actions(self, value):
        if not value:
            raise serializers.ValidationError('Must have at least one action.')
        valid = [c[0] for c in Workflow.ActionType.choices]
        for a in value:
            if a not in valid:
                raise serializers.ValidationError(f'"{a}" is not a valid action type.')
        return value


class WorkflowLogSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        model = WorkflowLog
        fields = ['id', 'workflow', 'workflow_name', 'triggered_at', 'trigger_type', 'actions_log', 'success']
        read_only_fields = fields
