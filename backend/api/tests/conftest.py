"""pytest fixtures available to every test under api/tests/."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """An API client with no logged-in user."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """A user saved in the test database."""
    return get_user_model().objects.create_user(
        username='testuser',
        password='password123',
        email='test@example.com',
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """An API client logged in as `test_user`."""
    api_client.force_authenticate(user=test_user)
    return api_client
