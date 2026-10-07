"""Tests for api/workflow_engine.py."""

from django.test import TestCase

from api.models import Notification, User
from api.tests.factories import make_ceo, make_hr, make_workflow
from api.workflow_engine import execute_workflow


class WorkflowEngineTests(TestCase):
    def setUp(self):
        self.ceo = make_ceo(username='ceo4')
        self.hr = make_hr(username='hr2')
        self.workflow = make_workflow(actions=['NOTIFY_MANAGER', 'EMAIL_CEO', 'LOG_TO_AUDIT_TRAIL'])

    def test_failed_action_logs_error_and_continues(self):
        """An action that throws must not stop subsequent actions."""
        from unittest.mock import patch

        def boom(*args, **kwargs):
            raise ValueError('simulated failure')

        with patch('api.workflow_engine._notify_manager', side_effect=boom):
            result = execute_workflow(self.workflow, 'DAILY_AT_TIME', {'message': 'x', 'link': '/'})

        self.assertFalse(result['success'])
        log = result['actions_log']
        # NOTIFY_MANAGER failed
        self.assertFalse(log[0]['success'])
        self.assertIn('simulated failure', log[0]['message'])
        # EMAIL_CEO still ran
        self.assertTrue(log[1]['success'])
        # LOG_TO_AUDIT_TRAIL still ran
        self.assertTrue(log[2]['success'])

    def test_engine_creates_notifications_for_managers(self):
        workflow = make_workflow(actions=['NOTIFY_MANAGER'])
        before = Notification.objects.count()
        execute_workflow(workflow, 'DAILY_AT_TIME', {'message': 'alert', 'link': '/'})
        after = Notification.objects.count()
        # Should have created one notification per CEO/HR user
        managers = User.objects.filter(role__in=('HR', 'CEO')).count()
        self.assertEqual(after - before, managers)

    def test_engine_updates_last_triggered_at(self):
        self.assertIsNone(self.workflow.last_triggered_at)
        execute_workflow(self.workflow, 'DAILY_AT_TIME', {'message': 'x', 'link': '/'})
        self.workflow.refresh_from_db()
        self.assertIsNotNone(self.workflow.last_triggered_at)
