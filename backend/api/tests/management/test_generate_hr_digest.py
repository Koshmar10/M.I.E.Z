"""Tests for the generate_hr_digest management command."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from api.management.commands.generate_hr_digest import DigestGenerator
from api.models import Contract, LeaveRequest, Notification, PayrollEntry, Report, User
from api.tests.base import DigestTestCase


class TestDigestGenerator(DigestTestCase):
    def test_digest_has_required_structure(self):
        generator = DigestGenerator()
        digest = generator.generate()

        required_fields = {'week', 'generated_at', 'critical', 'warning', 'info', 'summary_line', 'period'}
        assert required_fields.issubset(digest.keys())
        assert isinstance(digest['critical'], list)
        assert isinstance(digest['warning'], list)
        assert isinstance(digest['info'], list)
        assert isinstance(digest['summary_line'], str)

    def test_empty_digest_returns_no_anomalies_summary(self):
        generator = DigestGenerator()
        digest = generator.generate()

        if not digest['critical'] and not digest['warning']:
            assert 'normal range' in digest['summary_line'].lower()

    def test_insight_has_required_fields(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        generator = DigestGenerator()
        digest = generator.generate()

        if digest['critical']:
            insight = digest['critical'][0]
            required_fields = {'title', 'description', 'suggested_action', 'related_employee', 'related_department'}
            assert required_fields.issubset(insight.keys())

    def test_detects_unpaid_payroll(self):
        current_month = self._current_month()
        baker.make(PayrollEntry, paid=False, month=current_month)
        baker.make(PayrollEntry, paid=False, month=current_month)

        digest = DigestGenerator().generate()

        assert len(digest['critical']) > 0
        payroll_insight = next((insight for insight in digest['critical'] if 'Unpaid' in insight['title']), None)
        assert payroll_insight is not None
        assert '2' in payroll_insight['title']

    def test_detects_pending_leave_requests(self):
        baker.make(LeaveRequest, status=LeaveRequest.Status.PENDING)
        baker.make(LeaveRequest, status=LeaveRequest.Status.PENDING)

        digest = DigestGenerator().generate()

        pending_insight = next((insight for insight in digest['warning'] if 'Pending' in insight['title']), None)
        assert pending_insight is not None
        assert '2' in pending_insight['title']

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
        assert contract_insight is not None

    def test_summary_line_includes_critical_count(self):
        current_month = self._current_month()
        for _ in range(3):
            baker.make(PayrollEntry, paid=False, month=current_month)

        digest = DigestGenerator().generate()

        assert len(digest['critical']) > 0
        assert 'critical' in digest['summary_line'].lower()


class TestDigestManagementCommand(DigestTestCase):
    def test_management_command_generates_digest(self):
        out = StringIO()
        call_command('generate_hr_digest', stdout=out)

        output = out.getvalue()
        assert 'Weekly HR Digest' in output or 'No anomalies' in output

    def test_management_command_save_report_flag(self):
        initial_count = Report.objects.filter(category=Report.Category.HR).count()

        out = StringIO()
        call_command('generate_hr_digest', '--save-report', stdout=out)

        final_count = Report.objects.filter(category=Report.Category.HR).count()
        assert final_count == initial_count + 1

    def test_management_command_notify_hr_flag(self):
        baker.make(PayrollEntry, paid=False, month=self._current_month())

        initial_notifications = Notification.objects.filter(recipient=self.hr_manager).count()

        out = StringIO()
        call_command('generate_hr_digest', '--notify-hr', stdout=out)

        final_notifications = Notification.objects.filter(recipient=self.hr_manager).count()
        assert final_notifications > initial_notifications
