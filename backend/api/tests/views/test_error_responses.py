"""Tests for the API error response format (core/exception_handler.py)."""

from unittest.mock import patch

from model_bakery import baker

from api.models import Department, User


def test_unauthenticated_error_has_standard_schema(api_client):
    response = api_client.get('/api/auth/me/')

    assert response.status_code == 401
    assert 'detail' in response.data
    assert 'code' in response.data
    assert response.data['field_errors'] == {}


def test_validation_error_has_standard_schema_with_field_errors(ceo_client):
    payload = {
        'last_name': 'Ionescu',
        'email': 'schema.employee@example.com',
        'phone': '+40123456789',
        'department': baker.make(Department).id,
        'position': 'Analyst',
        'employment_type': User.EmploymentType.FULL_TIME,
        'start_date': '2025-02-01',
        'salary_ron': '5000.00',
        'address': 'Schema Street 1',
        'is_active': True,
    }

    response = ceo_client.post('/api/employees/', payload, format='json')

    assert response.status_code == 400
    assert 'detail' in response.data
    assert 'code' in response.data
    assert 'first_name' in response.data['field_errors']


def test_unhandled_exception_returns_standard_500_schema(ceo_client):
    with patch('api.views.auth.UserMeView.get', side_effect=Exception('boom')):
        response = ceo_client.get('/api/auth/me/')

    assert response.status_code == 500
    assert response.data['detail'] == 'Internal server error.'
    assert response.data['code'] == 'server_error'
    assert response.data['field_errors'] == {}
