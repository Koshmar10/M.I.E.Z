"""Tests for api/views/workflows.py."""

from model_bakery import baker

from api.models import Workflow, WorkflowLog
from api.workflow_engine import execute_workflow

VALID_PAYLOAD = {
    'name': 'New Order Alert',
    'trigger_type': 'NEW_ORDER_RECEIVED',
    'trigger_config': {},
    'actions': ['NOTIFY_MANAGER', 'EMAIL_CEO'],
    'is_active': True,
}


def test_create_workflow_returns_201(ceo_client):
    res = ceo_client.post('/api/workflows/', VALID_PAYLOAD, format='json')
    assert res.status_code == 201
    assert res.data['name'] == 'New Order Alert'
    assert Workflow.objects.filter(name='New Order Alert').exists()


def test_create_workflow_missing_name_returns_400(ceo_client):
    res = ceo_client.post('/api/workflows/', {**VALID_PAYLOAD, 'name': ''}, format='json')
    assert res.status_code == 400


def test_create_workflow_empty_actions_returns_400(ceo_client):
    res = ceo_client.post('/api/workflows/', {**VALID_PAYLOAD, 'actions': []}, format='json')
    assert res.status_code == 400


def test_create_workflow_invalid_trigger_type_returns_400(ceo_client):
    res = ceo_client.post('/api/workflows/', {**VALID_PAYLOAD, 'trigger_type': 'NOT_A_REAL_TRIGGER'}, format='json')
    assert res.status_code == 400


def test_create_workflow_forbidden_for_non_ceo_hr(it_client):
    res = it_client.post('/api/workflows/', VALID_PAYLOAD, format='json')
    assert res.status_code == 403


def test_list_workflows_returns_correct_active_count(ceo_client):
    baker.make(Workflow, is_active=True, _quantity=2)
    baker.make(Workflow, is_active=False)

    res = ceo_client.get('/api/workflows/')

    assert res.status_code == 200
    assert len(res.data) == 3
    assert len([w for w in res.data if w['is_active']]) == 2


def test_list_includes_trigger_and_action_labels(ceo_client):
    baker.make(Workflow)

    res = ceo_client.get('/api/workflows/')

    assert res.status_code == 200
    assert 'trigger_label' in res.data[0]
    assert 'action_labels' in res.data[0]


def test_toggle_workflow_flips_is_active_to_false(ceo_client):
    workflow = baker.make(Workflow, is_active=True)

    res = ceo_client.patch(f'/api/workflows/{workflow.id}/toggle/', {'is_active': False}, format='json')

    assert res.status_code == 200
    workflow.refresh_from_db()
    assert not workflow.is_active


def test_toggle_workflow_flips_is_active_to_true(ceo_client):
    workflow = baker.make(Workflow, is_active=False)

    res = ceo_client.patch(f'/api/workflows/{workflow.id}/toggle/', {'is_active': True}, format='json')

    assert res.status_code == 200
    workflow.refresh_from_db()
    assert workflow.is_active


def test_toggle_missing_is_active_returns_400(ceo_client):
    workflow = baker.make(Workflow)
    res = ceo_client.patch(f'/api/workflows/{workflow.id}/toggle/', {}, format='json')
    assert res.status_code == 400


def test_delete_workflow_returns_204(ceo_client):
    workflow = baker.make(Workflow)

    res = ceo_client.delete(f'/api/workflows/{workflow.id}/')

    assert res.status_code == 204
    assert not Workflow.objects.filter(id=workflow.id).exists()


def test_delete_nonexistent_returns_404(ceo_client):
    res = ceo_client.delete('/api/workflows/99999/')
    assert res.status_code == 404


def test_triggers_endpoint_returns_all_types(ceo_client):
    res = ceo_client.get('/api/workflows/triggers/')
    assert res.status_code == 200
    values = [t['value'] for t in res.data]
    assert 'DAILY_AT_TIME' in values
    assert 'NEW_ORDER_RECEIVED' in values
    assert 'NEW_IT_TICKET' in values


def test_actions_endpoint_returns_all_types(ceo_client):
    res = ceo_client.get('/api/workflows/actions/')
    assert res.status_code == 200
    values = [a['value'] for a in res.data]
    assert 'NOTIFY_MANAGER' in values
    assert 'EMAIL_CEO' in values
    assert 'LOG_TO_AUDIT_TRAIL' in values


def test_workflow_log_created_on_execution():
    workflow = baker.make(Workflow, actions=['NOTIFY_MANAGER'])
    assert WorkflowLog.objects.count() == 0

    execute_workflow(workflow, 'DAILY_AT_TIME', {'message': 'Test execution', 'link': '/workflows'})

    assert WorkflowLog.objects.count() == 1
    log = WorkflowLog.objects.first()
    assert log.workflow == workflow
    assert log.trigger_type == 'DAILY_AT_TIME'
    assert log.success


def test_workflow_log_endpoint_ceo_only(ceo_client):
    execute_workflow(
        baker.make(Workflow, actions=['NOTIFY_MANAGER']), 'DAILY_AT_TIME', {'message': 'test', 'link': '/'}
    )

    res = ceo_client.get('/api/workflows/logs/')

    assert res.status_code == 200
    assert len(res.data) == 1


def test_workflow_log_endpoint_forbidden_for_hr(hr_client):
    res = hr_client.get('/api/workflows/logs/')
    assert res.status_code == 403
