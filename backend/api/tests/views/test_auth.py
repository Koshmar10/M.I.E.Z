"""Tests for api/views/auth.py."""

import pytest
from django.conf import settings

from api.models import User

ACCESS_COOKIE = settings.SIMPLE_JWT['AUTH_COOKIE']
REFRESH_COOKIE = settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH']
CREDENTIALS = {'username': 'testuser', 'password': 'testpass123'}


@pytest.fixture(autouse=True)
def user():
    return User.objects.create_user(**CREDENTIALS)


def test_login_sets_cookies(api_client):
    response = api_client.post('/api/auth/login/', CREDENTIALS, format='json')

    assert response.status_code == 200
    assert ACCESS_COOKIE in response.cookies
    assert REFRESH_COOKIE in response.cookies
    assert response.cookies[ACCESS_COOKIE]['httponly']


def test_protected_route_access(api_client):
    api_client.post('/api/auth/login/', CREDENTIALS)

    response = api_client.get('/api/auth/me/')

    assert response.status_code == 200
    data = response.json()
    assert data['username'] == CREDENTIALS['username']
    assert 'email' in data
    assert 'message' in data


def test_access_denied_without_cookie(api_client):
    response = api_client.get('/api/auth/me/')
    assert response.status_code == 401


def test_logout_clears_cookies(api_client):
    api_client.post('/api/auth/login/', CREDENTIALS)

    response = api_client.post('/api/auth/logout/')

    assert response.cookies[ACCESS_COOKIE].value == ''
