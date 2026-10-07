"""Tests for api/views/auth.py."""

import pytest
from django.conf import settings

from api.models import User

CREDENTIALS = {'username': 'testuser', 'password': 'testpass123'}


@pytest.fixture(autouse=True)
def user():
    return User.objects.create_user(**CREDENTIALS)


def test_login_sets_session_cookie(api_client):
    response = api_client.post('/api/auth/login/', CREDENTIALS, format='json')

    assert response.status_code == 200
    assert response.data['username'] == CREDENTIALS['username']
    assert response.cookies[settings.SESSION_COOKIE_NAME]['httponly']


def test_protected_route_access(api_client):
    api_client.post('/api/auth/login/', CREDENTIALS, format='json')

    response = api_client.get('/api/auth/me/')

    assert response.status_code == 200
    data = response.json()
    assert data['username'] == CREDENTIALS['username']
    assert 'email' in data
    assert 'message' in data


def test_access_denied_without_cookie(api_client):
    response = api_client.get('/api/auth/me/')
    assert response.status_code == 401


def test_logout_ends_session(api_client):
    api_client.post('/api/auth/login/', CREDENTIALS, format='json')

    assert api_client.post('/api/auth/logout/').status_code == 200
    assert api_client.get('/api/auth/me/').status_code == 401
