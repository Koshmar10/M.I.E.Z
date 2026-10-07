"""Tests for api/views/employees.py: departments and employees."""

import pytest
from model_bakery import baker

from api.models import Department, User


@pytest.fixture
def hr_department():
    return baker.make(Department, name='HR', slug='hr')


@pytest.fixture
def it_department():
    return baker.make(Department, name='IT', slug='it')


@pytest.fixture
def employee_payload(hr_department):
    return {
        'first_name': 'Ana',
        'last_name': 'Popescu',
        'email': 'ana.popescu@example.com',
        'phone': '+40123456789',
        'department': hr_department.id,
        'position': 'Sales Representative',
        'employment_type': User.EmploymentType.FULL_TIME,
        'start_date': '2025-03-10',
        'salary_ron': '5500.00',
        'address': 'Str. Test 1, Bucuresti',
        'is_active': True,
    }


# ── Employees ────────────────────────────────────────────────────────────────


def test_post_employees_valid_payload_returns_201_with_employee_object(ceo_client, employee_payload):
    response = ceo_client.post('/api/employees/', employee_payload, format='json')

    assert response.status_code == 201
    assert response.data['email'] == employee_payload['email']
    assert response.data['first_name'] == employee_payload['first_name']
    assert response.data['department']['id'] == employee_payload['department']


def test_post_employees_missing_required_field_returns_400_with_field_name_in_error(ceo_client, employee_payload):
    del employee_payload['first_name']

    response = ceo_client.post('/api/employees/', employee_payload, format='json')

    assert response.status_code == 400
    assert 'first_name' in response.data['field_errors']


def test_post_employees_duplicate_email_returns_400(ceo_client, employee_payload):
    baker.make(User, email=employee_payload['email'])

    response = ceo_client.post('/api/employees/', employee_payload, format='json')

    assert response.status_code == 400
    assert 'email' in response.data['field_errors']


def test_patch_employee_updates_department_and_role_for_hr_and_ceo(hr_client, hr_department, it_department):
    employee = baker.make(User, role=User.Role.SALES, department=hr_department, is_active=True)

    response = hr_client.patch(
        f'/api/employees/{employee.id}/',
        {
            'first_name': 'Anca',
            'last_name': 'Pop',
            'position': 'IT Specialist',
            'department': it_department.id,
            'phone': '+40222222222',
            'is_active': False,
        },
        format='json',
    )

    assert response.status_code == 200
    assert response.data['first_name'] == 'Anca'
    assert response.data['last_name'] == 'Pop'
    assert response.data['position'] == 'IT Specialist'
    assert response.data['phone'] == '+40222222222'
    assert not response.data['is_active']
    assert response.data['department']['id'] == it_department.id
    employee.refresh_from_db()
    assert employee.role == User.Role.IT


def test_patch_employee_denied_for_non_hr_or_ceo(sales_client):
    employee = baker.make(User, role=User.Role.SALES)
    response = sales_client.patch(f'/api/employees/{employee.id}/', {'first_name': 'Blocked'}, format='json')
    assert response.status_code == 403


def test_get_employees_returns_paginated_list_with_correct_count(ceo_client, hr_department):
    baker.make(User, role=User.Role.SALES, department=hr_department, _quantity=3)

    response = ceo_client.get('/api/employees/?page_size=2')

    assert response.status_code == 200
    assert response.data['count'] == User.objects.count()
    assert len(response.data['results']) == 2


def test_get_employees_department_hr_filters_correctly(ceo_client, hr_department, it_department):
    baker.make(User, department=hr_department, role=User.Role.HR)
    baker.make(User, department=it_department, role=User.Role.IT)

    response = ceo_client.get('/api/employees/?department=hr')

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['department']['slug'] == 'hr'


def test_get_employees_returns_full_list_with_expected_fields(hr_client):
    baker.make(User, role=User.Role.SALES, _quantity=2)

    response = hr_client.get('/api/employees/?page_size=100')

    assert response.status_code == 200
    assert response.data['count'] >= 2
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
    assert expected_keys <= response.data['results'][0].keys()


def test_get_employees_stats_totals_computed_correctly_via_orm(
    ceo_client, ceo_user, hr_user, hr_department, it_department
):
    # The two logged-in users count as inactive, part-time and without a department.
    User.objects.filter(id__in=[ceo_user.id, hr_user.id]).update(is_active=False, full_time=False)
    baker.make(User, department=hr_department, role=User.Role.HR, is_active=True, full_time=True)
    baker.make(User, department=it_department, role=User.Role.IT, is_active=True, full_time=False)
    baker.make(User, department=None, role=User.Role.SALES, is_active=False, full_time=False)

    response = ceo_client.get('/api/employees/stats/')

    assert response.status_code == 200
    assert response.data['total'] == User.objects.count()
    assert response.data['active'] == 2
    assert response.data['full_time'] == 1
    departments = {row['name']: row['count'] for row in response.data['departments']}
    assert departments == {'HR': 1, 'IT': 1, 'Unassigned': 3}


# ── Departments ──────────────────────────────────────────────────────────────


def test_post_departments_ceo_creates_department_returns_201(ceo_client):
    response = ceo_client.post(
        '/api/departments/', {'name': 'Finance', 'slug': 'finance', 'icon': 'Calculator'}, format='json'
    )

    assert response.status_code == 201
    assert response.data['name'] == 'Finance'
    assert Department.objects.filter(slug='finance').exists()


def test_post_departments_non_ceo_role_returns_403(hr_client):
    response = hr_client.post('/api/departments/', {'name': 'Legal', 'slug': 'legal', 'icon': 'Scale'}, format='json')
    assert response.status_code == 403


def test_delete_departments_id_removes_department_returns_204(ceo_client):
    department = baker.make(Department)

    response = ceo_client.delete(f'/api/departments/{department.id}/')

    assert response.status_code == 204
    assert not Department.objects.filter(id=department.id).exists()
