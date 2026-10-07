"""Tests for api/views/employees.py: departments and employees."""

from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import (
    Department,
    User,
)
from api.tests.base import HrEndpointsTestCase


class EmployeeDepartmentCrudTests(APITestCase):
    def setUp(self):
        self.ceo_user = User.objects.create_user(
            username='ceo_employee_crud',
            email='ceo_employee_crud@example.com',
            role=User.Role.CEO,
        )
        self.hr_user = User.objects.create_user(
            username='hr_employee_crud',
            email='hr_employee_crud@example.com',
            role=User.Role.HR,
        )
        self.hr_department = Department.objects.create(name='HR', slug='hr')
        self.it_department = Department.objects.create(name='IT', slug='it')

        self.valid_payload = {
            'first_name': 'Ana',
            'last_name': 'Popescu',
            'email': 'ana.popescu@example.com',
            'phone': '+40123456789',
            'department': self.hr_department.id,
            'position': 'Sales Representative',
            'employment_type': User.EmploymentType.FULL_TIME,
            'start_date': '2025-03-10',
            'salary_ron': '5500.00',
            'address': 'Str. Test 1, Bucuresti',
            'is_active': True,
        }

    def test_post_employees_valid_payload_returns_201_with_employee_object(self):
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.post('/api/employees/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], self.valid_payload['email'])
        self.assertEqual(response.data['first_name'], self.valid_payload['first_name'])
        self.assertEqual(response.data['department']['id'], self.valid_payload['department'])

    def test_post_employees_missing_required_field_returns_400_with_field_name_in_error(self):
        self.client.force_authenticate(user=self.ceo_user)
        payload = dict(self.valid_payload)
        payload.pop('first_name')

        response = self.client.post('/api/employees/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', response.data['field_errors'])

    def test_post_employees_duplicate_email_returns_400(self):
        User.objects.create_user(
            username='existing_employee_email',
            email=self.valid_payload['email'],
            role=User.Role.SALES,
        )
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.post('/api/employees/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data['field_errors'])

    def test_patch_employee_updates_department_and_role_for_hr_and_ceo(self):
        employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Ana',
            last_name='Popescu',
            phone='+40111111111',
            position='Sales Representative',
            is_active=True,
        )
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.patch(
            f'/api/employees/{employee.id}/',
            {
                'first_name': 'Anca',
                'last_name': 'Pop',
                'position': 'IT Specialist',
                'department': self.it_department.id,
                'phone': '+40222222222',
                'is_active': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Anca')
        self.assertEqual(response.data['last_name'], 'Pop')
        self.assertEqual(response.data['position'], 'IT Specialist')
        self.assertEqual(response.data['phone'], '+40222222222')
        self.assertFalse(response.data['is_active'])
        self.assertEqual(response.data['department']['id'], self.it_department.id)

        employee.refresh_from_db()
        self.assertEqual(employee.role, User.Role.IT)

    def test_patch_employee_denied_for_non_hr_or_ceo(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        sales_user = baker.make(User, role=User.Role.SALES)
        self.client.force_authenticate(user=sales_user)

        response = self.client.patch(
            f'/api/employees/{employee.id}/',
            {'first_name': 'Blocked'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_employees_returns_paginated_list_with_correct_count(self):
        baker.make(User, _quantity=3, department=self.hr_department, role=User.Role.SALES)
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/?page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], User.objects.count())
        self.assertEqual(len(response.data['results']), 2)

    def test_get_employees_department_hr_filters_correctly(self):
        baker.make(User, department=self.hr_department, role=User.Role.HR)
        baker.make(User, department=self.it_department, role=User.Role.IT)
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/?department=hr')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['department']['slug'], 'hr')

    def test_get_employees_stats_totals_computed_correctly_via_orm(self):
        self.ceo_user.is_active = False
        self.ceo_user.full_time = False
        self.ceo_user.save(update_fields=['is_active', 'full_time'])

        self.hr_user.is_active = False
        self.hr_user.full_time = False
        self.hr_user.save(update_fields=['is_active', 'full_time'])

        baker.make(
            User,
            department=self.hr_department,
            role=User.Role.HR,
            is_active=True,
            full_time=True,
        )
        baker.make(
            User,
            department=self.it_department,
            role=User.Role.IT,
            is_active=True,
            full_time=False,
        )
        baker.make(
            User,
            department=None,
            role=User.Role.SALES,
            is_active=False,
            full_time=False,
        )
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/stats/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], User.objects.count())
        self.assertEqual(response.data['active'], 2)
        self.assertEqual(response.data['full_time'], 1)

        departments = {row['name']: row['count'] for row in response.data['departments']}
        self.assertEqual(departments['HR'], 1)
        self.assertEqual(departments['IT'], 1)
        self.assertEqual(departments['Unassigned'], 3)

    def test_post_departments_ceo_creates_department_returns_201(self):
        self.client.force_authenticate(user=self.ceo_user)

        payload = {
            'name': 'Finance',
            'slug': 'finance',
            'icon': 'Calculator',
        }
        response = self.client.post('/api/departments/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertTrue(Department.objects.filter(slug='finance').exists())

    def test_post_departments_non_ceo_role_returns_403(self):
        self.client.force_authenticate(user=self.hr_user)

        payload = {
            'name': 'Legal',
            'slug': 'legal',
            'icon': 'Scale',
        }
        response = self.client.post('/api/departments/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_departments_id_removes_department_returns_204(self):
        department = Department.objects.create(name='Operations', slug='operations')
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.delete(f'/api/departments/{department.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Department.objects.filter(id=department.id).exists())


class TestHrEmployeesEndpoint(HrEndpointsTestCase):
    def test_get_employees_returns_full_list_with_expected_fields(self):
        baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Ana',
            last_name='Pop',
            username='ana.pop',
            email='ana.pop@example.com',
            employment_type=User.EmploymentType.FULL_TIME,
            full_time=True,
            is_active=True,
        )
        baker.make(
            User,
            role=User.Role.IT,
            department=self.hr_department,
            first_name='Mihai',
            last_name='Ionescu',
            username='mihai.ionescu',
            email='mihai.ionescu@example.com',
            employment_type=User.EmploymentType.CONTRACTOR,
            full_time=False,
            is_active=False,
        )

        response = self.hr_client.get('/api/employees/?page_size=100')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 2)
        self.assertGreaterEqual(len(response.data['results']), 2)

        first = response.data['results'][0]
        expected_keys = {
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'position',
            'employment_type',
            'start_date',
            'salary_ron',
            'address',
            'role',
            'is_active',
            'full_time',
            'department',
        }
        self.assertTrue(expected_keys.issubset(first.keys()))
