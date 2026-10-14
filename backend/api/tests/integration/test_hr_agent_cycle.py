"""End-to-end test of the HR insights agent cycle."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from api.models import Attendance, Contract, Department, Notification, PayrollEntry, Report, User, Workflow, WorkflowLog


@pytest.fixture(autouse=True)
def company(hr_user):
    """Departments, 7 employees with 4 weeks of attendance, 2 expiring contracts and 1 unpaid payroll entry."""
    hr, sales, it, inventory = (
        baker.make(Department, name=name, slug=slug)
        for name, slug in [('Human Resources', 'hr'), ('Sales', 'sales'), ('IT', 'it'), ('Inventory', 'inventory')]
    )
    sales_staff = baker.make(User, role=User.Role.SALES, department=sales, is_active=True, _quantity=2)
    employees = [
        *sales_staff,
        *baker.make(User, role=User.Role.IT, department=it, is_active=True, _quantity=2),
        *baker.make(User, role=User.Role.INVENTORY, department=inventory, is_active=True, _quantity=2),
        baker.make(User, role=User.Role.HR, department=hr, is_active=True),
    ]

    today = timezone.localdate()
    first_week = today - timedelta(weeks=4)
    for employee in employees:
        for week in range(4):
            for day in range(5):  # mostly present, sometimes remote or absent
                seed = employee.id + week + day
                status = (
                    Attendance.Status.ABSENT
                    if seed % 11 == 0
                    else Attendance.Status.REMOTE
                    if seed % 7 == 0
                    else Attendance.Status.PRESENT
                )
                baker.make(
                    Attendance, employee=employee, date=first_week + timedelta(weeks=week, days=day), status=status
                )

    for employee, days_left in [(sales_staff[0], 10), (sales_staff[1], 20)]:
        baker.make(Contract, employee=employee, department=sales, end_date=today + timedelta(days=days_left))
    baker.make(PayrollEntry, employee=employees[2], month=today.replace(day=1), paid=False)
    baker.make(Workflow, name='HR Insights Agent', is_active=True, actions=['GENERATE_REPORT'])
    return sales_staff


@pytest.fixture
def agent_reply():
    """Set what the (mocked) HR agent answers with."""
    with patch('api.management.commands.run_hr_agent.AgentRunner.run') as run:

        def reply(digest):
            run.return_value = {'response': json.dumps(digest), 'tool_calls_made': []}

        yield reply


def test_full_hr_agent_cycle_creates_report_and_notifications(agent_reply, hr_user, hr_client):
    agent_reply(
        {
            'week': timezone.localdate().isoformat(),
            'generated_at': timezone.now().isoformat(),
            'critical': [{'title': 'Unpaid Payroll', 'description': '1 unpaid entry'}],
            'warning': [],
            'info': [],
            'summary_line': '1 critical issue — unpaid payroll',
            'period': f'Week of {timezone.localdate().isoformat()}',
        }
    )

    call_command('run_hr_agent')

    assert WorkflowLog.objects.latest('triggered_at').success
    report = Report.objects.filter(category=Report.Category.HR).latest('generated_at')
    # run_hr_agent stores the digest either directly or as a JSON string under 'content'
    digest = report.digest_data
    if 'summary_line' not in digest:
        digest = json.loads(digest['content'])
    assert 'summary_line' in digest
    assert Notification.objects.filter(recipient=hr_user).exists()

    latest = hr_client.get('/api/hr/latest-digest/')
    assert latest.status_code == 200
    assert latest.json()['id'] == report.id
    assert latest.json()['category'] == Report.Category.HR

    dashboard = hr_client.get('/api/hr/dashboard/')
    assert dashboard.status_code == 200
    assert 'summary' in dashboard.json()['latest_digest']


def test_management_command_run_hr_agent_dry_run_no_notification(agent_reply, hr_user):
    agent_reply({'critical': [{'title': 'Test'}], 'warning': [], 'summary_line': 'test'})

    call_command('run_hr_agent', dry_run=True)

    assert not Notification.objects.filter(recipient=hr_user).exists()
    assert WorkflowLog.objects.latest('triggered_at').success


def test_run_hr_agent_zero_insights_no_notification_sent(agent_reply, hr_user):
    agent_reply({'critical': [], 'warning': [], 'summary_line': 'No issues detected'})

    call_command('run_hr_agent')

    assert not Notification.objects.filter(recipient=hr_user).exists()


def test_run_hr_agent_critical_insight_creates_notification_type_warning(agent_reply, hr_user):
    agent_reply({'critical': [{'title': 'CRITICAL!'}], 'warning': [], 'summary_line': 'Has critical'})

    call_command('run_hr_agent')

    assert Notification.objects.get(recipient=hr_user).type == 'WARNING'


def test_post_run_insights_agent_non_hr_role_forbidden(api_client, company):
    api_client.force_authenticate(user=company[0])  # a sales employee
    assert api_client.post('/api/hr/run-insights-agent/').status_code == 403


def test_post_run_insights_agent_rate_limit_enforced(hr_client):
    # _spawn_agent is mocked so the endpoint doesn't start real background threads,
    # which would run the agent and lock the shared SQLite test database.
    with patch('api.views.hr.RunInsightsAgentView._spawn_agent') as spawn:
        for _ in range(3):
            assert hr_client.post('/api/hr/run-insights-agent/').status_code == 200
        assert hr_client.post('/api/hr/run-insights-agent/').status_code == 429
    assert spawn.call_count == 3
