"""Tests for the run_workflows management command (time-based triggers)."""

import datetime
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from model_bakery import baker

from api.models import Workflow, WorkflowLog

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def _run_workflows_at(weekday: str, time: str) -> None:
    """Run the command as if it were `time` (HH:MM) on the next `weekday`."""
    today = datetime.date.today()
    day = today + datetime.timedelta(days=(WEEKDAYS.index(weekday) - today.weekday()) % 7)
    hour, minute = map(int, time.split(':'))
    now = datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.get_current_timezone())
    with patch('api.management.commands.run_workflows.timezone.localtime', return_value=now):
        call_command('run_workflows', verbosity=0)


def test_daily_at_time_triggers_at_scheduled_time():
    baker.make(Workflow, trigger_type='DAILY_AT_TIME', trigger_config={'time': '09:30'}, actions=['NOTIFY_MANAGER'])

    _run_workflows_at('monday', '09:30')

    assert WorkflowLog.objects.get().trigger_type == 'DAILY_AT_TIME'


def test_daily_at_time_does_not_trigger_at_wrong_time():
    baker.make(Workflow, trigger_type='DAILY_AT_TIME', trigger_config={'time': '09:30'}, actions=['NOTIFY_MANAGER'])

    _run_workflows_at('monday', '10:00')

    assert WorkflowLog.objects.count() == 0


def test_weekly_at_time_triggers_on_correct_day_and_time():
    baker.make(
        Workflow,
        trigger_type='WEEKLY_AT_TIME',
        trigger_config={'day_of_week': 'wednesday', 'time': '08:00'},
        actions=['EMAIL_CEO'],
    )

    _run_workflows_at('wednesday', '08:00')

    assert WorkflowLog.objects.get().trigger_type == 'WEEKLY_AT_TIME'


def test_weekly_at_time_does_not_trigger_on_wrong_day():
    baker.make(
        Workflow,
        trigger_type='WEEKLY_AT_TIME',
        trigger_config={'day_of_week': 'wednesday', 'time': '08:00'},
        actions=['EMAIL_CEO'],
    )

    _run_workflows_at('tuesday', '08:00')

    assert WorkflowLog.objects.count() == 0


def test_inactive_workflow_not_triggered_by_command():
    baker.make(
        Workflow,
        trigger_type='DAILY_AT_TIME',
        trigger_config={'time': '09:30'},
        actions=['NOTIFY_MANAGER'],
        is_active=False,
    )

    _run_workflows_at('monday', '09:30')

    assert WorkflowLog.objects.count() == 0


def test_managed_by_workflow_skipped_by_command():
    """Workflows with managed_by in trigger_config are owned by dedicated commands."""
    baker.make(
        Workflow,
        trigger_type='WEEKLY_AT_TIME',
        trigger_config={'day_of_week': 'monday', 'time': '06:00', 'managed_by': 'run_hr_agent'},
        actions=['GENERATE_REPORT'],
    )

    _run_workflows_at('monday', '06:00')

    assert WorkflowLog.objects.count() == 0
