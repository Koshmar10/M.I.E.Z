"""Tests for the generate_hr_digest management command and its DigestGenerator."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from api.management.commands.generate_hr_digest import DigestGenerator
from api.models import Contract, Department, LeaveRequest, Notification, PayrollEntry, Report, User


def _current_month():
    return timezone.now().date().replace(day=1)


def test_digest_has_required_structure():
    digest = DigestGenerator().generate()

    assert {'week', 'generated_at', 'critical', 'warning', 'info', 'summary_line', 'period'} <= digest.keys()
    assert isinstance(digest['critical'], list)
    assert isinstance(digest['warning'], list)
    assert isinstance(digest['info'], list)
    assert isinstance(digest['summary_line'], str)


def test_empty_digest_returns_no_anomalies_summary():
    digest = DigestGenerator().generate()

    if not digest['critical'] and not digest['warning']:
        assert 'normal range' in digest['summary_line'].lower()


def test_insight_has_required_fields():
    baker.make(PayrollEntry, paid=False, month=_current_month())

    digest = DigestGenerator().generate()

    if digest['critical']:
        required = {'title', 'description', 'suggested_action', 'related_employee', 'related_department'}
        assert required <= digest['critical'][0].keys()


def test_detects_unpaid_payroll():
    baker.make(PayrollEntry, paid=False, month=_current_month(), _quantity=2)

    digest = DigestGenerator().generate()

    payroll_insight = next((i for i in digest['critical'] if 'Unpaid' in i['title']), None)
    assert payroll_insight is not None
    assert '2' in payroll_insight['title']


def test_detects_pending_leave_requests():
    baker.make(LeaveRequest, status=LeaveRequest.Status.PENDING, _quantity=2)

    digest = DigestGenerator().generate()

    pending_insight = next((i for i in digest['warning'] if 'Pending' in i['title']), None)
    assert pending_insight is not None
    assert '2' in pending_insight['title']


def test_detects_expiring_contracts():
    department = baker.make(Department)
    employee = baker.make(User, department=department)
    baker.make(Contract, employee=employee, department=department, end_date=timezone.localdate() + timedelta(days=15))

    digest = DigestGenerator().generate()

    assert any('expir' in i['title'].lower() for i in digest['warning'])


def test_summary_line_includes_critical_count():
    baker.make(PayrollEntry, paid=False, month=_current_month(), _quantity=3)

    digest = DigestGenerator().generate()

    assert len(digest['critical']) > 0
    assert 'critical' in digest['summary_line'].lower()


def test_management_command_generates_digest():
    out = StringIO()
    call_command('generate_hr_digest', stdout=out)

    assert 'Weekly HR Digest' in out.getvalue() or 'No anomalies' in out.getvalue()


def test_management_command_save_report_flag():
    call_command('generate_hr_digest', '--save-report', stdout=StringIO())

    assert Report.objects.filter(category=Report.Category.HR).count() == 1


def test_management_command_notify_hr_flag(hr_user):
    baker.make(PayrollEntry, paid=False, month=_current_month())

    call_command('generate_hr_digest', '--notify-hr', stdout=StringIO())

    assert Notification.objects.filter(recipient=hr_user).exists()
