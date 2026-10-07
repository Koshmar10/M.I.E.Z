"""Tests for the assistant tools in api/agent/operations.py."""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from api.agent.operations import (
    create_leave_request,
    create_ticket,
    generate_report,
    get_attendance_trend,
    get_dashboard_summary,
    get_headcount_vs_workload,
    get_leave_patterns,
    query_employees,
    query_inventory,
    query_orders,
    query_tickets,
)
from api.models import Attendance, Department, LeaveRequest, Order, Product, Report, StockMovement, Ticket, User


@pytest.fixture
def sales_department():
    return baker.make(Department, name='Sales', slug='sales')


@pytest.fixture
def hr_department():
    return baker.make(Department, name='Human Resources', slug='hr')


def _kpi(summary, label):
    return next(k['value'] for k in summary['kpis'] if k['label'] == label)


# ── get_dashboard_summary ────────────────────────────────────────────────────


def test_get_dashboard_summary_sales_returns_standard_envelope(sales_user):
    baker.make(Order, value_ron='100.00', date=timezone.localdate(), status=Order.Status.PROCESSING)

    summary = get_dashboard_summary(module='sales', user=sales_user)

    assert summary.keys() == {'module', 'kpis', 'generated_at'}
    assert summary['module'] == 'sales'
    assert all('label' in k and 'value' in k for k in summary['kpis'])
    assert _kpi(summary, 'Orders Today') == 1
    assert _kpi(summary, 'Revenue Today (RON)') == '100.00'


def test_get_dashboard_summary_hr_returns_standard_envelope(hr_user):
    summary = get_dashboard_summary(module='hr', user=hr_user)

    assert summary.keys() == {'module', 'kpis', 'generated_at'}
    assert summary['module'] == 'hr'
    assert isinstance(summary['kpis'], list)


def test_get_dashboard_summary_it_returns_standard_envelope(it_user):
    baker.make(Ticket, status=Ticket.Status.OPEN)

    summary = get_dashboard_summary(module='it', user=it_user)

    assert summary.keys() == {'module', 'kpis', 'generated_at'}
    assert summary['module'] == 'it'
    assert _kpi(summary, 'Open Tickets') == 1


def test_get_dashboard_summary_inventory_returns_standard_envelope(inventory_user):
    baker.make(Product, stock_count=0, min_stock=5)

    summary = get_dashboard_summary(module='inventory', user=inventory_user)

    assert summary.keys() == {'module', 'kpis', 'generated_at'}
    assert summary['module'] == 'inventory'
    assert _kpi(summary, 'Out of Stock') == 1


def test_get_dashboard_summary_ceo_can_access_any_module(ceo_user):
    for module in ['sales', 'hr', 'it', 'inventory']:
        assert get_dashboard_summary(module=module, user=ceo_user)['module'] == module


def test_get_dashboard_summary_hr_denied_for_sales_role(sales_user):
    with pytest.raises(PermissionError):
        get_dashboard_summary(module='hr', user=sales_user)


def test_get_dashboard_summary_invalid_module_raises_value_error(ceo_user):
    with pytest.raises(ValueError):
        get_dashboard_summary(module='finance', user=ceo_user)


# ── Queries ──────────────────────────────────────────────────────────────────


def test_query_tickets_new_returns_only_open_tickets(it_user):
    open_ticket = baker.make(Ticket, status=Ticket.Status.OPEN)
    baker.make(Ticket, status=Ticket.Status.IN_PROGRESS)

    results = query_tickets(status='NEW', user=it_user)

    assert [(r['id'], r['status']) for r in results] == [(open_ticket.id, 'NEW')]


def test_query_tickets_filters_priority_assigned_and_limit(it_user):
    assignee = baker.make(User, role=User.Role.IT)
    baker.make(Ticket, status=Ticket.Status.OPEN, priority=Ticket.Priority.HIGH, assigned_to=assignee, _quantity=12)
    baker.make(Ticket, status=Ticket.Status.OPEN, priority=Ticket.Priority.LOW, assigned_to=assignee)

    results = query_tickets(user=it_user, status='NEW', priority='HIGH', assigned_to=assignee.id, limit=50)

    assert len(results) == 10
    assert all(item['status'] == 'NEW' for item in results)


def test_query_orders_filters_and_caps_at_ten(sales_user):
    acme = baker.make('api.Customer', name='Acme Retail')
    baker.make(Order, customer=acme, status=Order.Status.PROCESSING, channel=Order.Channel.WEBSITE, _quantity=12)
    baker.make(Order, customer=acme, status=Order.Status.SHIPPED, channel=Order.Channel.WEBSITE)
    baker.make(Order, status=Order.Status.PROCESSING, channel=Order.Channel.DIRECT)

    results = query_orders(user=sales_user, status='PROCESSING', channel='WEBSITE', customer='Acme', limit=20)

    assert len(results) == 10
    assert all(item['status'] == Order.Status.PROCESSING for item in results)
    assert all(item['channel'] == Order.Channel.WEBSITE for item in results)
    assert all('Acme' in item['customer_name'] for item in results)


