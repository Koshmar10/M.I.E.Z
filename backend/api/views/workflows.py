"""Workflow automation: CRUD, toggling, available triggers/actions and the execution log."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    User,
    Workflow,
    WorkflowLog,
)
from ..permissions import role_required
from ..serializers.workflows import WorkflowLogSerializer, WorkflowSerializer, WorkflowWriteSerializer


class WorkflowListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
        workflows = Workflow.objects.all().order_by('name')
        return Response(WorkflowSerializer(workflows, many=True).data)

    def post(self, request):
        ser = WorkflowWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        workflow = ser.save()
        return Response(WorkflowSerializer(workflow).data, status=201)


class WorkflowDetailView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def _get_workflow(self, id):
        return get_object_or_404(Workflow, id=id)

    def patch(self, request, id):
        workflow = self._get_workflow(id)
        ser = WorkflowWriteSerializer(workflow, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        workflow = ser.save()
        return Response(WorkflowSerializer(workflow).data)

    def delete(self, request, id):
        workflow = self._get_workflow(id)
        workflow.delete()
        return Response(status=204)


class WorkflowToggleView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def patch(self, request, id):
        workflow = get_object_or_404(Workflow, id=id)
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response({'detail': 'is_active required.'}, status=400)
        workflow.is_active = bool(is_active)
        workflow.save(update_fields=['is_active', 'updated_at'])
        return Response({'id': workflow.id, 'is_active': workflow.is_active})


class WorkflowTriggersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{'value': v, 'label': l} for v, l in Workflow.TriggerType.choices])


class WorkflowActionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{'value': v, 'label': l} for v, l in Workflow.ActionType.choices])


class WorkflowLogListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO)]

    def get(self, request):
        logs = WorkflowLog.objects.select_related('workflow').order_by('-triggered_at')[:100]
        return Response(WorkflowLogSerializer(logs, many=True).data)
