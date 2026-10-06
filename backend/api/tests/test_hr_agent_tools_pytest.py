import datetime

import pytest
from django.utils import timezone
from model_bakery import baker

from api.agent.operations import (
    get_attendance_trend,
    get_expiring_contracts,
    get_headcount_vs_workload,
    get_leave_patterns,
    get_payroll_anomalies,
)
from api.models import Attendance, Contract, LeaveRequest, Order, PayrollEntry, StockMovement, Ticket, User


pytestmark = pytest.mark.django_db


def _iso_monday(value: datetime.date) -> datetime.date:
    return value - datetime.timedelta(days=value.weekday())


def test_get_attendance_trend_calculates_pct_and_flags_departments_below_85():
    today = timezone.localdate()
    week_start = _iso_monday(today)

    hr_user = baker.make(User, role=User.Role.HR)
    sales_dept = baker.make('api.Department', name='Sales', slug='sales')
    hr_dept = baker.make('api.Department', name='HR', slug='hr')

    sales_employee = baker.make(User, role=User.Role.SALES, department=sales_dept)
    hr_employee = baker.make(User, role=User.Role.HR, department=hr_dept)

    baker.make(Attendance, employee=sales_employee, date=week_start + datetime.timedelta(days=0), status=Attendance.Status.PRESENT)
    baker.make(Attendance, employee=sales_employee, date=week_start + datetime.timedelta(days=1), status=Attendance.Status.REMOTE)
    baker.make(Attendance, employee=sales_employee, date=week_start + datetime.timedelta(days=2), status=Attendance.Status.ABSENT)
    baker.make(Attendance, employee=sales_employee, date=week_start + datetime.timedelta(days=3), status=Attendance.Status.ABSENT)

    baker.make(Attendance, employee=hr_employee, date=week_start + datetime.timedelta(days=0), status=Attendance.Status.PRESENT)
    baker.make(Attendance, employee=hr_employee, date=week_start + datetime.timedelta(days=1), status=Attendance.Status.PRESENT)

    trend = get_attendance_trend(user=hr_user, weeks=4)

    sales_row = next(item for item in trend if item['department'] == 'Sales' and item['week'] == week_start.isoformat())
    hr_row = next(item for item in trend if item['department'] == 'HR' and item['week'] == week_start.isoformat())

    assert sales_row['attendance_pct'] == 50.0
    assert sales_row['flag_low_attendance'] is True
    assert hr_row['attendance_pct'] == 100.0
    assert hr_row['flag_low_attendance'] is False


def test_get_attendance_trend_marks_employee_with_3_absences_in_4_weeks():
    today = timezone.localdate()
    current_week_start = _iso_monday(today)

    hr_user = baker.make(User, role=User.Role.HR)
    hr_dept = baker.make('api.Department', name='Human Resources', slug='human-resources')
    employee = baker.make(User, role=User.Role.HR, department=hr_dept, first_name='Ana', last_name='Pop')

    baker.make(Attendance, employee=employee, date=current_week_start, status=Attendance.Status.ABSENT)
    baker.make(Attendance, employee=employee, date=current_week_start - datetime.timedelta(days=7), status=Attendance.Status.ABSENT)
    baker.make(Attendance, employee=employee, date=current_week_start - datetime.timedelta(days=14), status=Attendance.Status.ABSENT)
    baker.make(Attendance, employee=employee, date=current_week_start + datetime.timedelta(days=1), status=Attendance.Status.PRESENT)

    trend = get_attendance_trend(user=hr_user, weeks=4)
    current_row = next(item for item in trend if item['department'] == 'Human Resources' and item['week'] == current_week_start.isoformat())
    flagged_absence = next(item for item in current_row['employees_absent'] if item['absence_type'] == 'unexcused')

    assert flagged_absence['name'] == 'Ana Pop'
    assert flagged_absence['flag_repeated_absence'] is True


