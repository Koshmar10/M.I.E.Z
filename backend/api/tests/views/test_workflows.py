"""Tests for api/views/workflows.py."""

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Workflow, WorkflowLog
from api.tests.factories import make_ceo, make_hr, make_it, make_workflow
from api.workflow_engine import execute_workflow

VALID_PAYLOAD = {
    'name': 'New Order Alert',
    'trigger_type': 'NEW_ORDER_RECEIVED',
    'trigger_config': {},
    'actions': ['NOTIFY_MANAGER', 'EMAIL_CEO'],
    'is_active': True,
}


class WorkflowCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ceo = make_ceo()
        self.client.force_authenticate(user=self.ceo)

    def test_create_workflow_returns_201(self):
        res = self.client.post('/api/workflows/', VALID_PAYLOAD, format='json')
        assert res.status_code == 201
        assert res.data['name'] == 'New Order Alert'
        assert Workflow.objects.filter(name='New Order Alert').exists()

    def test_create_workflow_missing_name_returns_400(self):
        payload = {**VALID_PAYLOAD, 'name': ''}
        res = self.client.post('/api/workflows/', payload, format='json')
        assert res.status_code == 400

    def test_create_workflow_empty_actions_returns_400(self):
        payload = {**VALID_PAYLOAD, 'actions': []}
        res = self.client.post('/api/workflows/', payload, format='json')
        assert res.status_code == 400

    def test_create_workflow_invalid_trigger_type_returns_400(self):
        payload = {**VALID_PAYLOAD, 'trigger_type': 'NOT_A_REAL_TRIGGER'}
        res = self.client.post('/api/workflows/', payload, format='json')
        assert res.status_code == 400

    def test_create_workflow_forbidden_for_non_ceo_hr(self):
        self.client.force_authenticate(user=make_it(username='it1'))
        res = self.client.post('/api/workflows/', VALID_PAYLOAD, format='json')
        assert res.status_code == 403


class WorkflowListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ceo = make_ceo()
        self.client.force_authenticate(user=self.ceo)
        make_workflow(name='W1', is_active=True)
        make_workflow(name='W2', is_active=True)
        make_workflow(name='W3', is_active=False)

    def test_list_workflows_returns_correct_active_count(self):
        res = self.client.get('/api/workflows/')
        assert res.status_code == 200
        assert len(res.data) == 3
        active = [w for w in res.data if w['is_active']]
        assert len(active) == 2

    def test_list_includes_trigger_and_action_labels(self):
        res = self.client.get('/api/workflows/')
        assert res.status_code == 200
        w = res.data[0]
        assert 'trigger_label' in w
        assert 'action_labels' in w


class WorkflowToggleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ceo = make_ceo()
        self.client.force_authenticate(user=self.ceo)
        self.workflow = make_workflow(is_active=True)

    def test_toggle_workflow_flips_is_active_to_false(self):
        res = self.client.patch(
            f'/api/workflows/{self.workflow.id}/toggle/',
            {'is_active': False},
            format='json',
        )
        assert res.status_code == 200
        self.workflow.refresh_from_db()
        assert not self.workflow.is_active

    def test_toggle_workflow_flips_is_active_to_true(self):
        self.workflow.is_active = False
        self.workflow.save()
        res = self.client.patch(
            f'/api/workflows/{self.workflow.id}/toggle/',
            {'is_active': True},
            format='json',
        )
        assert res.status_code == 200
        self.workflow.refresh_from_db()
        assert self.workflow.is_active

    def test_toggle_missing_is_active_returns_400(self):
        res = self.client.patch(f'/api/workflows/{self.workflow.id}/toggle/', {}, format='json')
        assert res.status_code == 400


class WorkflowDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ceo = make_ceo()
        self.client.force_authenticate(user=self.ceo)
        self.workflow = make_workflow()

    def test_delete_workflow_returns_204(self):
        wid = self.workflow.id
        res = self.client.delete(f'/api/workflows/{wid}/')
        assert res.status_code == 204
        assert not Workflow.objects.filter(id=wid).exists()

    def test_delete_nonexistent_returns_404(self):
        res = self.client.delete('/api/workflows/99999/')
        assert res.status_code == 404


class WorkflowRegistryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=make_ceo(username='ceo2'))

    def test_triggers_endpoint_returns_all_types(self):
        res = self.client.get('/api/workflows/triggers/')
        assert res.status_code == 200
        values = [t['value'] for t in res.data]
        assert 'DAILY_AT_TIME' in values
        assert 'NEW_ORDER_RECEIVED' in values
        assert 'NEW_IT_TICKET' in values

    def test_actions_endpoint_returns_all_types(self):
        res = self.client.get('/api/workflows/actions/')
        assert res.status_code == 200
        values = [a['value'] for a in res.data]
        assert 'NOTIFY_MANAGER' in values
        assert 'EMAIL_CEO' in values
        assert 'LOG_TO_AUDIT_TRAIL' in values


class WorkflowLogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ceo = make_ceo(username='ceo3')
        self.hr = make_hr(username='hr1')
        self.workflow = make_workflow()

    def test_workflow_log_created_on_execution(self):
        assert WorkflowLog.objects.count() == 0
        execute_workflow(
            self.workflow,
            'DAILY_AT_TIME',
            {
                'message': 'Test execution',
                'link': '/workflows',
            },
        )
        assert WorkflowLog.objects.count() == 1
        log = WorkflowLog.objects.first()
        assert log.workflow == self.workflow
        assert log.trigger_type == 'DAILY_AT_TIME'
        assert log.success

    def test_workflow_log_endpoint_ceo_only(self):
        execute_workflow(self.workflow, 'DAILY_AT_TIME', {'message': 'test', 'link': '/'})
        self.client.force_authenticate(user=self.ceo)
        res = self.client.get('/api/workflows/logs/')
        assert res.status_code == 200
        assert len(res.data) == 1

    def test_workflow_log_endpoint_forbidden_for_hr(self):
        self.client.force_authenticate(user=self.hr)
        res = self.client.get('/api/workflows/logs/')
        assert res.status_code == 403
