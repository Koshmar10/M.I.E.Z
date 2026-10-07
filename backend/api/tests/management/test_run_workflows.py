"""Tests for the run_workflows management command (time-based triggers)."""

from django.test import TestCase

from api.models import WorkflowLog
from api.tests.factories import make_workflow


class TimeTriggerTests(TestCase):
    """Verify run_workflows management command fires time-based triggers."""

    def _call(self, fake_now):
        from unittest.mock import patch

        from django.core.management import call_command

        with patch('api.management.commands.run_workflows.timezone.localtime', return_value=fake_now):
            call_command('run_workflows', verbosity=0)

    def _fake_now(self, weekday_name: str, time_str: str):
        """Return a mock datetime matching the given weekday name and HH:MM string."""
        import datetime

        from django.utils import timezone as tz

        # Build a real date for the requested weekday
        days = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
        target_weekday = days[weekday_name]
        today = datetime.date.today()
        delta = (target_weekday - today.weekday()) % 7
        target_date = today + datetime.timedelta(days=delta)
        h, m = map(int, time_str.split(':'))
        dt = datetime.datetime(
            target_date.year, target_date.month, target_date.day, h, m, tzinfo=tz.get_current_timezone()
        )
        return dt

    def test_daily_at_time_triggers_at_scheduled_time(self):
        make_workflow(
            name='Daily Standup',
            trigger_type='DAILY_AT_TIME',
            trigger_config={'time': '09:30'},
            actions=['NOTIFY_MANAGER'],
        )
        self._call(self._fake_now('monday', '09:30'))
        assert WorkflowLog.objects.count() == 1
        assert WorkflowLog.objects.first().trigger_type == 'DAILY_AT_TIME'

    def test_daily_at_time_does_not_trigger_at_wrong_time(self):
        make_workflow(
            name='Daily Check',
            trigger_type='DAILY_AT_TIME',
            trigger_config={'time': '09:30'},
            actions=['NOTIFY_MANAGER'],
        )
        self._call(self._fake_now('monday', '10:00'))
        assert WorkflowLog.objects.count() == 0

    def test_weekly_at_time_triggers_on_correct_day_and_time(self):
        make_workflow(
            name='Weekly Report',
            trigger_type='WEEKLY_AT_TIME',
            trigger_config={'day_of_week': 'wednesday', 'time': '08:00'},
            actions=['EMAIL_CEO'],
        )
        self._call(self._fake_now('wednesday', '08:00'))
        assert WorkflowLog.objects.count() == 1
        assert WorkflowLog.objects.first().trigger_type == 'WEEKLY_AT_TIME'

    def test_weekly_at_time_does_not_trigger_on_wrong_day(self):
        make_workflow(
            name='Weekly Check',
            trigger_type='WEEKLY_AT_TIME',
            trigger_config={'day_of_week': 'wednesday', 'time': '08:00'},
            actions=['EMAIL_CEO'],
        )
        self._call(self._fake_now('tuesday', '08:00'))
        assert WorkflowLog.objects.count() == 0

    def test_inactive_workflow_not_triggered_by_command(self):
        make_workflow(
            name='Inactive Daily',
            trigger_type='DAILY_AT_TIME',
            trigger_config={'time': '09:30'},
            actions=['NOTIFY_MANAGER'],
            is_active=False,
        )
        self._call(self._fake_now('monday', '09:30'))
        assert WorkflowLog.objects.count() == 0

    def test_managed_by_workflow_skipped_by_command(self):
        """Workflows with managed_by in trigger_config are owned by dedicated commands."""
        make_workflow(
            name='HR Agent',
            trigger_type='WEEKLY_AT_TIME',
            trigger_config={'day_of_week': 'monday', 'time': '06:00', 'managed_by': 'run_hr_agent'},
            actions=['GENERATE_REPORT'],
        )
        self._call(self._fake_now('monday', '06:00'))
        assert WorkflowLog.objects.count() == 0
