"""Serializers for the AI assistant chat API and conversation sessions."""

from rest_framework import serializers

from ..models import (
    ConversationMessage,
    ConversationSession,
)


class ChatMessageHistorySerializer(serializers.Serializer):
    """Serializer for a single message in conversation history."""

    role = serializers.ChoiceField(choices=['user', 'assistant'])
    content = serializers.CharField()


class AssistantChatRequestSerializer(serializers.Serializer):
    """Serializer for the assistant chat endpoint request."""

    message = serializers.CharField(required=True)
    history = ChatMessageHistorySerializer(many=True, required=False, allow_empty=True)
    current_page = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError('Message cannot be empty.')
        if len(value) > 4000:
            raise serializers.ValidationError('Message cannot exceed 4000 characters.')
        return value


class ToolCallSerializer(serializers.Serializer):
    """Serializer for tool calls made by the agent."""

    tool_name = serializers.CharField()
    arguments = serializers.JSONField()


class AssistantChatResponseSerializer(serializers.Serializer):
    """Serializer for the assistant chat endpoint response."""

    response = serializers.CharField()
    tool_calls_made = ToolCallSerializer(many=True, allow_empty=True)


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSessionSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ConversationSession
        fields = ['id', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationSessionListSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    preview = serializers.SerializerMethodField()

    def get_preview(self, obj):
        first = obj.messages.filter(role='user').first()
        return first.content[:80] if first else ''

    class Meta:
        model = ConversationSession
        fields = ['id', 'created_at', 'updated_at', 'message_count', 'preview']
        read_only_fields = fields
