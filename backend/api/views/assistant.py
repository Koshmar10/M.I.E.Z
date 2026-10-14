"""The MIEZ AI assistant: chat endpoint and conversation sessions."""

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..agent import AgentRunner, get_registry
from ..models import (
    ConversationMessage,
    ConversationSession,
)
from ..serializers.assistant import (
    AssistantChatRequestSerializer,
    AssistantChatResponseSerializer,
    ConversationSessionListSerializer,
    ConversationSessionSerializer,
)


class AssistantChatView(APIView):
    """
    API endpoint for the MIEZ Assistant chat functionality.

    POST /api/assistant/chat/
    - Accepts a user message and conversation history
    - Instantiates AgentRunner with role-specific system prompt and tools
    - Returns agent response and any tool calls made
    - Rate limited: 20 requests per user per minute
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Handle chat message POST request.

        Request body:
        {
            "message": "user message",
            "history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

        Response:
        {
            "response": "agent response text",
            "tool_calls_made": [
                {"tool_name": "...", "arguments": {...}},
                ...
            ]
        }
        """
        # Check rate limit
        if not self._check_rate_limit(request.user):
            return Response(
                {
                    'detail': 'Rate limit exceeded. Maximum 20 requests per minute per user.',
                    'rate_limit': {
                        'limit': 20,
                        'window_seconds': 60,
                    },
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Validate request
        serializer = AssistantChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message = serializer.validated_data['message']
        session_id = request.data.get('session_id')

        try:
            # Resolve or create session
            if session_id:
                session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
            else:
                session = ConversationSession.objects.create(user=request.user)

            # Build history from DB
            db_messages = session.messages.values('role', 'content')
            history = [{'role': m['role'], 'content': m['content']} for m in db_messages]

            # Persist user message
            ConversationMessage.objects.create(session=session, role='user', content=message)

            # Run agent
            current_page = serializer.validated_data.get('current_page', '')
            agent = AgentRunner(user=request.user, current_page=current_page)
            agent.register_tools(get_registry().get_all())
            result = agent.run(message=message, history=history)

            reply = result.get('response', '')

            # Persist assistant response
            ConversationMessage.objects.create(session=session, role='assistant', content=reply)
            session.save()  # bump updated_at

            response_serializer = AssistantChatResponseSerializer(data=result)
            if not response_serializer.is_valid():
                return Response(
                    {'detail': 'Invalid agent response format'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            data = response_serializer.data
            data['session_id'] = session.id
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error processing chat: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _check_rate_limit(self, user) -> bool:
        """
        Check rate limit for user: max 20 requests per minute.

        Args:
            user: Django User object

        Returns:
            True if within limit, False if exceeded
        """
        cache_key = f'assistant_chat_rate_limit_{user.id}'
        request_count = cache.get(cache_key, 0)

        if request_count >= 20:
            return False

        # Increment and set 60-second expiry
        cache.set(cache_key, request_count + 1, timeout=60)
        return True


class ConversationSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = ConversationSession.objects.filter(user=request.user).prefetch_related('messages')
        serializer = ConversationSessionListSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        session = ConversationSession.objects.create(user=request.user)
        serializer = ConversationSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConversationSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
        serializer = ConversationSessionSerializer(session)
        return Response(serializer.data)

    def delete(self, request, session_id):
        session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
