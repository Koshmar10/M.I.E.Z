"""Per-user in-app notifications."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Notification,
)
from ..serializers.notifications import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        unread_count = qs.filter(is_read=False).count()
        page_size = min(int(request.query_params.get('page_size', 20)), 50)
        page = max(int(request.query_params.get('page', 1)), 1)
        total = qs.count()
        results = qs[(page - 1) * page_size : page * page_size]
        serializer = NotificationSerializer(results, many=True)
        return Response(
            {
                'count': total,
                'unread_count': unread_count,
                'results': serializer.data,
            }
        )


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        notification = get_object_or_404(Notification, id=id, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'id': notification.id, 'is_read': True})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        marked = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'marked_read': marked})
