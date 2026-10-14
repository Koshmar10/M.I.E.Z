from django.db import models


class Workflow(models.Model):
    class TriggerType(models.TextChoices):
        STOCK_BELOW_MINIMUM = 'STOCK_BELOW_MINIMUM', 'Stock Below Minimum'
        NEW_ORDER_RECEIVED = 'NEW_ORDER_RECEIVED', 'New Order Received'
        DAILY_AT_TIME = 'DAILY_AT_TIME', 'Daily At Time'
        WEEKLY_AT_TIME = 'WEEKLY_AT_TIME', 'Weekly At Time'
        NEW_IT_TICKET = 'NEW_IT_TICKET', 'New IT Ticket'
        CONTRACT_EXPIRES = 'CONTRACT_EXPIRES', 'Contract Expires'
        ORDER_EXCEEDS_THRESHOLD = 'ORDER_EXCEEDS_THRESHOLD', 'Order Exceeds Threshold'

    class ActionType(models.TextChoices):
        EMAIL_SUPPLIER = 'EMAIL_SUPPLIER', 'Email Supplier'
        NOTIFY_MANAGER = 'NOTIFY_MANAGER', 'Notify Manager'
        SEND_CONFIRMATION_EMAIL = 'SEND_CONFIRMATION_EMAIL', 'Send Confirmation Email'
        UPDATE_DASHBOARD = 'UPDATE_DASHBOARD', 'Update Dashboard'
        GENERATE_REPORT = 'GENERATE_REPORT', 'Generate Report'
        EMAIL_CEO = 'EMAIL_CEO', 'Email CEO'
        ASSIGN_TO_TEAM_LEAD = 'ASSIGN_TO_TEAM_LEAD', 'Assign to Team Lead'
        POST_TO_CHANNEL = 'POST_TO_CHANNEL', 'Post to Channel'
        LOG_TO_AUDIT_TRAIL = 'LOG_TO_AUDIT_TRAIL', 'Log to Audit Trail'

    name = models.CharField(max_length=160)
    trigger_type = models.CharField(max_length=64, choices=TriggerType.choices, blank=True, default='')
    trigger_config = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
