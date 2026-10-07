"""pytest fixtures shared by every test under api/tests/.

Every test gets database access. Create test data inline with `baker.make(Model, field=...)`,
setting only the fields the test is about.
"""

import pytest
from rest_framework.test import APIClient

from api.models import User


@pytest.fixture(autouse=True)
def _db(db):
    """Give every test database access."""


def _user(role: str) -> User:
    name = role.lower()
    return User.objects.create_user(username=name, email=f'{name}@test.com', password='password123', role=role)


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def api_client():
    """An API client with no logged-in user."""
    return APIClient()


@pytest.fixture
def ceo_user():
    return _user(User.Role.CEO)


@pytest.fixture
def hr_user():
    return _user(User.Role.HR)


@pytest.fixture
def it_user():
    return _user(User.Role.IT)


@pytest.fixture
def sales_user():
    return _user(User.Role.SALES)


@pytest.fixture
def inventory_user():
    return _user(User.Role.INVENTORY)


@pytest.fixture
def ceo_client(ceo_user):
    return _client_for(ceo_user)


@pytest.fixture
def hr_client(hr_user):
    return _client_for(hr_user)


@pytest.fixture
def it_client(it_user):
    return _client_for(it_user)


@pytest.fixture
def sales_client(sales_user):
    return _client_for(sales_user)


@pytest.fixture
def inventory_client(inventory_user):
    return _client_for(inventory_user)
