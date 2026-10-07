"""Tests for api/workflow_engine.py."""

from unittest.mock import patch

from model_bakery import baker

from api.models import Notification, User, Workflow
from api.workflow_engine import execute_workflow


def test_failed_action_logs_error_and_continues(ceo_user, hr_user):
    """An action that throws must not stop subsequent actions."""
    workflow = baker.make(Workflow, actions=['NOTIFY_MANAGER', 'EMAIL_CEO', 'LOG_TO_AUDIT_TRAIL'])

    with patch('api.workflow_engine._notify_manager', side_effect=ValueError('simulated failure')):
        result = execute_workflow(workflow, 'DAILY_AT_TIME', {'message': 'x', 'link': '/'})

    assert not result['success']
    notify, email_ceo, audit = result['actions_log']
    assert not notify['success']
    assert 'simulated failure' in notify['message']
    assert email_ceo['success']
    assert audit['success']


def test_engine_creates_notifications_for_managers(ceo_user, hr_user):
    workflow = baker.make(Workflow, actions=['NOTIFY_MANAGER'])

    execute_workflow(workflow, 'DAILY_AT_TIME', {'message': 'alert', 'link': '/'})

    # one notification per CEO/HR user
    assert Notification.objects.count() == User.objects.filter(role__in=('HR', 'CEO')).count()


def test_engine_updates_last_triggered_at():
    workflow = baker.make(Workflow, actions=['LOG_TO_AUDIT_TRAIL'])
    assert workflow.last_triggered_at is None

    execute_workflow(workflow, 'DAILY_AT_TIME', {'message': 'x', 'link': '/'})

    workflow.refresh_from_db()
    assert workflow.last_triggered_at is not None
