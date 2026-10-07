"""Tests for api/views/hr.py."""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Attendance, Contract, Department, LeaveRequest, Notification, PayrollEntry, Report, User
from api.tests.base import DigestTestCase, HrEndpointsTestCase


class TestHrDigestGenerateView(DigestTestCase):
    def test_only_ceo_can_generate_digest(self):
        hr_client = APITestCase.client_class()
        hr_client.force_authenticate(user=self.hr_manager)

        response = hr_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_ceo_can_generate_digest(self):
        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert 'success' in data
        assert data['success']
        assert 'digest' in data
        assert 'report_id' in data

    def test_digest_generates_creates_report(self):
        initial_count = Report.objects.filter(category=Report.Category.HR).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        final_count = Report.objects.filter(category=Report.Category.HR).count()
        assert final_count == initial_count + 1

        report = Report.objects.filter(category=Report.Category.HR).latest('generated_at')
        assert report.digest_data is not None
        assert 'critical' in report.digest_data

    def test_digest_sends_notification_for_critical_issues(self):
        current_month = self._current_month()
        baker.make(PayrollEntry, paid=False, month=current_month)

        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data['notifications_sent']

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        assert final_notifications == initial_notifications + 1

        notification = Notification.objects.filter(recipient=self.hr_manager).latest('created_at')
        assert 'Critical' in notification.title

    def test_digest_does_not_send_notification_for_no_issues(self):
        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        assert final_notifications - initial_notifications <= 1

    def test_report_stores_full_digest_data(self):
        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        report = Report.objects.get(id=response.json()['report_id'])
        assert report.digest_data is not None
        assert 'week' in report.digest_data
        assert 'generated_at' in report.digest_data
        assert 'summary_line' in report.digest_data
        assert report.generated_by == self.ceo_user

    def test_unauthenticated_user_cannot_generate_digest(self):
        client = APITestCase.client_class()
        response = client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDigestNotifications(DigestTestCase):
    def test_notification_sent_to_all_active_hr_managers(self):
        hr_managers = [baker.make(User, role=User.Role.HR, is_active=True) for _ in range(3)]
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        for hr_manager in hr_managers:
            assert Notification.objects.filter(recipient=hr_manager, title__icontains='Critical').exists()

    def test_notification_body_uses_summary_line(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        digest = response.json()['digest']
        summary = digest['summary_line']

        notification = Notification.objects.filter(
            recipient=self.hr_manager,
            title__icontains='Critical',
        ).latest('created_at')

        assert notification.body == summary

    def test_notification_includes_link_to_reports(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        assert response.status_code == status.HTTP_200_OK

        notification = Notification.objects.filter(
            recipient=self.hr_manager,
            title__icontains='Critical',
        ).latest('created_at')

        assert '/reports' in notification.link
        assert 'HR' in notification.link


class TestHrAttendanceEndpoint(HrEndpointsTestCase):
    def test_get_attendance_week_returns_expected_grid(self):
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())

        employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Elena',
            last_name='Vasilescu',
            username='elena.v',
        )

        baker.make(Attendance, employee=employee, date=week_start, status=Attendance.Status.PRESENT)
        baker.make(Attendance, employee=employee, date=week_start + timedelta(days=1), status=Attendance.Status.REMOTE)

        response = self.hr_client.get(f'/api/attendance/?week={week_start.isoformat()}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['week_start'] == week_start.isoformat()
        assert len(response.data['days']) == 7

        row = next(item for item in response.data['grid'] if item['employee_id'] == employee.id)
        assert row['statuses'][week_start.isoformat()] == Attendance.Status.PRESENT
        assert row['statuses'][(week_start + timedelta(days=1)).isoformat()] == Attendance.Status.REMOTE


class TestHrLeaveRequestsEndpoint(HrEndpointsTestCase):
    def test_get_leave_requests_returns_expected_rows(self):
        employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Ana',
            last_name='Pop',
            username='ana.pop',
        )
        pending_request = baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            type=LeaveRequest.Type.VACATION,
            from_date='2026-05-04',
            to_date='2026-05-06',
            status=LeaveRequest.Status.PENDING,
        )
        approved_request = baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            type=LeaveRequest.Type.SICK,
            from_date='2026-05-07',
            to_date='2026-05-08',
            status=LeaveRequest.Status.APPROVED,
            approved_by=self.hr_user,
        )

        response = self.hr_client.get('/api/leave-requests/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

        by_id = {item['id']: item for item in response.data}
        assert by_id[pending_request.id]['type'] == LeaveRequest.Type.VACATION
        assert by_id[pending_request.id]['days'] == 3
        assert by_id[approved_request.id]['status'] == LeaveRequest.Status.APPROVED
        assert by_id[approved_request.id]['approved_by']['id'] == self.hr_user.id

    def test_get_leave_requests_status_filter_returns_only_matching_rows(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            status=LeaveRequest.Status.PENDING,
        )
        baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            status=LeaveRequest.Status.REJECTED,
        )

        response = self.hr_client.get('/api/leave-requests/?status=approved')

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_post_leave_requests_creates_pending_status(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)

        payload = {
            'employee': employee.id,
            'type': LeaveRequest.Type.VACATION,
            'from_date': '2026-05-01',
            'to_date': '2026-05-03',
            'reason': 'Family event',
        }

        response = self.hr_client.post('/api/leave-requests/', payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        leave_request = LeaveRequest.objects.get(id=response.data['id'])
        assert leave_request.status == LeaveRequest.Status.PENDING

    def test_patch_leave_request_approve_sets_approved_status(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        leave_request = baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            status=LeaveRequest.Status.PENDING,
        )

        response = self.hr_client.patch(f'/api/leave-requests/{leave_request.id}/approve/', {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        leave_request.refresh_from_db()
        assert leave_request.status == LeaveRequest.Status.APPROVED
        assert leave_request.approved_by_id == self.hr_user.id

    def test_patch_leave_request_reject_sets_rejected_status(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        leave_request = baker.make(
            LeaveRequest,
            employee=employee,
            department=self.hr_department,
            status=LeaveRequest.Status.PENDING,
        )

        response = self.hr_client.patch(f'/api/leave-requests/{leave_request.id}/reject/', {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        leave_request.refresh_from_db()
        assert leave_request.status == LeaveRequest.Status.REJECTED
        assert leave_request.approved_by_id == self.hr_user.id


class TestHrContractsEndpoint(HrEndpointsTestCase):
    def test_get_contracts_returns_all_with_status_computation(self):
        today = timezone.localdate()
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)

        active_contract = baker.make(
            Contract,
            contract_number='CTR-100',
            employee=employee,
            department=self.hr_department,
            end_date=today + timedelta(days=90),
        )
        expiring_contract = baker.make(
            Contract,
            contract_number='CTR-101',
            employee=employee,
            department=self.hr_department,
            end_date=today + timedelta(days=10),
        )
        expired_contract = baker.make(
            Contract,
            contract_number='CTR-102',
            employee=employee,
            department=self.hr_department,
            end_date=today - timedelta(days=1),
        )

        response = self.hr_client.get('/api/contracts/')

        assert response.status_code == status.HTTP_200_OK
        by_number = {item['contract_number']: item for item in response.data['contracts']}

        assert by_number[active_contract.contract_number]['status'] == 'ACTIVE'
        assert by_number[expiring_contract.contract_number]['status'] == 'EXPIRING'
        assert by_number[expired_contract.contract_number]['status'] == 'EXPIRED'

    def test_get_contracts_expiring_filter_returns_only_expiring(self):
        today = timezone.localdate()
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)

        baker.make(
            Contract,
            contract_number='CTR-201',
            employee=employee,
            department=self.hr_department,
            end_date=today + timedelta(days=12),
        )
        baker.make(
            Contract,
            contract_number='CTR-202',
            employee=employee,
            department=self.hr_department,
            end_date=today + timedelta(days=120),
        )

        response = self.hr_client.get('/api/contracts/?status=expiring')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['contracts']) == 1
        assert response.data['contracts'][0]['status'] == 'EXPIRING'

    def test_get_contract_detail_returns_full_contract_payload(self):
        today = timezone.localdate()
        employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Ana',
            last_name='Pop',
            username='ana.pop',
        )
        contract = baker.make(
            Contract,
            contract_number='CTR-301',
            employee=employee,
            department=self.hr_department,
            type=Contract.Type.CONTRACTOR,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            salary_ron=Decimal('7250.50'),
        )

        response = self.hr_client.get(f'/api/contracts/{contract.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == contract.id
        assert response.data['employee_name'] == 'Ana Pop'
        assert response.data['department'] == self.hr_department.name
        assert response.data['type'] == Contract.Type.CONTRACTOR
        assert response.data['start_date'] == contract.start_date.isoformat()
        assert response.data['end_date'] == contract.end_date.isoformat()
        assert response.data['salary_ron'] == '7250.50'
        assert response.data['status'] == 'EXPIRING'

    def test_get_contract_detail_requires_hr_or_ceo(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        contract = baker.make(Contract, employee=employee, department=self.hr_department)
        client = APITestCase.client_class()
        client.force_authenticate(user=employee)

        response = client.get(f'/api/contracts/{contract.id}/')

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestHrUpcomingEventsEndpoint(HrEndpointsTestCase):
    def test_get_upcoming_events_returns_chronological_db_driven_rows(self):
        today = timezone.localdate()
        near_contract_end = today + timedelta(days=3)
        onboarding_day = today + timedelta(days=5)
        payroll_month = date(today.year, today.month, 1)

        contract_employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Andrei',
            last_name='Popa',
            username='andrei.popa',
        )
        baker.make(
            Contract,
            contract_number='CTR-301',
            employee=contract_employee,
            department=self.hr_department,
            end_date=near_contract_end,
        )

        baker.make(
            User,
            role=User.Role.IT,
            department=self.hr_department,
            first_name='Maria',
            last_name='Ionescu',
            username='maria.ionescu',
            start_date=onboarding_day,
        )

        payroll_employee = baker.make(User, role=User.Role.HR, department=self.hr_department)
        baker.make(
            PayrollEntry,
            employee=payroll_employee,
            month=payroll_month,
            gross_salary_ron=Decimal('4200.00'),
            net_salary_ron=Decimal('4000.00'),
            paid=False,
        )

        response = self.hr_client.get('/api/hr/upcoming-events/?days=30')

        assert response.status_code == status.HTTP_200_OK
        events = response.data['events']
        assert len(events) >= 3
        assert [event['date'] for event in events] == sorted(event['date'] for event in events)

        contract_event = next(event for event in events if event['type'] == 'CONTRACT_EXPIRY')
        onboarding_event = next(event for event in events if event['type'] == 'ONBOARDING')
        payroll_event = next(event for event in events if event['type'] == 'PAYROLL_PROCESSING')

        assert contract_event['is_warning']
        assert contract_event['link'] == '/hr/contracts'
        assert contract_event['dot_color'] == 'red'
        assert onboarding_event['dot_color'] == 'blue'
        assert payroll_event['dot_color'] == 'blue'
        assert 'unpaid payroll' in payroll_event['description']

    def test_get_upcoming_events_requires_hr_or_ceo(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        client = APITestCase.client_class()
        client.force_authenticate(user=employee)

        response = client.get('/api/hr/upcoming-events/')

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestHrPayrollEndpoint(HrEndpointsTestCase):
    def test_get_payroll_month_returns_correct_net_calculation(self):
        month_date = timezone.datetime(2026, 4, 1).date()
        employee = baker.make(
            User, role=User.Role.SALES, department=self.hr_department, first_name='Dana', last_name='Marin'
        )

        baker.make(
            PayrollEntry,
            employee=employee,
            month=month_date,
            gross_salary_ron=Decimal('4000.00'),
            net_salary_ron=Decimal('0.00'),
        )

        response = self.hr_client.get('/api/payroll/?month=2026-04&bonus=500&deductions=200')

        assert response.status_code == status.HTTP_200_OK
        row = response.data['payroll'][0]
        assert Decimal(row['base_salary_ron']) == Decimal('4000.00')
        assert Decimal(row['bonus_ron']) == Decimal('500')
        assert Decimal(row['deductions_ron']) == Decimal('200')
        assert Decimal(row['net_salary_ron']) == Decimal('4300.00')

    def test_payroll_deduction_formula_net_equals_base_plus_bonus_minus_deductions(self):
        month_date = timezone.datetime(2026, 6, 1).date()
        employee = baker.make(User, role=User.Role.IT, department=self.hr_department)

        baker.make(
            PayrollEntry,
            employee=employee,
            month=month_date,
            gross_salary_ron=Decimal('3200.50'),
            net_salary_ron=Decimal('0.00'),
        )

        response = self.hr_client.get('/api/payroll/?month=2026-06&bonus=150.25&deductions=99.75')

        assert response.status_code == status.HTTP_200_OK
        row = response.data['payroll'][0]

        base = Decimal(row['base_salary_ron'])
        bonus = Decimal(row['bonus_ron'])
        deductions = Decimal(row['deductions_ron'])
        net = Decimal(row['net_salary_ron'])

        assert net == base + bonus - deductions


class TestCeoHrSummaryEndpoint(APITestCase):
    def test_ceo_hr_summary_counts_it_and_sales_departments(self):
        ceo = baker.make(User, role=User.Role.CEO, username='ceo_summary', email='ceo_summary@example.com')
        client = APITestCase.client_class()
        client.force_authenticate(user=ceo)

        it_department = baker.make(Department, name='IT Support', slug='it-support')
        sales_department = baker.make(Department, name='Sales & Marketing', slug='sales-marketing')

        baker.make(User, role=User.Role.IT, department=it_department, is_active=True)
        baker.make(User, role=User.Role.IT, department=it_department, is_active=False)
        baker.make(User, role=User.Role.SALES, department=sales_department, is_active=True)

        response = client.get('/api/hr/ceo-summary/')

        assert response.status_code == status.HTTP_200_OK
        by_department = {row['department']: row for row in response.data['department_headcount']}

        assert by_department['IT Support']['total'] == 2
        assert by_department['IT Support']['active'] == 1
        assert by_department['Sales & Marketing']['total'] == 1
        assert by_department['Sales & Marketing']['active'] == 1
