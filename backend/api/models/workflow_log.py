from django.db import models

from .workflow import Workflow


class WorkflowLog(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='logs')
    triggered_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(max_length=64, blank=True, default='')
    actions_log = models.JSONField(default=list, blank=True)
    success = models.BooleanField(default=True)