def test_query_employees_denied_for_sales_role(sales_user):
    with pytest.raises(PermissionError):
        query_employees(user=sales_user)


def test_query_employees_filters_department_role_active_and_limit(hr_user, sales_department, hr_department):
    baker.make(User, role=User.Role.SALES, department=sales_department, is_active=True, _quantity=12)
    baker.make(User, role=User.Role.SALES, department=sales_department, is_active=False)
    baker.make(User, role=User.Role.HR, department=hr_department, is_active=True)

    results = query_employees(user=hr_user, department='sales', role='SALES', is_active=True, limit=99)

    assert len(results) == 10
    assert all(item['role'] == User.Role.SALES for item in results)
    assert all(item['is_active'] for item in results)
    assert all(item['department']['slug'] == 'sales' for item in results)


def test_query_inventory_filters_status_category_below_min_and_limit(inventory_user):
    baker.make(Product, category=Product.Category.ELECTRONICS, stock_count=2, min_stock=10, _quantity=12)
    baker.make(Product, category=Product.Category.ACCESSORIES, stock_count=2, min_stock=10)
    baker.make(Product, category=Product.Category.ELECTRONICS, stock_count=30, min_stock=10)

    results = query_inventory(
        user=inventory_user, status='low_stock', category='Electronics', below_min_stock=True, limit=50
    )

    assert len(results) == 10
    assert all(item['status'] == 'Low Stock' for item in results)
    assert all(item['category'] == Product.Category.ELECTRONICS for item in results)


# ── Actions ──────────────────────────────────────────────────────────────────


def test_create_ticket_returns_ticket_number_and_status(sales_user):
    result = create_ticket(
        user=sales_user,
        title='Laptop replacement',
        description='Battery no longer holds charge',
        category='Hardware',
        location='HQ',
    )

    assert result['status'] == Ticket.Status.OPEN
    assert Ticket.objects.get(ticket_number=result['ticket_number']).requested_by == sales_user


def test_create_ticket_available_to_all_roles(ceo_user, hr_user, sales_user, it_user):
    for user in [ceo_user, hr_user, sales_user, it_user]:
        assert 'ticket_number' in create_ticket(user=user, title=f'Ticket by {user.username}')


def test_create_leave_request_returns_id_and_pending_status(hr_user):
    employee = baker.make(User, role=User.Role.SALES)
    tomorrow = timezone.localdate() + timedelta(days=1)

    result = create_leave_request(
        user=hr_user, employee=employee.id, from_date=tomorrow, to_date=tomorrow + timedelta(days=2), reason='Vacation'
    )

    assert result['status'] == LeaveRequest.Status.PENDING
    assert LeaveRequest.objects.get(id=result['id']).employee == employee


def test_create_leave_request_defaults_employee_to_requesting_user(sales_user):
    tomorrow = timezone.localdate() + timedelta(days=1)

    result = create_leave_request(user=sales_user, from_date=tomorrow, to_date=tomorrow + timedelta(days=2))

    assert result['status'] == LeaveRequest.Status.PENDING
    assert LeaveRequest.objects.get(id=result['id']).employee == sales_user


def test_create_leave_request_denied_for_ceo(ceo_user):
    tomorrow = timezone.localdate() + timedelta(days=1)
    with pytest.raises(PermissionError):
        create_leave_request(user=ceo_user, from_date=tomorrow, to_date=tomorrow + timedelta(days=2))


def test_generate_report_denied_for_non_manager_role(sales_user):
    report = baker.make(Report, slug='sales-report', category='Sales')
    with pytest.raises(PermissionError):
        generate_report(user=sales_user, slug=report.slug)


# ── HR insights ──────────────────────────────────────────────────────────────


