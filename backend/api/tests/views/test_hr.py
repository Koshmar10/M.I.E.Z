"""Tests for api/views/hr.py."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from model_bakery import baker

from api.models import Attendance, Contract, Department, LeaveRequest, Notification, PayrollEntry, Report, User


@pytest.fixture
def department():
    return baker.make(Department, name='Human Resources', slug='hr')


def _unpaid_payroll_this_month():
    baker.make(PayrollEntry, paid=False, month=timezone.now().date().replace(day=1))


# ── HR digest ────────────────────────────────────────────────────────────────


def test_only_ceo_can_generate_digest(hr_client):
    response = hr_client.post('/api/hr/digest/generate/')
    assert response.status_code == 403


def test_ceo_can_generate_digest(ceo_client):
    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    data = response.json()
    assert data['success']
    assert 'digest' in data
    assert 'report_id' in data


def test_digest_generates_creates_report(ceo_client):
    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    report = Report.objects.get(category=Report.Category.HR)
    assert 'critical' in report.digest_data


def test_digest_sends_notification_for_critical_issues(ceo_client, hr_user):
    _unpaid_payroll_this_month()

    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    assert response.json()['notifications_sent']
    notification = Notification.objects.get(recipient=hr_user)
    assert 'Critical' in notification.title


def test_digest_does_not_send_notification_for_no_issues(ceo_client, hr_user):
    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    assert Notification.objects.filter(recipient=hr_user).count() <= 1


def test_report_stores_full_digest_data(ceo_client, ceo_user):
    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    report = Report.objects.get(id=response.json()['report_id'])
    assert {'week', 'generated_at', 'summary_line'} <= report.digest_data.keys()
    assert report.generated_by == ceo_user


def test_unauthenticated_user_cannot_generate_digest(api_client):
    response = api_client.post('/api/hr/digest/generate/')
    assert response.status_code == 401


def test_notification_sent_to_all_active_hr_managers(ceo_client):
    hr_managers = baker.make(User, role=User.Role.HR, is_active=True, _quantity=3)
    _unpaid_payroll_this_month()

    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    for hr_manager in hr_managers:
        assert Notification.objects.filter(recipient=hr_manager, title__icontains='Critical').exists()


def test_notification_body_uses_summary_line(ceo_client, hr_user):
    _unpaid_payroll_this_month()

    response = ceo_client.post('/api/hr/digest/generate/')

    notification = Notification.objects.get(recipient=hr_user, title__icontains='Critical')
    assert notification.body == response.json()['digest']['summary_line']


def test_notification_includes_link_to_reports(ceo_client, hr_user):
    _unpaid_payroll_this_month()

    response = ceo_client.post('/api/hr/digest/generate/')

    assert response.status_code == 200
    notification = Notification.objects.get(recipient=hr_user, title__icontains='Critical')
    assert '/reports' in notification.link
    assert 'HR' in notification.link


# ── Attendance ───────────────────────────────────────────────────────────────


def test_get_attendance_week_returns_expected_grid(hr_client, department):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    employee = baker.make(User, role=User.Role.SALES, department=department)
    baker.make(Attendance, employee=employee, date=week_start, status=Attendance.Status.PRESENT)
    baker.make(Attendance, employee=employee, date=week_start + timedelta(days=1), status=Attendance.Status.REMOTE)

    response = hr_client.get(f'/api/attendance/?week={week_start.isoformat()}')

    assert response.status_code == 200
    assert response.data['week_start'] == week_start.isoformat()
    assert len(response.data['days']) == 7
    row = next(item for item in response.data['grid'] if item['employee_id'] == employee.id)
    assert row['statuses'][week_start.isoformat()] == Attendance.Status.PRESENT
    assert row['statuses'][(week_start + timedelta(days=1)).isoformat()] == Attendance.Status.REMOTE


# ── Leave requests ───────────────────────────────────────────────────────────


def test_get_leave_requests_returns_expected_rows(hr_client, hr_user, department):
    employee = baker.make(User, role=User.Role.SALES, department=department)
    pending = baker.make(
        LeaveRequest,
        employee=employee,
        department=department,
        type=LeaveRequest.Type.VACATION,
        from_date='2026-05-04',
        to_date='2026-05-06',
        status=LeaveRequest.Status.PENDING,
    )
    approved = baker.make(
        LeaveRequest,
        employee=employee,
        department=department,
        type=LeaveRequest.Type.SICK,
        status=LeaveRequest.Status.APPROVED,
        approved_by=hr_user,
    )

    response = hr_client.get('/api/leave-requests/')

    assert response.status_code == 200
    by_id = {item['id']: item for item in response.data}
    assert by_id[pending.id]['type'] == LeaveRequest.Type.VACATION
    assert by_id[pending.id]['days'] == 3
    assert by_id[approved.id]['status'] == LeaveRequest.Status.APPROVED
    assert by_id[approved.id]['approved_by']['id'] == hr_user.id


def test_get_leave_requests_status_filter_returns_only_matching_rows(hr_client, department):
    baker.make(LeaveRequest, department=department, status=LeaveRequest.Status.PENDING)
    baker.make(LeaveRequest, department=department, status=LeaveRequest.Status.REJECTED)

    response = hr_client.get('/api/leave-requests/?status=approved')

    assert response.status_code == 200
    assert response.data == []


def test_post_leave_requests_creates_pending_status(hr_client, department):
    employee = baker.make(User, role=User.Role.SALES, department=department)
    payload = {
        'employee': employee.id,
        'type': LeaveRequest.Type.VACATION,
        'from_date': '2026-05-01',
        'to_date': '2026-05-03',
        'reason': 'Family event',
    }

    response = hr_client.post('/api/leave-requests/', payload, format='json')

    assert response.status_code == 201
    assert LeaveRequest.objects.get(id=response.data['id']).status == LeaveRequest.Status.PENDING


def test_patch_leave_request_approve_sets_approved_status(hr_client, hr_user, department):
    leave_request = baker.make(LeaveRequest, department=department, status=LeaveRequest.Status.PENDING)

    response = hr_client.patch(f'/api/leave-requests/{leave_request.id}/approve/', {}, format='json')

    assert response.status_code == 200
    leave_request.refresh_from_db()
    assert leave_request.status == LeaveRequest.Status.APPROVED
    assert leave_request.approved_by == hr_user


def test_patch_leave_request_reject_sets_rejected_status(hr_client, hr_user, department):
    leave_request = baker.make(LeaveRequest, department=department, status=LeaveRequest.Status.PENDING)

    response = hr_client.patch(f'/api/leave-requests/{leave_request.id}/reject/', {}, format='json')

    assert response.status_code == 200
    leave_request.refresh_from_db()
    assert leave_request.status == LeaveRequest.Status.REJECTED
    assert leave_request.approved_by == hr_user


# ── Contracts ────────────────────────────────────────────────────────────────


def test_get_contracts_returns_all_with_status_computation(hr_client, department):
    today = timezone.localdate()
    for number, days in [('CTR-100', 90), ('CTR-101', 10), ('CTR-102', -1)]:
        baker.make(Contract, contract_number=number, department=department, end_date=today + timedelta(days=days))

    response = hr_client.get('/api/contracts/')

    assert response.status_code == 200
    status_by_number = {item['contract_number']: item['status'] for item in response.data['contracts']}
    assert status_by_number == {'CTR-100': 'ACTIVE', 'CTR-101': 'EXPIRING', 'CTR-102': 'EXPIRED'}


def test_get_contracts_expiring_filter_returns_only_expiring(hr_client, department):
    today = timezone.localdate()
    baker.make(Contract, department=department, end_date=today + timedelta(days=12))
    baker.make(Contract, department=department, end_date=today + timedelta(days=120))

    response = hr_client.get('/api/contracts/?status=expiring')

    assert response.status_code == 200
    assert [c['status'] for c in response.data['contracts']] == ['EXPIRING']


def test_get_contract_detail_returns_full_contract_payload(hr_client, department):
    today = timezone.localdate()
    employee = baker.make(User, first_name='Ana', last_name='Pop', department=department)
    contract = baker.make(
        Contract,
        employee=employee,
        department=department,
        type=Contract.Type.CONTRACTOR,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=20),
        salary_ron=Decimal('7250.50'),
    )

    response = hr_client.get(f'/api/contracts/{contract.id}/')

    assert response.status_code == 200
    assert response.data['id'] == contract.id
    assert response.data['employee_name'] == 'Ana Pop'
    assert response.data['department'] == department.name
    assert response.data['type'] == Contract.Type.CONTRACTOR
    assert response.data['start_date'] == contract.start_date.isoformat()
    assert response.data['end_date'] == contract.end_date.isoformat()
    assert response.data['salary_ron'] == '7250.50'
    assert response.data['status'] == 'EXPIRING'


def test_get_contract_detail_requires_hr_or_ceo(sales_client):
    contract = baker.make(Contract)
    response = sales_client.get(f'/api/contracts/{contract.id}/')
    assert response.status_code == 403


# ── Upcoming events ──────────────────────────────────────────────────────────


def test_get_upcoming_events_returns_chronological_db_driven_rows(hr_client, department):
    today = timezone.localdate()
    baker.make(Contract, department=department, end_date=today + timedelta(days=3))
    baker.make(User, role=User.Role.IT, department=department, start_date=today + timedelta(days=5))
    baker.make(
        PayrollEntry,
        month=date(today.year, today.month, 1),
        gross_salary_ron=Decimal('4200.00'),
        net_salary_ron=Decimal('4000.00'),
        paid=False,
    )

    response = hr_client.get('/api/hr/upcoming-events/?days=30')

    assert response.status_code == 200
    events = response.data['events']
    assert len(events) >= 3
    assert [e['date'] for e in events] == sorted(e['date'] for e in events)
    contract_event = next(e for e in events if e['type'] == 'CONTRACT_EXPIRY')
    onboarding_event = next(e for e in events if e['type'] == 'ONBOARDING')
    payroll_event = next(e for e in events if e['type'] == 'PAYROLL_PROCESSING')
    assert contract_event['is_warning']
    assert contract_event['link'] == '/hr/contracts'
    assert contract_event['dot_color'] == 'red'
    assert onboarding_event['dot_color'] == 'blue'
    assert payroll_event['dot_color'] == 'blue'
    assert 'unpaid payroll' in payroll_event['description']


def test_get_upcoming_events_requires_hr_or_ceo(sales_client):
    response = sales_client.get('/api/hr/upcoming-events/')
    assert response.status_code == 403


# ── Payroll ──────────────────────────────────────────────────────────────────


def test_get_payroll_month_returns_correct_net_calculation(hr_client, department):
    employee = baker.make(User, role=User.Role.SALES, department=department)
    baker.make(
        PayrollEntry,
        employee=employee,
        month=date(2026, 4, 1),
        gross_salary_ron=Decimal('4000.00'),
        net_salary_ron=Decimal('0.00'),
    )

    response = hr_client.get('/api/payroll/?month=2026-04&bonus=500&deductions=200')

    assert response.status_code == 200
    row = response.data['payroll'][0]
    assert Decimal(row['base_salary_ron']) == Decimal('4000.00')
    assert Decimal(row['bonus_ron']) == Decimal('500')
    assert Decimal(row['deductions_ron']) == Decimal('200')
    assert Decimal(row['net_salary_ron']) == Decimal('4300.00')


def test_payroll_deduction_formula_net_equals_base_plus_bonus_minus_deductions(hr_client, department):
    employee = baker.make(User, role=User.Role.IT, department=department)
    baker.make(
        PayrollEntry,
        employee=employee,
        month=date(2026, 6, 1),
        gross_salary_ron=Decimal('3200.50'),
        net_salary_ron=Decimal('0.00'),
    )

    response = hr_client.get('/api/payroll/?month=2026-06&bonus=150.25&deductions=99.75')

    assert response.status_code == 200
    row = response.data['payroll'][0]
    base, bonus, deductions, net = (
        Decimal(row[key]) for key in ('base_salary_ron', 'bonus_ron', 'deductions_ron', 'net_salary_ron')
    )
    assert net == base + bonus - deductions


# ── CEO summary ──────────────────────────────────────────────────────────────


def test_ceo_hr_summary_counts_it_and_sales_departments(ceo_client):
    it_department = baker.make(Department, name='IT Support', slug='it-support')
    sales_department = baker.make(Department, name='Sales & Marketing', slug='sales-marketing')
    baker.make(User, role=User.Role.IT, department=it_department, is_active=True)
    baker.make(User, role=User.Role.IT, department=it_department, is_active=False)
    baker.make(User, role=User.Role.SALES, department=sales_department, is_active=True)

    response = ceo_client.get('/api/hr/ceo-summary/')

    assert response.status_code == 200
    by_department = {row['department']: row for row in response.data['department_headcount']}
    assert by_department['IT Support']['total'] == 2
    assert by_department['IT Support']['active'] == 1
    assert by_department['Sales & Marketing']['total'] == 1
    assert by_department['Sales & Marketing']['active'] == 1