def test_get_expiring_contracts_returns_only_contracts_within_60_days():
    today = timezone.localdate()

    hr_user = baker.make(User, role=User.Role.HR)
    dept = baker.make('api.Department', name='IT', slug='it')
    employee_in_window = baker.make(User, role=User.Role.IT, department=dept, first_name='Ana', last_name='Pop')
    employee_outside_window = baker.make(User, role=User.Role.IT, department=dept)

    baker.make(
        Contract,
        employee=employee_in_window,
        department=dept,
        contract_number='CTR-IN-60',
        end_date=today + datetime.timedelta(days=30),
    )
    baker.make(
        Contract,
        employee=employee_outside_window,
        department=dept,
        contract_number='CTR-OUT-60',
        end_date=today + datetime.timedelta(days=90),
    )

    results = get_expiring_contracts(user=hr_user, days=60)

    assert len(results) == 1
    assert results[0]['employee_name'] == 'Ana Pop'


def test_get_expiring_contracts_sets_has_open_tickets_when_employee_has_non_resolved_tickets():
    today = timezone.localdate()

    hr_user = baker.make(User, role=User.Role.HR)
    dept = baker.make('api.Department', name='IT Ops', slug='it-ops')
    employee = baker.make(User, role=User.Role.IT, department=dept, first_name='Mihai', last_name='Ionescu')

    baker.make(
        Contract,
        employee=employee,
        department=dept,
        contract_number='CTR-TICKETS',
        end_date=today + datetime.timedelta(days=20),
    )
    baker.make(
        Ticket,
        ticket_number='TKT-HAS-OPEN',
        requested_by=employee,
        assigned_to=employee,
        status=Ticket.Status.OPEN,
    )

    results = get_expiring_contracts(user=hr_user, days=60)

    assert results[0]['employee_name'] == 'Mihai Ionescu'
    assert results[0]['has_open_tickets'] is True


def test_get_payroll_anomalies_flags_bonus_over_2x_average():
    today = timezone.localdate()
    month_start = today.replace(day=1)

    hr_user = baker.make(User, role=User.Role.HR)
    employee = baker.make(User, role=User.Role.SALES, first_name='Andrei', last_name='Marin')

    baker.make(PayrollEntry, employee=employee, month=month_start - datetime.timedelta(days=30), gross_salary_ron='1100.00', net_salary_ron='1000.00')
    baker.make(PayrollEntry, employee=employee, month=month_start - datetime.timedelta(days=60), gross_salary_ron='1100.00', net_salary_ron='1000.00')
    baker.make(PayrollEntry, employee=employee, month=month_start, gross_salary_ron='1300.00', net_salary_ron='1000.00')

    anomalies = get_payroll_anomalies(user=hr_user)

    assert any(item['anomaly_type'] == 'bonus_spike' and item['employee_name'] == 'Andrei Marin' for item in anomalies)


def test_get_payroll_anomalies_flags_employee_missing_from_current_month():
    today = timezone.localdate()
    month_start = today.replace(day=1)

    hr_user = baker.make(User, role=User.Role.HR)
    present_employee = baker.make(User, role=User.Role.HR, first_name='Present', last_name='Employee')
    missing_employee = baker.make(User, role=User.Role.HR, first_name='Missing', last_name='Employee')

    baker.make(PayrollEntry, employee=present_employee, month=month_start, gross_salary_ron='3000.00', net_salary_ron='2500.00')

    anomalies = get_payroll_anomalies(user=hr_user)

    assert any(item['anomaly_type'] == 'missing_payroll_entry' and item['employee_name'] == 'Missing Employee' for item in anomalies)


def test_get_payroll_anomalies_does_not_flag_bonus_within_20_percent_of_average():
    today = timezone.localdate()
    month_start = today.replace(day=1)

    hr_user = baker.make(User, role=User.Role.HR)
    employee = baker.make(User, role=User.Role.SALES, first_name='Calm', last_name='Bonus')

    baker.make(PayrollEntry, employee=employee, month=month_start - datetime.timedelta(days=30), gross_salary_ron='1100.00', net_salary_ron='1000.00')
    baker.make(PayrollEntry, employee=employee, month=month_start - datetime.timedelta(days=60), gross_salary_ron='1100.00', net_salary_ron='1000.00')
    baker.make(PayrollEntry, employee=employee, month=month_start, gross_salary_ron='1115.00', net_salary_ron='1000.00')

    anomalies = get_payroll_anomalies(user=hr_user)

    assert not any(item['anomaly_type'] == 'bonus_spike' and item['employee_name'] == 'Calm Bonus' for item in anomalies)