def test_get_attendance_trend_flags_low_department_attendance_and_repeated_absence(hr_user, hr_department):
    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    absent = baker.make(User, role=User.Role.HR, department=hr_department, first_name='Ana', last_name='Popa')
    on_leave = baker.make(User, role=User.Role.HR, department=hr_department, first_name='Maria', last_name='Ionescu')
    for offset in range(4):  # 4 unexcused absences -> repeated absence flag
        baker.make(
            Attendance, employee=absent, date=week_start + timedelta(days=offset), status=Attendance.Status.ABSENT
        )
    baker.make(Attendance, employee=absent, date=week_start + timedelta(days=4), status=Attendance.Status.PRESENT)
    baker.make(Attendance, employee=on_leave, date=week_start, status=Attendance.Status.LEAVE)

    result = get_attendance_trend(user=hr_user, weeks=4)

    row = next(r for r in result if r['department'] == hr_department.name and r['week'] == week_start.isoformat())
    assert row['attendance_pct'] < 85.0
    assert row['flag_low_attendance']
    assert row['approved_leave_count'] == 1
    assert row['unexcused_absence_count'] == 4
    unexcused = next(i for i in row['employees_absent'] if i['absence_type'] == 'unexcused')
    approved = next(i for i in row['employees_absent'] if i['absence_type'] == 'approved_leave')
    assert (unexcused['name'], unexcused['count'], unexcused['flag_repeated_absence']) == ('Ana Popa', 4, True)
    assert (approved['name'], approved['count'], approved['flag_repeated_absence']) == ('Maria Ionescu', 1, False)


def test_get_attendance_trend_denied_for_sales_role(sales_user):
    with pytest.raises(PermissionError):
        get_attendance_trend(user=sales_user, weeks=4)


def test_get_leave_patterns_detects_monday_friday_medical_and_rejection_follow_up(hr_user, hr_department):
    today = timezone.localdate()
    now = timezone.now()

    def leave(employee, from_date, created_ago, **fields):
        request = baker.make(
            LeaveRequest, employee=employee, department=hr_department, from_date=from_date, to_date=from_date, **fields
        )
        LeaveRequest.objects.filter(pk=request.pk).update(created_at=now - created_ago)

    monday_taker = baker.make(User, role=User.Role.HR, department=hr_department, first_name='Ana', last_name='Popescu')
    for week in range(3):
        leave(
            monday_taker,
            today - timedelta(days=today.weekday() + 7 * week),
            timedelta(weeks=week, days=today.weekday()),
            type=LeaveRequest.Type.VACATION,
        )

    sick = baker.make(User, role=User.Role.HR, department=hr_department, first_name='Maria', last_name='Ionescu')
    for index, days_ago in enumerate([1, 4, 10]):
        leave(sick, today - timedelta(days=days_ago), timedelta(days=index * 3), type=LeaveRequest.Type.SICK)

    rejected = baker.make(User, role=User.Role.HR, department=hr_department, first_name='Elena', last_name='Marin')
    vacation = LeaveRequest.Type.VACATION
    leave(rejected, today - timedelta(days=14), timedelta(days=10), type=vacation, status=LeaveRequest.Status.REJECTED)
    leave(rejected, today - timedelta(days=7), timedelta(days=2), type=vacation, status=LeaveRequest.Status.PENDING)

    observations = get_leave_patterns(user=hr_user, weeks=8)

    by_type = {o['pattern_type']: o for o in observations}
    assert by_type['monday_friday_leave_requests']['employee_name'] == 'Ana Popescu'
    assert by_type['monday_friday_leave_requests']['occurrences'] == 3
    assert by_type['medical_leave_cluster']['department'] == hr_department.name
    assert by_type['medical_leave_cluster']['occurrences'] == 3
    assert by_type['leave_after_rejection']['employee_name'] == 'Elena Marin'
    assert all('Observation:' in o['description'] for o in by_type.values())


def test_get_leave_patterns_denied_for_sales_role(sales_user):
    with pytest.raises(PermissionError):
        get_leave_patterns(user=sales_user, weeks=8)


def test_get_headcount_vs_workload_returns_ratios_and_threshold_statuses(hr_user, sales_user, it_user):
    today = timezone.localdate()
    baker.make(User, role=User.Role.SALES, is_active=True)  # 2 active sales with the fixture user
    baker.make(User, role=User.Role.INVENTORY, is_active=True, _quantity=4)
    baker.make(Order, status=Order.Status.PROCESSING, _quantity=11)
    baker.make(Ticket, status=Ticket.Status.OPEN, _quantity=12)
    product = baker.make(Product)
    for days in range(1, 9):
        baker.make(
            StockMovement,
            movement_type=StockMovement.Type.INBOUND,
            product=product,
            quantity=1,
            expected_date=today + timedelta(days=days),
        )

    results = get_headcount_vs_workload(user=hr_user)

    rows = {r['department']: (r['active_headcount'], r['workload_items'], r['ratio'], r['status']) for r in results}
    assert [r['department'] for r in results] == ['Sales', 'IT', 'Inventory']
    assert rows['Sales'] == (2, 11, 5.5, 'warning')
    assert rows['IT'] == (1, 12, 12.0, 'critical')
    assert rows['Inventory'] == (4, 8, 2.0, 'ok')


def test_get_headcount_vs_workload_denied_for_sales_role(sales_user):
    with pytest.raises(PermissionError):
        get_headcount_vs_workload(user=sales_user)
