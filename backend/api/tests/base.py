"""Shared TestCase base classes with common fixtures."""

from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APITestCase

from api.models import Department, User


class DigestTestCase(APITestCase):
    def setUp(self):
        self.ceo_user = baker.make(
            User,
            role=User.Role.CEO,
            username='ceo_test',
            email='ceo@example.com',
            is_active=True,
        )
        self.hr_manager = baker.make(
            User,
            role=User.Role.HR,
            username='hr_manager',
            email='hr@example.com',
            is_active=True,
        )
        self.hr_department = baker.make(Department, name='Human Resources', slug='hr')
        self.sales_department = baker.make(Department, name='Sales', slug='sales')
        self.ceo_client = APITestCase.client_class()
        self.ceo_client.force_authenticate(user=self.ceo_user)

    def _current_month(self):
        return timezone.now().date().replace(day=1)


class HrEndpointsTestCase(APITestCase):
    def setUp(self):
        self.hr_user = baker.make(
            User,
            role=User.Role.HR,
            username='hr_test_user',
            email='hr_test_user@example.com',
        )
        self.hr_client = APITestCase.client_class()
        self.hr_client.force_authenticate(user=self.hr_user)
        self.hr_department = baker.make(Department, name='Human Resources', slug='hr')