def test_get_leave_patterns_detects_monday_friday_pattern_after_3_occurrences():
    today = timezone.localdate()

    hr_user = baker.make(User, role=User.Role.HR)
    dept = baker.make('api.Department', name='People', slug='people')
    employee = baker.make(User, role=User.Role.HR, department=dept, first_name='Ioana', last_name='Radu')

    monday = _iso_monday(today)
    friday = monday + datetime.timedelta(days=4)
    previous_friday = friday - datetime.timedelta(days=7)

    req1 = baker.make(LeaveRequest, employee=employee, department=dept, type=LeaveRequest.Type.VACATION, from_date=monday, to_date=monday)
    req2 = baker.make(LeaveRequest, employee=employee, department=dept, type=LeaveRequest.Type.VACATION, from_date=friday, to_date=friday)
    req3 = baker.make(LeaveRequest, employee=employee, department=dept, type=LeaveRequest.Type.VACATION, from_date=previous_friday, to_date=previous_friday)

    req1_created = timezone.make_aware(datetime.datetime.combine(monday, datetime.time(hour=9, minute=0)))
    req2_created = timezone.make_aware(datetime.datetime.combine(friday, datetime.time(hour=9, minute=0)))
    req3_created = timezone.make_aware(datetime.datetime.combine(previous_friday, datetime.time(hour=9, minute=0)))

    LeaveRequest.objects.filter(id=req1.id).update(created_at=req1_created)
    LeaveRequest.objects.filter(id=req2.id).update(created_at=req2_created)
    LeaveRequest.objects.filter(id=req3.id).update(created_at=req3_created)

    patterns = get_leave_patterns(user=hr_user, weeks=8)

    pattern = next(item for item in patterns if item['pattern_type'] == 'monday_friday_leave_requests')
    assert pattern['employee_name'] == 'Ioana Radu'
    assert pattern['occurrences'] == 3


def test_get_headcount_vs_workload_computes_ratio_per_department():
    today = timezone.localdate()

    hr_user = baker.make(User, role=User.Role.HR)

    baker.make(User, role=User.Role.SALES, is_active=True)
    baker.make(User, role=User.Role.SALES, is_active=True)
    baker.make(User, role=User.Role.IT, is_active=True)
    baker.make(User, role=User.Role.INVENTORY, is_active=True)

    customer = baker.make('api.Customer')
    baker.make(Order, customer=customer, status=Order.Status.PROCESSING, _quantity=6)
    baker.make(Ticket, status=Ticket.Status.OPEN, ticket_number='TKT-RT-0001')
    baker.make(Ticket, status=Ticket.Status.OPEN, ticket_number='TKT-RT-0002')

    product = baker.make('api.Product', sku='SKU-RATIO-1')
    supplier = baker.make('api.Supplier')
    baker.make(
        StockMovement,
        movement_type=StockMovement.Type.INBOUND,
        expected_date=today + datetime.timedelta(days=1),
        product=product,
        supplier=supplier,
        _quantity=4,
    )

    rows = get_headcount_vs_workload(user=hr_user)

    sales_row = next(item for item in rows if item['department'] == 'Sales')
    it_row = next(item for item in rows if item['department'] == 'IT')
    inventory_row = next(item for item in rows if item['department'] == 'Inventory')

    assert sales_row['ratio'] == 3.0
    assert it_row['ratio'] == 2.0
    assert inventory_row['ratio'] == 4.0


def test_get_headcount_vs_workload_sets_status_when_ratio_exceeds_threshold():
    today = timezone.localdate()

    hr_user = baker.make(User, role=User.Role.HR)
    baker.make(User, role=User.Role.SALES, is_active=True)

    customer = baker.make('api.Customer')
    baker.make(Order, customer=customer, status=Order.Status.PROCESSING, _quantity=11)

    rows = get_headcount_vs_workload(user=hr_user)
    sales_row = next(item for item in rows if item['department'] == 'Sales')

    assert sales_row['ratio'] == 11.0
    assert sales_row['status'] == 'critical'
