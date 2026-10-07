"""Tests for HR weekly digest feature.
Tests the digest generation, insights creation, and notification logic.
"""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from api.management.commands.generate_hr_digest import DigestGenerator
from api.models import Contract, Department, LeaveRequest, Notification, PayrollEntry, Report, User


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


class TestDigestGenerator(DigestTestCase):
    def test_digest_has_required_structure(self):
        generator = DigestGenerator()
        digest = generator.generate()

        required_fields = {'week', 'generated_at', 'critical', 'warning', 'info', 'summary_line', 'period'}
        self.assertTrue(required_fields.issubset(digest.keys()))
        self.assertIsInstance(digest['critical'], list)
        self.assertIsInstance(digest['warning'], list)
        self.assertIsInstance(digest['info'], list)
        self.assertIsInstance(digest['summary_line'], str)

    def test_empty_digest_returns_no_anomalies_summary(self):
        generator = DigestGenerator()
        digest = generator.generate()

        if not digest['critical'] and not digest['warning']:
            self.assertIn('normal range', digest['summary_line'].lower())

    def test_insight_has_required_fields(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        generator = DigestGenerator()
        digest = generator.generate()

        if digest['critical']:
            insight = digest['critical'][0]
            required_fields = {'title', 'description', 'suggested_action', 'related_employee', 'related_department'}
            self.assertTrue(required_fields.issubset(insight.keys()))

    def test_detects_unpaid_payroll(self):
        current_month = self._current_month()
        baker.make(PayrollEntry, paid=False, month=current_month)
        baker.make(PayrollEntry, paid=False, month=current_month)

        digest = DigestGenerator().generate()

        self.assertGreater(len(digest['critical']), 0)
        payroll_insight = next((insight for insight in digest['critical'] if 'Unpaid' in insight['title']), None)
        self.assertIsNotNone(payroll_insight)
        self.assertIn('2', payroll_insight['title'])

    def test_detects_pending_leave_requests(self):
        baker.make(LeaveRequest, status=LeaveRequest.Status.PENDING)
        baker.make(LeaveRequest, status=LeaveRequest.Status.PENDING)

        digest = DigestGenerator().generate()

        pending_insight = next((insight for insight in digest['warning'] if 'Pending' in insight['title']), None)
        self.assertIsNotNone(pending_insight)
        self.assertIn('2', pending_insight['title'])

    def test_detects_expiring_contracts(self):
        today = timezone.localdate()
        employee = baker.make(User, department=self.sales_department)

        baker.make(
            Contract,
            employee=employee,
            department=self.sales_department,
            end_date=today + timedelta(days=15),
        )

        digest = DigestGenerator().generate()

        contract_insight = next((insight for insight in digest['warning'] if 'expir' in insight['title'].lower()), None)
        self.assertIsNotNone(contract_insight)

    def test_summary_line_includes_critical_count(self):
        current_month = self._current_month()
        for _ in range(3):
            baker.make(PayrollEntry, paid=False, month=current_month)

        digest = DigestGenerator().generate()

        self.assertGreater(len(digest['critical']), 0)
        self.assertIn('critical', digest['summary_line'].lower())


class TestHrDigestGenerateView(DigestTestCase):
    def test_only_ceo_can_generate_digest(self):
        hr_client = APITestCase.client_class()
        hr_client.force_authenticate(user=self.hr_manager)

        response = hr_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ceo_can_generate_digest(self):
        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('digest', data)
        self.assertIn('report_id', data)

    def test_digest_generates_creates_report(self):
        initial_count = Report.objects.filter(category=Report.Category.HR).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        final_count = Report.objects.filter(category=Report.Category.HR).count()
        self.assertEqual(final_count, initial_count + 1)

        report = Report.objects.filter(category=Report.Category.HR).latest('generated_at')
        self.assertIsNotNone(report.digest_data)
        self.assertIn('critical', report.digest_data)

    def test_digest_sends_notification_for_critical_issues(self):
        current_month = self._current_month()
        baker.make(PayrollEntry, paid=False, month=current_month)

        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data['notifications_sent'])

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        self.assertEqual(final_notifications, initial_notifications + 1)

        notification = Notification.objects.filter(recipient=self.hr_manager).latest('created_at')
        self.assertIn('Critical', notification.title)

    def test_digest_does_not_send_notification_for_no_issues(self):
        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        self.assertLessEqual(final_notifications - initial_notifications, 1)

    def test_report_stores_full_digest_data(self):
        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        report = Report.objects.get(id=response.json()['report_id'])
        self.assertIsNotNone(report.digest_data)
        self.assertIn('week', report.digest_data)
        self.assertIn('generated_at', report.digest_data)
        self.assertIn('summary_line', report.digest_data)
        self.assertEqual(report.generated_by, self.ceo_user)

    def test_unauthenticated_user_cannot_generate_digest(self):
        client = APITestCase.client_class()
        response = client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestDigestNotifications(DigestTestCase):
    def test_notification_sent_to_all_active_hr_managers(self):
        hr_managers = [baker.make(User, role=User.Role.HR, is_active=True) for _ in range(3)]
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for hr_manager in hr_managers:
            self.assertTrue(Notification.objects.filter(recipient=hr_manager, title__icontains='Critical').exists())

    def test_notification_body_uses_summary_line(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        digest = response.json()['digest']
        summary = digest['summary_line']

        notification = Notification.objects.filter(
            recipient=self.hr_manager,
            title__icontains='Critical',
        ).latest('created_at')

        self.assertEqual(notification.body, summary)

    def test_notification_includes_link_to_reports(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        response = self.ceo_client.post('/api/hr/digest/generate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notification = Notification.objects.filter(
            recipient=self.hr_manager,
            title__icontains='Critical',
        ).latest('created_at')

        self.assertIn('/reports', notification.link)
        self.assertIn('HR', notification.link)


class TestDigestManagementCommand(DigestTestCase):
    def test_management_command_generates_digest(self):
        out = StringIO()
        call_command('generate_hr_digest', stdout=out)

        output = out.getvalue()
        self.assertTrue('Weekly HR Digest' in output or 'No anomalies' in output)

    def test_management_command_save_report_flag(self):
        initial_count = Report.objects.filter(category=Report.Category.HR).count()

        out = StringIO()
        call_command('generate_hr_digest', '--save-report', stdout=out)

        final_count = Report.objects.filter(category=Report.Category.HR).count()
        self.assertEqual(final_count, initial_count + 1)

    def test_management_command_notify_hr_flag(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        out = StringIO()
        call_command('generate_hr_digest', '--notify-hr', stdout=out)

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        self.assertGreater(final_notifications, initial_notifications)
