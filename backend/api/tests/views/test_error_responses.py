"""Tests for the API error response format (core/exception_handler.py)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Department, User


class ApiErrorSchemaTests(APITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.ceo = self.user_model.objects.create_user(
            username='ceo_error_schema',
            email='ceo_error_schema@example.com',
            role=User.Role.CEO,
        )
        self.department = Department.objects.create(name='Schema HR', slug='schema-hr')

    def test_unauthenticated_error_has_standard_schema(self):
        response = self.client.get('/api/auth/me/')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data
        assert 'code' in response.data
        assert 'field_errors' in response.data
        assert response.data['field_errors'] == {}

    def test_validation_error_has_standard_schema_with_field_errors(self):
        self.client.force_authenticate(user=self.ceo)

        payload = {
            'last_name': 'Ionescu',
            'email': 'schema.employee@example.com',
            'phone': '+40123456789',
            'department': self.department.id,
            'position': 'Analyst',
            'employment_type': User.EmploymentType.FULL_TIME,
            'start_date': '2025-02-01',
            'salary_ron': '5000.00',
            'address': 'Schema Street 1',
            'is_active': True,
        }
        response = self.client.post('/api/employees/', payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
        assert 'code' in response.data
        assert 'field_errors' in response.data
        assert 'first_name' in response.data['field_errors']

    def test_unhandled_exception_returns_standard_500_schema(self):
        self.client.force_authenticate(user=self.ceo)

        with patch('api.views.auth.UserMeView.get', side_effect=Exception('boom')):
            response = self.client.get('/api/auth/me/')

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == 'Internal server error.'
        assert response.data['code'] == 'server_error'
        assert response.data['field_errors'] == {}
