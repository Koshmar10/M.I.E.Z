"""End-to-end test of the HR insights agent cycle."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from api.models import Attendance, Contract, Department, Notification, PayrollEntry, Report, User, Workflow, WorkflowLog


class HrAgentIntegrationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Departments
        cls.depts = [
            baker.make(Department, name=n, slug=s)
            for n, s in (
                ('Human Resources', 'hr'),
                ('Sales', 'sales'),
                ('IT', 'it'),
                ('Inventory', 'inventory'),
            )
        ]

        # Users: CEO, HR manager, and 7 employees across departments
        cls.ceo = baker.make(User, role=User.Role.CEO, username='ceo_integ')
        cls.hr_manager = baker.make(User, role=User.Role.HR, username='hr_manager_integ', is_active=True)

        cls.employees = []
        # 2 in Sales, 2 in IT, 2 in Inventory, 1 in HR
        cls.employees += [
            baker.make(User, role=User.Role.SALES, department=cls.depts[1], is_active=True) for _ in range(2)
        ]
        cls.employees += [
            baker.make(User, role=User.Role.IT, department=cls.depts[2], is_active=True) for _ in range(2)
        ]
        cls.employees += [
            baker.make(User, role=User.Role.INVENTORY, department=cls.depts[3], is_active=True) for _ in range(2)
        ]
        cls.employees += [
            baker.make(User, role=User.Role.HR, department=cls.depts[0], is_active=True) for _ in range(1)
        ]

        # 4 weeks of attendance records for each employee
        today = timezone.localdate()
        start_week = today - timedelta(weeks=4)
        for emp in cls.employees:
            for w in range(4):
                week_start = start_week + timedelta(weeks=w)
                for d in range(5):
                    # make most days present, occasionally remote/absent
                    status = Attendance.Status.PRESENT
                    if (emp.id + w + d) % 11 == 0:
                        status = Attendance.Status.ABSENT
                    elif (emp.id + w + d) % 7 == 0:
                        status = Attendance.Status.REMOTE
                    Attendance.objects.create(employee=emp, date=week_start + timedelta(days=d), status=status)

        # 2 expiring contracts
        expiring_emp1 = cls.employees[0]
        expiring_emp2 = cls.employees[1]
        Contract.objects.create(
            employee=expiring_emp1,
            department=cls.depts[1],
            contract_number='EXP-1',
            start_date=today - timedelta(days=365),
            end_date=today + timedelta(days=10),
        )
        Contract.objects.create(
            employee=expiring_emp2,
            department=cls.depts[1],
            contract_number='EXP-2',
            start_date=today - timedelta(days=200),
            end_date=today + timedelta(days=20),
        )

        # 1 payroll anomaly - unpaid entry in current month
        month_start = timezone.now().date().replace(day=1)
        PayrollEntry.objects.create(
            employee=cls.employees[2],
            month=month_start,
            gross_salary_ron='3000.00',
            net_salary_ron='2700.00',
            paid=False,
        )

        # Ensure Workflow exists
        Workflow.objects.create(name='HR Insights Agent', is_active=True, actions=['GENERATE_REPORT'])

    def setUp(self):
        self.client = APIClient()

    @patch('api.management.commands.run_hr_agent.AgentRunner.run')
    def test_full_hr_agent_cycle_creates_report_and_notifications(self, mocked_run):
        # Mock agent response with realistic structured JSON digest
        digest = {
            'week': timezone.localdate().isoformat(),
            'generated_at': timezone.now().isoformat(),
            'critical': [{'title': 'Unpaid Payroll', 'description': '1 unpaid entry'}],
            'warning': [],
            'info': [],
            'summary_line': '1 critical issue — unpaid payroll',
            'period': f'Week of {timezone.localdate().isoformat()}',
        }
        mocked_run.return_value = {'response': json.dumps(digest), 'tool_calls_made': []}

        # Run the management command
        call_command('run_hr_agent')

        # Assert a WorkflowLog created with success=True
        log = WorkflowLog.objects.order_by('-triggered_at').first()
        self.assertIsNotNone(log)
        self.assertTrue(log.success)

        # Assert Report created with category HR and non-null digest content
        report = Report.objects.filter(category=Report.Category.HR).order_by('-generated_at').first()
        self.assertIsNotNone(report)
        self.assertIsNotNone(report.digest_data)
        # run_hr_agent stores the structured digest as a JSON string in digest_data['content']
        if 'summary_line' not in report.digest_data:
            content = report.digest_data.get('content')
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
            except Exception:
                parsed = None
            self.assertIsNotNone(parsed)
            self.assertIn('summary_line', parsed)

        # Assert Notification created for HR Manager users
        notifications = Notification.objects.filter(recipient=self.hr_manager)
        self.assertTrue(notifications.exists())

        # Assert GET /api/hr/latest-digest/ returns the created Report
        self.client.force_authenticate(user=self.hr_manager)
        resp = self.client.get('/api/hr/latest-digest/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['id'], report.id)
        self.assertEqual(data['category'], Report.Category.HR)

        # Assert HR dashboard includes digest summary
        resp2 = self.client.get('/api/hr/dashboard/')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('latest_digest', resp2.json())
        ld = resp2.json()['latest_digest']
        self.assertIsNotNone(ld)
        self.assertIn('summary', ld)

    @patch('api.management.commands.run_hr_agent.AgentRunner.run')
    def test_management_command_run_hr_agent_dry_run_no_notification(self, mocked_run):
        Notification.objects.all().delete()
        digest = {'critical': [{'title': 'Test'}], 'warning': [], 'summary_line': 'test'}
        mocked_run.return_value = {'response': json.dumps(digest), 'tool_calls_made': []}

        call_command('run_hr_agent', dry_run=True)

        notifications = Notification.objects.filter(recipient=self.hr_manager)
        self.assertFalse(notifications.exists())

        log = WorkflowLog.objects.order_by('-triggered_at').first()
        self.assertTrue(log.success)

    @patch('api.management.commands.run_hr_agent.AgentRunner.run')
    def test_run_hr_agent_zero_insights_no_notification_sent(self, mocked_run):
        Notification.objects.all().delete()
        digest = {'critical': [], 'warning': [], 'summary_line': 'No issues detected'}
        mocked_run.return_value = {'response': json.dumps(digest), 'tool_calls_made': []}

        call_command('run_hr_agent')

        notifications = Notification.objects.filter(recipient=self.hr_manager)
        self.assertFalse(notifications.exists())

    @patch('api.management.commands.run_hr_agent.AgentRunner.run')
    def test_run_hr_agent_critical_insight_creates_notification_type_warning(self, mocked_run):
        Notification.objects.all().delete()
        digest = {'critical': [{'title': 'CRITICAL!'}], 'warning': [], 'summary_line': 'Has critical'}
        mocked_run.return_value = {'response': json.dumps(digest), 'tool_calls_made': []}

        call_command('run_hr_agent')

        notifications = Notification.objects.filter(recipient=self.hr_manager)
        self.assertTrue(notifications.exists())
        self.assertEqual(notifications.first().type, 'WARNING')

    def test_post_run_insights_agent_non_hr_role_forbidden(self):
        non_hr = self.employees[0]  # SALES
        self.client.force_authenticate(user=non_hr)
        resp = self.client.post('/api/hr/run-insights-agent/')
        self.assertEqual(resp.status_code, 403)

    @patch('api.views.hr.RunInsightsAgentView._spawn_agent')
    def test_post_run_insights_agent_rate_limit_enforced(self, mock_spawn):
        # _spawn_agent is mocked so the endpoint doesn't launch real background
        # threads that would run the agent and lock the shared SQLite test DB.
        self.client.force_authenticate(user=self.hr_manager)
        from django.core.cache import cache

        cache.clear()

        for _ in range(3):
            resp = self.client.post('/api/hr/run-insights-agent/')
            self.assertEqual(resp.status_code, 200)

        resp_rate_limit = self.client.post('/api/hr/run-insights-agent/')
        self.assertEqual(resp_rate_limit.status_code, 429)
        self.assertEqual(mock_spawn.call_count, 3)
