"""Business tools exposed to the MIEZ Assistant agent."""

from __future__ import annotations

import datetime
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from api.models import (
    Asset,
    Attendance,
    Contract,
    Customer,
    Department,
    Invoice,
    LeaveRequest,
    Notification,
    Order,
    PayrollEntry,
    Product,
    Report,
    StockMovement,
    Supplier,
    SystemStatus,
    Ticket,
    TicketComment,
    User,
)
from api.report_utils import generate_report_file
from api.services import hr as hr_services
from api.services import it as it_services
from api.services import sales as sales_services

from .tools import Tool, agent_tool, get_registry, register_tool


def _parse_iso_week(week: str) -> tuple[datetime.date, datetime.date]:
    """Parse ISO week string '2026-W18' to (monday, sunday)."""
    year_str, week_str = week.split('-W')
    monday = datetime.date.fromisocalendar(int(year_str), int(week_str), 1)
    return monday, monday + timedelta(days=6)


def _permission_error(message: str) -> PermissionError:
    return PermissionError(message)


def _require_roles(user: User, allowed_roles: list[str], message: str) -> None:
    if user.role not in allowed_roles:
        raise _permission_error(message)


def can_generate_reports(user: User) -> bool:
    if user.role == User.Role.CEO:
        return True

    position = (user.position or '').strip().lower()
    if not position:
        return False

    return any(token in position for token in ('manager', 'lead', 'head', 'director'))


def _serialize_department(department: Department | None) -> dict[str, Any] | None:
    if department is None:
        return None
    return {
        'id': department.id,
        'name': department.name,
        'slug': department.slug,
    }


def _serialize_ticket(ticket: Ticket) -> dict[str, Any]:
    return {
        'id': ticket.id,
        'ticket_number': ticket.ticket_number,
        'title': ticket.title,
        'status': 'NEW' if ticket.status == Ticket.Status.OPEN else ticket.status,
        'priority': ticket.priority,
        'requested_by_id': ticket.requested_by_id,
        'requested_by_username': ticket.requested_by.username if ticket.requested_by else None,
        'department': _serialize_department(ticket.department),
    }


def _serialize_employee(employee: User) -> dict[str, Any]:
    return {
        'id': employee.id,
        'username': employee.username,
        'email': employee.email,
        'role': employee.role,
        'department': _serialize_department(employee.department),
        'is_active': employee.is_active,
    }


def _serialize_order(order: Order) -> dict[str, Any]:
    return {
        'id': order.id,
        'order_number': order.order_number,
        'status': order.status,
        'channel': order.channel,
        'customer_id': order.customer_id,
        'customer_name': order.customer.name if order.customer else None,
        'value_ron': f'{Decimal(str(order.value_ron or 0)).quantize(Decimal("0.01")):.2f}',
        'date': order.date.isoformat() if order.date else None,
    }


def _serialize_inventory(product: Product) -> dict[str, Any]:
    return {
        'id': product.id,
        'name': product.name,
        'sku': product.sku,
        'category': product.category,
        'stock_count': product.stock_count,
        'min_stock': product.min_stock,
        'status': product.availability,
    }


def _serialize_customer(customer: Customer) -> dict[str, Any]:
    return {
        'id': customer.id,
        'name': customer.name,
        'contact_name': customer.contact_name,
        'contact_email': customer.contact_email,
        'tier': customer.tier,
        'location': customer.location,
    }


def _serialize_invoice(invoice: Invoice) -> dict[str, Any]:
    return {
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'status': invoice.status,
        'order_number': invoice.order.order_number if invoice.order else None,
        'customer_name': invoice.order.customer.name if invoice.order and invoice.order.customer else None,
        'amount_ron': f'{Decimal(str(invoice.amount_ron or 0)).quantize(Decimal("0.01")):.2f}',
        'issued_date': invoice.issued_date.isoformat() if invoice.issued_date else None,
        'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
    }


def _serialize_supplier(supplier: Supplier) -> dict[str, Any]:
    return {
        'id': supplier.id,
        'name': supplier.name,
        'contact_email': supplier.contact_email,
        'contact_phone': supplier.contact_phone,
        'address': supplier.address,
    }


def _serialize_stock_movement(movement: StockMovement) -> dict[str, Any]:
    return {
        'id': movement.id,
        'movement_type': movement.movement_type,
        'product_name': movement.product.name if movement.product else None,
        'sku': movement.product.sku if movement.product else None,
        'supplier_name': movement.supplier.name if movement.supplier else None,
        'quantity': movement.quantity,
        'expected_date': movement.expected_date.isoformat() if movement.expected_date else None,
        'created_at': movement.created_at.isoformat() if movement.created_at else None,
    }


def _serialize_asset(asset: Asset) -> dict[str, Any]:
    return {
        'id': asset.id,
        'name': asset.name,
        'serial_number': asset.serial_number,
        'category': asset.category,
        'status': asset.status,
        'assigned_to_id': asset.assigned_to_id,
        'assigned_to_username': asset.assigned_to.username if asset.assigned_to else None,
    }


def _serialize_system_status(status_row: SystemStatus) -> dict[str, Any]:
    return {
        'id': status_row.id,
        'name': status_row.name,
        'status': status_row.status,
        'uptime_pct': f'{Decimal(str(status_row.uptime_pct or 0)).quantize(Decimal("0.01")):.2f}',
        'last_incident_date': status_row.last_incident_date.isoformat() if status_row.last_incident_date else None,
    }


def _serialize_notification(notification: Notification) -> dict[str, Any]:
    return {
        'id': notification.id,
        'type': notification.type,
        'title': notification.title,
        'body': notification.body,
        'is_read': notification.is_read,
        'link': notification.link,
        'created_at': notification.created_at.isoformat() if notification.created_at else None,
    }


def _normalized_limit(limit: int | None, default_limit: int = 10) -> int:
    if limit is None:
        return default_limit
    return max(1, min(int(limit), 10))


def _month_start(value: datetime.date) -> datetime.date:
    return value.replace(day=1)


def _shift_month(value: datetime.date, months: int) -> datetime.date:
    total_month = (value.year * 12 + value.month - 1) + months
    year = total_month // 12
    month = total_month % 12 + 1
    return datetime.date(year, month, 1)


@agent_tool(
    name='get_dashboard_summary',
    description='Get KPI summary for a business module. module must be one of: sales, hr, it, inventory.',
    schema={
        'type': 'object',
        'properties': {
            'module': {'type': 'string', 'enum': ['sales', 'hr', 'it', 'inventory']},
        },
        'required': ['module'],
    },
)
def get_dashboard_summary(module: str, user: User) -> dict[str, Any]:
    module_name = (module or '').strip().lower()

    def _result(kpis: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            'module': module_name,
            'kpis': kpis,
            'generated_at': timezone.now().isoformat(),
        }

    if module_name == 'sales':
        _require_roles(
            user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can access the sales dashboard summary.'
        )

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())
        base_qs = Order.objects.all()

        today_stats = base_qs.filter(date=today).aggregate(
            orders_today=Count('id'),
            revenue_today_ron=Sum('value_ron'),
        )
        yesterday_stats = base_qs.filter(date=yesterday).aggregate(
            orders_yesterday=Count('id'),
            revenue_yesterday_ron=Sum('value_ron'),
        )

        def _pct(current: Any, previous: Any) -> float:
            c, p = float(current or 0), float(previous or 0)
            if p == 0:
                return 100.0 if c > 0 else 0.0
            return round(((c - p) / p) * 100, 2)

        orders_today = today_stats['orders_today'] or 0
        revenue_today = Decimal(str(today_stats['revenue_today_ron'] or 0)).quantize(Decimal('0.01'))
        orders_yesterday = yesterday_stats['orders_yesterday'] or 0
        revenue_yesterday = yesterday_stats['revenue_yesterday_ron'] or 0

        return _result(
            [
                {'label': 'Orders Today', 'value': orders_today},
                {'label': 'Revenue Today (RON)', 'value': f'{revenue_today:.2f}'},
                {'label': 'Processing Orders', 'value': base_qs.filter(status=Order.Status.PROCESSING).count()},
                {
                    'label': 'Cancelled This Week',
                    'value': base_qs.filter(
                        status=Order.Status.CANCELLED, date__gte=start_of_week, date__lte=today
                    ).count(),
                },
                {'label': 'Orders Change vs Yesterday (%)', 'value': _pct(orders_today, orders_yesterday)},
                {'label': 'Revenue Change vs Yesterday (%)', 'value': _pct(revenue_today, revenue_yesterday)},
            ]
        )

    if module_name == 'hr':
        _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access the HR dashboard summary.')

        today = timezone.localdate()
        month_start = today.replace(day=1)
        employees = User.objects.all()
        total = employees.count()
        active = employees.filter(is_active=True).count()
        full_time = employees.filter(full_time=True).count()

        return _result(
            [
                {'label': 'Total Employees', 'value': total},
                {'label': 'Active Employees', 'value': active},
                {
                    'label': 'New Hires This Month',
                    'value': employees.filter(start_date__gte=month_start, start_date__lte=today).count(),
                },
                {
                    'label': 'Pending Leave Requests',
                    'value': LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
                },
                {'label': 'Full-Time Employees', 'value': full_time},
                {'label': 'Retention Rate (%)', 'value': round((active / total) * 100, 1) if total else 0.0},
            ]
        )

    if module_name == 'it':
        _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can access the IT dashboard summary.')

        now = timezone.now()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

        stats = Ticket.objects.aggregate(
            open_tickets=Count('id', filter=Q(status=Ticket.Status.OPEN)),
            in_progress=Count('id', filter=Q(status=Ticket.Status.IN_PROGRESS)),
            resolved_this_week=Count('id', filter=Q(status=Ticket.Status.RESOLVED, resolved_at__gte=week_start)),
            critical_open=Count(
                'id', filter=Q(status=Ticket.Status.OPEN, priority__in=[Ticket.Priority.HIGH, Ticket.Priority.URGENT])
            ),
        )

        resolved_qs = Ticket.objects.filter(status=Ticket.Status.RESOLVED, resolved_at__gte=week_start).annotate(
            duration=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        )
        perf = resolved_qs.aggregate(
            avg_res_time=Avg('duration'), sla_met=Count('id', filter=Q(duration__lte=timedelta(hours=4)))
        )

        avg_hrs = round(perf['avg_res_time'].total_seconds() / 3600, 2) if perf['avg_res_time'] else 0.0
        total_resolved = stats['resolved_this_week'] or 0
        sla_pct = round((perf['sla_met'] / total_resolved) * 100, 2) if total_resolved else 0.0

        return _result(
            [
                {'label': 'Open Tickets', 'value': stats['open_tickets']},
                {'label': 'In Progress', 'value': stats['in_progress']},
                {'label': 'Resolved This Week', 'value': total_resolved},
                {'label': 'Critical Open', 'value': stats['critical_open']},
                {'label': 'Avg Resolution Time (hrs)', 'value': avg_hrs},
                {'label': 'SLA Met (%)', 'value': sla_pct},
            ]
        )

    if module_name == 'inventory':
        _require_roles(
            user,
            [User.Role.CEO, User.Role.INVENTORY],
            'Only CEO and Inventory can access the inventory dashboard summary.',
        )

        import datetime as _dt

        today = _dt.date.today()

        return _result(
            [
                {'label': 'Total Products', 'value': Product.objects.count()},
                {
                    'label': 'Low Stock',
                    'value': Product.objects.filter(stock_count__lt=F('min_stock'), stock_count__gt=0).count(),
                },
                {'label': 'Out of Stock', 'value': Product.objects.filter(stock_count=0).count()},
                {
                    'label': 'Deliveries Today',
                    'value': StockMovement.objects.filter(
                        movement_type=StockMovement.Type.INBOUND, expected_date=today
                    ).count(),
                },
            ]
        )

    raise ValueError(f'Unsupported module: {module}. Must be one of: sales, hr, it, inventory.')


@agent_tool(name='query_tickets', description='Query tickets by status.')
def query_tickets(
    user: User,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: int | str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can query tickets.')

    queryset = Ticket.objects.select_related('department', 'requested_by', 'assigned_to').all()

    status_name = (status or '').strip().upper()
    status_map = {
        'NEW': Ticket.Status.OPEN,
        'OPEN': Ticket.Status.OPEN,
        'IN_PROGRESS': Ticket.Status.IN_PROGRESS,
        'RESOLVED': Ticket.Status.RESOLVED,
        'CLOSED': Ticket.Status.CLOSED,
    }
    if status_name and status_name not in status_map:
        raise ValueError(f'Unsupported ticket status: {status}')
    if status_name:
        queryset = queryset.filter(status=status_map[status_name])

    if priority:
        priority_name = priority.strip().upper()
        valid_priorities = {choice[0] for choice in Ticket.Priority.choices}
        if priority_name not in valid_priorities:
            raise ValueError(f'Unsupported ticket priority: {priority}')
        queryset = queryset.filter(priority=priority_name)

    if assigned_to is not None:
        if isinstance(assigned_to, int) or (isinstance(assigned_to, str) and assigned_to.isdigit()):
            queryset = queryset.filter(assigned_to_id=int(assigned_to))
        elif isinstance(assigned_to, str):
            queryset = queryset.filter(assigned_to__username=assigned_to)
        else:
            raise ValueError('assigned_to must be a user id or username')

    tickets = queryset.order_by('-created_at')[: _normalized_limit(limit)]
    return [_serialize_ticket(ticket) for ticket in tickets]


@agent_tool(name='query_employees', description='Query employees.')
def query_employees(
    user: User,
    department: int | str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can query employees.')

    employees = User.objects.select_related('department').all()

    if department is not None:
        if isinstance(department, int) or (isinstance(department, str) and department.isdigit()):
            employees = employees.filter(department_id=int(department))
        elif isinstance(department, str):
            employees = employees.filter(Q(department__slug=department) | Q(department__name__iexact=department))
        else:
            raise ValueError('department must be an id, slug, or name')

    if role:
        role_name = role.strip().upper()
        valid_roles = {choice[0] for choice in User.Role.choices}
        if role_name not in valid_roles:
            raise ValueError(f'Unsupported employee role: {role}')
        employees = employees.filter(role=role_name)

    if is_active is not None:
        employees = employees.filter(is_active=bool(is_active))

    employees = employees.order_by('id')[: _normalized_limit(limit)]
    return [_serialize_employee(employee) for employee in employees]


@agent_tool(name='query_orders', description='Query orders by status, channel, and customer.')
def query_orders(
    user: User,
    status: str | None = None,
    channel: str | None = None,
    customer: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can query orders.')

    queryset = Order.objects.select_related('customer').all()

    if status:
        status_name = status.strip().upper()
        valid_statuses = {choice[0] for choice in Order.Status.choices}
        if status_name not in valid_statuses:
            raise ValueError(f'Unsupported order status: {status}')
        queryset = queryset.filter(status=status_name)

    if channel:
        channel_name = channel.strip().upper()
        valid_channels = {choice[0] for choice in Order.Channel.choices}
        if channel_name not in valid_channels:
            raise ValueError(f'Unsupported order channel: {channel}')
        queryset = queryset.filter(channel=channel_name)

    if customer:
        queryset = queryset.filter(customer__name__icontains=customer)

    orders = queryset.order_by('-date', '-id')[: _normalized_limit(limit)]
    return [_serialize_order(order) for order in orders]


@agent_tool(name='query_inventory', description='Query inventory by status, category, and stock thresholds.')
def query_inventory(
    user: User,
    status: str | None = None,
    category: str | None = None,
    below_min_stock: bool | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.INVENTORY], 'Only CEO and Inventory can query inventory.')

    queryset = Product.objects.all()

    if category:
        category_input = category.strip()
        valid_categories = {choice[0] for choice in Product.Category.choices}
        matched = next((c for c in valid_categories if c.lower() == category_input.lower()), None)
        if matched is None:
            raise ValueError(f'Unsupported product category: {category}')
        queryset = queryset.filter(category=matched)

    if below_min_stock is True:
        queryset = queryset.filter(stock_count__lt=F('min_stock'))

    products = queryset.order_by('id')

    if status:
        status_name = status.strip().lower()
        status_map = {
            'out_of_stock': 'out of stock',
            'low_stock': 'low stock',
            'in_stock': 'in stock',
        }
        normalized_status = status_map.get(status_name, status_name)
        products = [product for product in products if product.availability.lower() == normalized_status]
        return [_serialize_inventory(product) for product in products[: _normalized_limit(limit)]]

    return [_serialize_inventory(product) for product in products[: _normalized_limit(limit)]]


@agent_tool(
    name='create_ticket',
    description='Create a support ticket. Available to all roles.',
    schema={
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'description': 'Short ticket title'},
            'description': {'type': 'string', 'description': 'Detailed description of the issue'},
            'category': {'type': 'string', 'description': 'Ticket category (e.g. Hardware, Software, Network)'},
            'priority': {'type': 'string', 'enum': ['LOW', 'MEDIUM', 'HIGH', 'URGENT']},
            'location': {'type': 'string', 'description': 'Physical location of the issue'},
        },
        'required': ['title'],
    },
)
def create_ticket(
    user: User,
    title: str,
    description: str = '',
    category: str = '',
    priority: str = Ticket.Priority.MEDIUM,
    location: str = '',
) -> dict[str, Any]:
    ticket = Ticket.objects.create(
        title=title,
        description=description,
        category=category,
        priority=priority,
        location=location,
        requested_by=user,
        status=Ticket.Status.OPEN,
    )
    return {'ticket_number': ticket.ticket_number, 'status': ticket.status}


@agent_tool(
    name='create_leave_request',
    description='Create a leave request. Not available to CEO.',
    schema={
        'type': 'object',
        'properties': {
            'employee': {'type': 'integer', 'description': 'Employee ID (HR only; defaults to the requesting user)'},
            'type': {'type': 'string', 'enum': ['VACATION', 'SICK', 'UNPAID']},
            'from_date': {'type': 'string', 'description': 'Start date (YYYY-MM-DD)'},
            'to_date': {'type': 'string', 'description': 'End date (YYYY-MM-DD)'},
            'reason': {'type': 'string', 'description': 'Reason for the leave'},
        },
        'required': ['from_date', 'to_date'],
    },
)
def create_leave_request(
    user: User,
    from_date: Any,
    to_date: Any,
    employee: Any = None,
    type: str = LeaveRequest.Type.VACATION,
    reason: str = '',
) -> dict[str, Any]:
    if user.role == User.Role.CEO:
        raise _permission_error('CEO cannot create leave requests through the assistant.')

    if employee is None:
        target_employee = user
    elif isinstance(employee, int):
        target_employee = User.objects.select_related('department').get(id=employee)
    else:
        target_employee = employee

    lr = LeaveRequest.objects.create(
        employee=target_employee,
        department=target_employee.department,
        type=type,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        status=LeaveRequest.Status.PENDING,
    )
    return {'id': lr.id, 'status': lr.status}


@agent_tool(
    name='generate_report',
    description=(
        'Generate a report HTML file. Before calling this, use query_* tools to gather real data from '
        'the app and pass it as context_data (a JSON string). The context_data will be embedded into '
        'the report so it reflects actual app data instead of placeholder numbers.'
    ),
)
def generate_report(user: User, slug: str, context_data: str | None = None) -> dict:
    if not can_generate_reports(user):
        raise _permission_error('Only the CEO or department managers can generate reports through the assistant.')

    report = Report.objects.get(slug=slug)
    generate_report_file(report, user=user, context_data=context_data or '')
    return {'report_name': report.name, 'slug': report.slug, 'status': 'generated'}


@agent_tool(
    name='query_leave_requests',
    description='Query leave requests, optionally filtered by ISO week (e.g. 2026-W18), status, or department.',
)
def query_leave_requests(
    user: User,
    week: str | None = None,
    status: str | None = None,
    department: int | str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can query leave requests.')

    queryset = LeaveRequest.objects.select_related('employee', 'department').all()

    if week:
        week_start, week_end = _parse_iso_week(week)
        queryset = queryset.filter(from_date__lte=week_end, to_date__gte=week_start)

    if status:
        status_name = status.strip().upper()
        valid_statuses = {choice[0] for choice in LeaveRequest.Status.choices}
        if status_name not in valid_statuses:
            raise ValueError(f'Unsupported leave request status: {status}')
        queryset = queryset.filter(status=status_name)

    if department is not None:
        if isinstance(department, int) or (isinstance(department, str) and department.isdigit()):
            queryset = queryset.filter(department_id=int(department))
        elif isinstance(department, str):
            queryset = queryset.filter(Q(department__slug=department) | Q(department__name__iexact=department))

    leave_requests = queryset.order_by('-created_at')[: _normalized_limit(limit)]
    return [
        {
            'id': lr.id,
            'employee_id': lr.employee_id,
            'employee_username': lr.employee.username if lr.employee else None,
            'department': _serialize_department(lr.department),
            'type': lr.type,
            'from_date': lr.from_date.isoformat() if lr.from_date else None,
            'to_date': lr.to_date.isoformat() if lr.to_date else None,
            'status': lr.status,
            'reason': lr.reason,
        }
        for lr in leave_requests
    ]


@agent_tool(
    name='query_attendance',
    description='Get attendance summary by department for an ISO week (e.g. 2026-W18). Defaults to the current week.',
)
def query_attendance(
    user: User,
    week: str | None = None,
    department: int | str | None = None,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can query attendance.')

    if week:
        week_start, week_end = _parse_iso_week(week)
    else:
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

    queryset = Attendance.objects.filter(date__gte=week_start, date__lte=week_end)

    if department is not None:
        if isinstance(department, int) or (isinstance(department, str) and department.isdigit()):
            queryset = queryset.filter(employee__department_id=int(department))
        elif isinstance(department, str):
            queryset = queryset.filter(
                Q(employee__department__slug=department) | Q(employee__department__name__iexact=department)
            )

    rows = (
        queryset.values('employee__department__name')
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status__in=[Attendance.Status.PRESENT, Attendance.Status.REMOTE])),
        )
        .order_by('employee__department__name')
    )

    return [
        {
            'department': row['employee__department__name'] or 'Unassigned',
            'total_records': row['total'],
            'present_or_remote': row['present'],
            'attendance_rate_pct': round((row['present'] / row['total']) * 100, 1) if row['total'] else 0.0,
            'week': week_start.isoformat(),
        }
        for row in rows
    ]


@agent_tool(
    name='get_attendance_trend',
    description='Get attendance trend by department for the last N weeks (default 4). Flags low department attendance and repeated unexcused absences.',
    schema={
        'type': 'object',
        'properties': {
            'weeks': {'type': 'integer', 'minimum': 1, 'maximum': 12, 'default': 4},
        },
    },
)
def get_attendance_trend(
    user: User,
    weeks: int = 4,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access attendance trends.')

    total_weeks = max(1, min(int(weeks), 12))
    today = timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    first_week_start = current_week_start - timedelta(weeks=total_weeks - 1)
    last_week_end = current_week_start + timedelta(days=6)
    repeated_absence_window_start = current_week_start - timedelta(weeks=3)

    base_queryset = Attendance.objects.filter(date__gte=first_week_start, date__lte=last_week_end)

    weekly_department_rows = (
        base_queryset.annotate(week=TruncWeek('date'))
        .values('week', 'employee__department__name')
        .annotate(
            total=Count('id'),
            attended=Count('id', filter=Q(status__in=[Attendance.Status.PRESENT, Attendance.Status.REMOTE])),
            approved_leave=Count('id', filter=Q(status=Attendance.Status.LEAVE)),
            unexcused_absence=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
        )
        .order_by('week', 'employee__department__name')
    )

    repeated_absence_rows = (
        Attendance.objects.filter(
            date__gte=repeated_absence_window_start,
            date__lte=last_week_end,
        )
        .filter(status=Attendance.Status.ABSENT)
        .values('employee_id')
        .annotate(total_unexcused_absences=Count('id'))
    )
    repeated_absence_map = {
        row['employee_id']: row['total_unexcused_absences']
        for row in repeated_absence_rows
        if (row['total_unexcused_absences'] or 0) >= 3
    }

    absent_employee_rows = (
        base_queryset.filter(status__in=[Attendance.Status.ABSENT, Attendance.Status.LEAVE])
        .annotate(week=TruncWeek('date'))
        .values(
            'week',
            'employee__department__name',
            'employee_id',
            'employee__first_name',
            'employee__last_name',
            'employee__username',
            'status',
        )
        .annotate(count=Count('id'))
        .order_by('week', 'employee__department__name', 'employee_id', 'status')
    )

    employees_absent_by_bucket: dict[tuple[datetime.date, str], list[dict[str, Any]]] = defaultdict(list)
    for row in absent_employee_rows:
        week_value = row['week']
        week_date = week_value.date() if hasattr(week_value, 'date') else week_value
        department_name = row['employee__department__name'] or 'Unassigned'

        full_name = f'{row["employee__first_name"]} {row["employee__last_name"]}'.strip() or row['employee__username']
        is_unexcused = row['status'] == Attendance.Status.ABSENT
        employee_id = row['employee_id']

        employees_absent_by_bucket[(week_date, department_name)].append(
            {
                'name': full_name,
                'count': row['count'] or 0,
                'absence_type': 'unexcused' if is_unexcused else 'approved_leave',
                'flag_repeated_absence': bool(is_unexcused and repeated_absence_map.get(employee_id, 0) >= 3),
            }
        )

    results: list[dict[str, Any]] = []
    for row in weekly_department_rows:
        week_value = row['week']
        week_date = week_value.date() if hasattr(week_value, 'date') else week_value
        department_name = row['employee__department__name'] or 'Unassigned'

        total_records = row['total'] or 0
        attended_records = row['attended'] or 0
        attendance_pct = round((attended_records / total_records) * 100, 1) if total_records else 0.0

        results.append(
            {
                'week': week_date.isoformat(),
                'department': department_name,
                'attendance_pct': attendance_pct,
                'employees_absent': employees_absent_by_bucket.get((week_date, department_name), []),
                'flag_low_attendance': attendance_pct < 85.0,
                'approved_leave_count': row['approved_leave'] or 0,
                'unexcused_absence_count': row['unexcused_absence'] or 0,
            }
        )

    return results


@agent_tool(
    name='get_leave_patterns',
    description='Get leave pattern observations for the last N weeks (default 8). Returns observations only, not conclusions.',
    schema={
        'type': 'object',
        'properties': {
            'weeks': {'type': 'integer', 'minimum': 1, 'maximum': 12, 'default': 8},
        },
    },
)
def get_leave_patterns(
    user: User,
    weeks: int = 8,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access leave patterns.')

    total_weeks = max(1, min(int(weeks), 12))
    today = timezone.localdate()
    window_start = today - timedelta(weeks=total_weeks)

    queryset = LeaveRequest.objects.select_related('employee', 'employee__department', 'department').filter(
        created_at__date__gte=window_start,
    )

    observations: list[dict[str, Any]] = []

    monday_friday_counts: dict[int, dict[str, Any]] = defaultdict(lambda: {'employee_name': '', 'occurrences': 0})
    for request in queryset.order_by('employee_id', 'created_at', 'id'):
        request_date = request.created_at.date()
        if request_date.weekday() not in (0, 4):
            continue

        employee_name = (
            f'{request.employee.first_name} {request.employee.last_name}'.strip() or request.employee.username
        )
        bucket = monday_friday_counts[request.employee_id]
        bucket['employee_name'] = employee_name
        bucket['occurrences'] += 1

    for bucket in monday_friday_counts.values():
        if bucket['occurrences'] >= 3:
            observations.append(
                {
                    'pattern_type': 'monday_friday_leave_requests',
                    'employee_name': bucket['employee_name'],
                    'description': (
                        f'Observation: {bucket["employee_name"]} submitted leave requests starting on Monday or Friday '
                        f'{bucket["occurrences"]} times in the last {total_weeks} weeks.'
                    ),
                    'occurrences': bucket['occurrences'],
                }
            )

    medical_rows = list(
        queryset.filter(type=LeaveRequest.Type.SICK)
        .values('department_id', 'department__name', 'created_at')
        .order_by('department_id', 'created_at', 'id')
    )
    medical_by_department: dict[str, list[datetime.date]] = defaultdict(list)
    for row in medical_rows:
        department_name = row['department__name'] or 'Unassigned'
        created_at = row['created_at']
        request_date = created_at.date() if hasattr(created_at, 'date') else created_at
        medical_by_department[department_name].append(request_date)

    for department_name, request_dates in medical_by_department.items():
        if len(request_dates) < 3:
            continue

        best_start_index = 0
        best_end_index = 0
        left = 0
        for right, right_date in enumerate(request_dates):
            while request_dates[left] < right_date - timedelta(days=13):
                left += 1
            if right - left > best_end_index - best_start_index:
                best_start_index = left
                best_end_index = right

        occurrences = best_end_index - best_start_index + 1
        if occurrences > 2:
            window_start_date = request_dates[best_start_index]
            window_end_date = request_dates[best_end_index]
            observations.append(
                {
                    'pattern_type': 'medical_leave_cluster',
                    'department': department_name,
                    'description': (
                        f'Observation: {department_name} logged {occurrences} medical leave requests between '
                        f'{window_start_date.isoformat()} and {window_end_date.isoformat()}.'
                    ),
                    'occurrences': occurrences,
                }
            )

    for employee_id, employee_requests in _group_leave_requests_by_employee(queryset).items():
        previous_rejected = False
        consecutive_after_rejection = 0
        employee_name = employee_requests[0]['employee_name'] if employee_requests else ''

        for request in employee_requests:
            if previous_rejected:
                consecutive_after_rejection += 1
                observations.append(
                    {
                        'pattern_type': 'leave_after_rejection',
                        'employee_name': employee_name,
                        'description': (
                            f'Observation: {employee_name} submitted a new leave request after a rejected request on '
                            f'{request["created_at"].date().isoformat()}.'
                        ),
                        'occurrences': consecutive_after_rejection,
                    }
                )
            previous_rejected = request['status'] == LeaveRequest.Status.REJECTED

    observations.sort(
        key=lambda item: (item['pattern_type'], item.get('employee_name') or item.get('department') or '')
    )
    return observations


@agent_tool(
    name='get_headcount_vs_workload',
    description='Compare active headcount with workload per department. Returns observations for Sales, IT and Inventory.',
)
def get_headcount_vs_workload(user: User) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access headcount vs workload.')

    warning_threshold = int(getattr(settings, 'HR_HEADCOUNT_WORKLOAD_WARNING_THRESHOLD', 5))
    critical_threshold = int(getattr(settings, 'HR_HEADCOUNT_WORKLOAD_CRITICAL_THRESHOLD', 10))
    today = timezone.localdate()

    def _status_for_ratio(ratio: float) -> str:
        if ratio >= critical_threshold:
            return 'critical'
        if ratio >= warning_threshold:
            return 'warning'
        return 'ok'

    departments = [
        {
            'department': 'Sales',
            'active_headcount': User.objects.filter(role=User.Role.SALES, is_active=True).count(),
            'workload_items': Order.objects.filter(status=Order.Status.PROCESSING).count(),
        },
        {
            'department': 'IT',
            'active_headcount': User.objects.filter(role=User.Role.IT, is_active=True).count(),
            'workload_items': Ticket.objects.filter(status=Ticket.Status.OPEN).count(),
        },
        {
            'department': 'Inventory',
            'active_headcount': User.objects.filter(role=User.Role.INVENTORY, is_active=True).count(),
            'workload_items': StockMovement.objects.filter(
                movement_type=StockMovement.Type.INBOUND,
                expected_date__gte=today,
            ).count(),
        },
    ]

    results: list[dict[str, Any]] = []
    for row in departments:
        active_headcount = row['active_headcount']
        workload_items = row['workload_items']
        if active_headcount:
            ratio = round(workload_items / active_headcount, 2)
            status = _status_for_ratio(ratio)
        else:
            ratio = float(workload_items)
            status = 'critical' if workload_items > 0 else 'ok'

        results.append(
            {
                'department': row['department'],
                'active_headcount': active_headcount,
                'workload_items': workload_items,
                'ratio': ratio,
                'status': status,
            }
        )

    return results


def _group_leave_requests_by_employee(queryset) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    rows = queryset.values(
        'employee_id',
        'employee__first_name',
        'employee__last_name',
        'employee__username',
        'status',
        'created_at',
        'id',
    ).order_by('employee_id', 'created_at', 'id')

    for row in rows:
        employee_name = (
            f'{row["employee__first_name"]} {row["employee__last_name"]}'.strip() or row['employee__username']
        )
        grouped[row['employee_id']].append(
            {
                'employee_name': employee_name,
                'status': row['status'],
                'created_at': row['created_at'],
            }
        )

    return grouped


@agent_tool(
    name='query_contracts', description='Query employee contracts expiring within a number of days (default 30).'
)
def query_contracts(
    user: User,
    expiring_within_days: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can query contracts.')

    queryset = Contract.objects.select_related('employee', 'department').exclude(end_date__isnull=True)
    today = timezone.localdate()
    days = int(expiring_within_days) if expiring_within_days is not None else 30
    queryset = queryset.filter(end_date__gte=today, end_date__lte=today + timedelta(days=days))

    contracts = queryset.order_by('end_date')[: _normalized_limit(limit)]
    return [
        {
            'id': c.id,
            'contract_number': c.contract_number,
            'employee_id': c.employee_id,
            'employee_username': c.employee.username if c.employee else None,
            'department': _serialize_department(c.department),
            'type': c.type,
            'end_date': c.end_date.isoformat() if c.end_date else None,
            'salary_ron': f'{Decimal(str(c.salary_ron or 0)).quantize(Decimal("0.01")):.2f}',
        }
        for c in contracts
    ]


@agent_tool(
    name='get_expiring_contracts',
    description='Get contracts expiring within a configurable number of days and indicate if the employee has open tickets or pending leave.',
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 60},
        },
    },
)
def get_expiring_contracts(
    user: User,
    days: int = 60,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access expiring contracts.')

    today = timezone.localdate()
    max_days = max(1, min(int(days), 365))
    queryset = (
        Contract.objects.select_related('employee', 'department')
        .exclude(end_date__isnull=True)
        .filter(end_date__gte=today, end_date__lte=today + timedelta(days=max_days))
        .order_by('end_date', 'employee__id')
    )

    result: list[dict[str, Any]] = []
    for contract in queryset:
        employee = contract.employee
        full_name = f'{employee.first_name} {employee.last_name}'.strip() or employee.username

        has_open_tickets = Ticket.objects.filter(assigned_to=employee).exclude(status=Ticket.Status.RESOLVED).exists()

        has_pending_leave = LeaveRequest.objects.filter(employee=employee, status=LeaveRequest.Status.PENDING).exists()

        result.append(
            {
                'employee_name': full_name,
                'role': employee.role,
                'department': contract.department.name if contract.department else None,
                'end_date': contract.end_date.isoformat() if contract.end_date else None,
                'days_remaining': (contract.end_date - today).days if contract.end_date else None,
                'has_open_tickets': has_open_tickets,
                'has_pending_leave': has_pending_leave,
            }
        )

    result.sort(key=lambda x: x['days_remaining'] if x['days_remaining'] is not None else 999)

    return result


@agent_tool(
    name='query_payroll', description='Get payroll summary for a month (format: YYYY-MM, defaults to current month).'
)
def query_payroll(
    user: User,
    month: str | None = None,
) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can query payroll.')

    if month:
        year_str, month_str = month.split('-')
        month_date = datetime.date(int(year_str), int(month_str), 1)
    else:
        today = timezone.localdate()
        month_date = today.replace(day=1)

    next_month = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    entries = PayrollEntry.objects.filter(month__gte=month_date, month__lt=next_month)

    agg = entries.aggregate(
        total_entries=Count('id'),
        total_gross=Sum('gross_salary_ron'),
        total_net=Sum('net_salary_ron'),
        unpaid_count=Count('id', filter=Q(paid=False)),
    )

    return {
        'month': month_date.strftime('%Y-%m'),
        'total_entries': agg['total_entries'] or 0,
        'total_gross_ron': f'{Decimal(str(agg["total_gross"] or 0)).quantize(Decimal("0.01")):.2f}',
        'total_net_ron': f'{Decimal(str(agg["total_net"] or 0)).quantize(Decimal("0.01")):.2f}',
        'unpaid_count': agg['unpaid_count'] or 0,
    }


@agent_tool(
    name='get_payroll_anomalies',
    description='Detect payroll anomalies, including unusual bonus spikes, zero deductions, and missing payroll entries.',
    schema={
        'type': 'object',
        'properties': {
            'month': {'type': 'string', 'description': 'Payroll month in YYYY-MM format; defaults to current month.'},
            'months': {
                'type': 'integer',
                'description': 'Number of historical months to compare against. Defaults to 3.',
                'default': 3,
            },
        },
    },
)
def get_payroll_anomalies(
    user: User,
    month: str | None = None,
    months: int = 3,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access payroll anomalies.')

    if month:
        year_str, month_str = month.split('-')
        month_date = datetime.date(int(year_str), int(month_str), 1)
    else:
        month_date = _month_start(timezone.localdate())

    next_month = _shift_month(month_date, 1)
    history_start = _shift_month(month_date, -months)

    current_entries = PayrollEntry.objects.select_related('employee').filter(
        month__gte=month_date, month__lt=next_month
    )
    historical_entries = PayrollEntry.objects.select_related('employee').filter(
        month__gte=history_start, month__lt=month_date
    )

    historical_diff_by_employee: dict[int, list[Decimal]] = defaultdict(list)
    historical_months_by_employee: dict[int, set[str]] = defaultdict(set)
    for entry in historical_entries:
        diff_component = Decimal(str(entry.gross_salary_ron or 0)) - Decimal(str(entry.net_salary_ron or 0))
        historical_diff_by_employee[entry.employee_id].append(diff_component)
        historical_months_by_employee[entry.employee_id].add(entry.month.strftime('%Y-%m'))

    anomalies: list[dict[str, Any]] = []
    current_employee_ids: set[int] = set()

    prev_month_str = _shift_month(month_date, -1).strftime('%Y-%m')

    for entry in current_entries:
        employee = entry.employee
        current_employee_ids.add(employee.id)
        employee_name = f'{employee.first_name} {employee.last_name}'.strip() or employee.username

        current_diff = Decimal(str(entry.gross_salary_ron or 0)) - Decimal(str(entry.net_salary_ron or 0))
        previous_diffs = historical_diff_by_employee.get(employee.id, [])
        prev_months = historical_months_by_employee.get(employee.id, set())

        # New hire check / missing from previous month
        if prev_month_str not in prev_months:
            anomalies.append(
                {
                    'employee_name': employee_name,
                    'anomaly_type': 'new_hire_or_missing_previous',
                    'current_value': 'Present',
                    'expected_range': 'Present in previous month',
                    'severity': 'INFO',
                }
            )

        if not previous_diffs:
            continue

        avg_diff = sum(previous_diffs, Decimal('0.00')) / Decimal(len(previous_diffs))

        # Bonus spike
        if avg_diff > 0 and current_diff > (avg_diff * Decimal('2.00')):
            anomalies.append(
                {
                    'employee_name': employee_name,
                    'anomaly_type': 'bonus_spike',
                    'current_value': f'{current_diff:.2f} RON',
                    'expected_range': f'<= {(avg_diff * Decimal("2.00")):.2f} RON',
                    'severity': 'WARNING',
                }
            )

        # Deductions = 0 when non-zero previously
        if current_diff == 0 and all(d > 0 for d in previous_diffs):
            anomalies.append(
                {
                    'employee_name': employee_name,
                    'anomaly_type': 'zero_deductions',
                    'current_value': '0.00 RON',
                    'expected_range': '> 0.00 RON',
                    'severity': 'CRITICAL',
                }
            )

    active_employee_ids = set(User.objects.filter(is_active=True).values_list('id', flat=True))
    missing_employee_ids = sorted(active_employee_ids - current_employee_ids)
    for employee_id in missing_employee_ids:
        employee = User.objects.get(id=employee_id)
        employee_name = f'{employee.first_name} {employee.last_name}'.strip() or employee.username
        anomalies.append(
            {
                'employee_name': employee_name,
                'anomaly_type': 'missing_payroll_entry',
                'current_value': 'Missing',
                'expected_range': 'Present',
                'severity': 'CRITICAL',
            }
        )

    return anomalies


# ---------------------------------------------------------------------------
# Sales module — customers & invoices
# ---------------------------------------------------------------------------


@agent_tool(name='query_customers', description='Query sales customers, optionally filtered by tier or name.')
def query_customers(
    user: User,
    tier: str | None = None,
    name: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can query customers.')

    queryset = Customer.objects.all()

    if tier:
        tier_input = tier.strip()
        valid_tiers = {choice[0] for choice in Customer.Tier.choices}
        matched = next((t for t in valid_tiers if t.lower() == tier_input.lower()), None)
        if matched is None:
            raise ValueError(f'Unsupported customer tier: {tier}')
        queryset = queryset.filter(tier=matched)

    if name:
        queryset = queryset.filter(name__icontains=name)

    customers = queryset.order_by('name')[: _normalized_limit(limit)]
    return [_serialize_customer(customer) for customer in customers]


@agent_tool(
    name='query_invoices',
    description='Query invoices by status or customer. Set overdue=true to list issued invoices past their due date.',
)
def query_invoices(
    user: User,
    status: str | None = None,
    customer: str | None = None,
    overdue: bool | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can query invoices.')

    queryset = Invoice.objects.select_related('order', 'order__customer').all()

    if status:
        status_name = status.strip().upper()
        valid_statuses = {choice[0] for choice in Invoice.Status.choices}
        if status_name not in valid_statuses:
            raise ValueError(f'Unsupported invoice status: {status}')
        queryset = queryset.filter(status=status_name)

    if customer:
        queryset = queryset.filter(order__customer__name__icontains=customer)

    if overdue is True:
        queryset = queryset.filter(
            status=Invoice.Status.ISSUED,
            due_date__isnull=False,
            due_date__lt=timezone.localdate(),
        )

    invoices = queryset.order_by('-issued_date', '-id')[: _normalized_limit(limit)]
    return [_serialize_invoice(invoice) for invoice in invoices]


@agent_tool(
    name='update_order_status',
    description='Update the status of an order identified by its order number.',
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string', 'description': 'Order number, e.g. ORD-00012'},
            'status': {'type': 'string', 'enum': ['PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED']},
        },
        'required': ['order_number', 'status'],
    },
)
def update_order_status(user: User, order_number: str, status: str) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can update orders.')

    order = Order.objects.select_related('customer').get(order_number=order_number)
    sales_services.change_order_status(order, (status or '').strip().upper())
    return {'order_number': order.order_number, 'status': order.status}


@agent_tool(
    name='mark_invoice_paid',
    description='Mark an invoice as paid, identified by its invoice number.',
    schema={
        'type': 'object',
        'properties': {
            'invoice_number': {'type': 'string', 'description': 'Invoice number, e.g. INV-00012'},
        },
        'required': ['invoice_number'],
    },
)
def mark_invoice_paid(user: User, invoice_number: str) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can update invoices.')

    invoice = Invoice.objects.get(invoice_number=invoice_number)
    sales_services.mark_invoice_paid(invoice)
    return {'invoice_number': invoice.invoice_number, 'status': invoice.status}


# ---------------------------------------------------------------------------
# Inventory module — suppliers, stock movements
# ---------------------------------------------------------------------------


@agent_tool(name='query_suppliers', description='Query inventory suppliers, optionally filtered by name.')
def query_suppliers(
    user: User,
    name: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.INVENTORY], 'Only CEO and Inventory can query suppliers.')

    queryset = Supplier.objects.all()
    if name:
        queryset = queryset.filter(name__icontains=name)

    suppliers = queryset.order_by('name')[: _normalized_limit(limit)]
    return [_serialize_supplier(supplier) for supplier in suppliers]


@agent_tool(
    name='query_stock_movements',
    description='Query recent stock movements, optionally filtered by movement type or product SKU.',
)
def query_stock_movements(
    user: User,
    movement_type: str | None = None,
    sku: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.INVENTORY], 'Only CEO and Inventory can query stock movements.')

    queryset = StockMovement.objects.select_related('product', 'supplier').all()

    if movement_type:
        type_name = movement_type.strip().upper()
        valid_types = {choice[0] for choice in StockMovement.Type.choices}
        if type_name not in valid_types:
            raise ValueError(f'Unsupported movement type: {movement_type}')
        queryset = queryset.filter(movement_type=type_name)

    if sku:
        queryset = queryset.filter(product__sku__iexact=sku.strip())

    movements = queryset.order_by('-created_at')[: _normalized_limit(limit)]
    return [_serialize_stock_movement(movement) for movement in movements]


@agent_tool(
    name='adjust_stock',
    description=(
        'Record a stock movement for a product (identified by SKU). The product stock is updated automatically. '
        'For ADJUSTMENT, quantity is the new absolute stock count; for INBOUND/OUTBOUND/WRITE_OFF it is the delta.'
    ),
    schema={
        'type': 'object',
        'properties': {
            'sku': {'type': 'string', 'description': 'Product SKU'},
            'movement_type': {'type': 'string', 'enum': ['INBOUND', 'OUTBOUND', 'ADJUSTMENT', 'WRITE_OFF']},
            'quantity': {'type': 'integer', 'minimum': 0},
            'supplier': {'type': 'string', 'description': 'Supplier name (optional, mainly for inbound)'},
            'notes': {'type': 'string', 'description': 'Optional notes'},
        },
        'required': ['sku', 'movement_type', 'quantity'],
    },
)
def adjust_stock(
    user: User,
    sku: str,
    movement_type: str,
    quantity: int,
    supplier: str | None = None,
    notes: str = '',
) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.INVENTORY], 'Only CEO and Inventory can adjust stock.')

    type_name = (movement_type or '').strip().upper()
    valid_types = {choice[0] for choice in StockMovement.Type.choices}
    if type_name not in valid_types:
        raise ValueError(f'Unsupported movement type: {movement_type}')

    product = Product.objects.get(sku=sku.strip())

    supplier_obj = None
    if supplier:
        supplier_obj = Supplier.objects.filter(name__iexact=supplier.strip()).first()
        if supplier_obj is None:
            raise ValueError(f'Unknown supplier: {supplier}')

    movement = StockMovement.objects.create(
        movement_type=type_name,
        product=product,
        supplier=supplier_obj,
        quantity=max(0, int(quantity)),
        notes=notes,
        created_by=user,
    )
    product.refresh_from_db(fields=['stock_count'])
    return {
        'movement_id': movement.id,
        'sku': product.sku,
        'movement_type': movement.movement_type,
        'new_stock_count': product.stock_count,
    }


# ---------------------------------------------------------------------------
# IT module — assets, system status, ticket actions
# ---------------------------------------------------------------------------


@agent_tool(name='query_assets', description='Query IT assets, optionally filtered by status, category, or assignee.')
def query_assets(
    user: User,
    status: str | None = None,
    category: str | None = None,
    assigned_to: int | str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can query assets.')

    queryset = Asset.objects.select_related('assigned_to').all()

    if status:
        status_name = status.strip().upper()
        valid_statuses = {choice[0] for choice in Asset.Status.choices}
        if status_name not in valid_statuses:
            raise ValueError(f'Unsupported asset status: {status}')
        queryset = queryset.filter(status=status_name)

    if category:
        category_name = category.strip().upper()
        valid_categories = {choice[0] for choice in Asset.Category.choices}
        if category_name not in valid_categories:
            raise ValueError(f'Unsupported asset category: {category}')
        queryset = queryset.filter(category=category_name)

    if assigned_to is not None:
        if isinstance(assigned_to, int) or (isinstance(assigned_to, str) and assigned_to.isdigit()):
            queryset = queryset.filter(assigned_to_id=int(assigned_to))
        elif isinstance(assigned_to, str):
            queryset = queryset.filter(assigned_to__username=assigned_to)
        else:
            raise ValueError('assigned_to must be a user id or username')

    assets = queryset.order_by('-created_at')[: _normalized_limit(limit)]
    return [_serialize_asset(asset) for asset in assets]


@agent_tool(name='query_system_status', description='List monitored systems with their current status and uptime.')
def query_system_status(user: User, limit: int = 10) -> list[dict[str, Any]]:
    _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can view system status.')

    rows = SystemStatus.objects.order_by('name')[: _normalized_limit(limit)]
    return [_serialize_system_status(row) for row in rows]


@agent_tool(
    name='update_ticket_status',
    description='Update a ticket status (and optionally reassign it). Setting status to RESOLVED stamps the resolution time.',
    schema={
        'type': 'object',
        'properties': {
            'ticket_number': {'type': 'string', 'description': 'Ticket number, e.g. TKT-00012'},
            'status': {'type': 'string', 'enum': ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED']},
            'assigned_to': {'type': 'string', 'description': 'Optional user id or username to assign the ticket to'},
        },
        'required': ['ticket_number', 'status'],
    },
)
def update_ticket_status(
    user: User,
    ticket_number: str,
    status: str,
    assigned_to: int | str | None = None,
) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can update tickets.')

    ticket = Ticket.objects.get(ticket_number=ticket_number)

    assignee = None
    if assigned_to is not None:
        if isinstance(assigned_to, int) or (isinstance(assigned_to, str) and assigned_to.isdigit()):
            assignee = User.objects.get(id=int(assigned_to))
        elif isinstance(assigned_to, str):
            assignee = User.objects.get(username=assigned_to)
        else:
            raise ValueError('assigned_to must be a user id or username')

    it_services.change_ticket_status(ticket, (status or '').strip().upper(), actor=user, assigned_to=assignee)
    return {
        'ticket_number': ticket.ticket_number,
        'status': ticket.status,
        'assigned_to_username': ticket.assigned_to.username if ticket.assigned_to else None,
        'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }


@agent_tool(
    name='add_ticket_comment',
    description='Add a comment to a ticket identified by its ticket number.',
    schema={
        'type': 'object',
        'properties': {
            'ticket_number': {'type': 'string', 'description': 'Ticket number, e.g. TKT-00012'},
            'body': {'type': 'string', 'description': 'Comment text'},
        },
        'required': ['ticket_number', 'body'],
    },
)
def add_ticket_comment(user: User, ticket_number: str, body: str) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.IT], 'Only CEO and IT can comment on tickets.')

    if not (body or '').strip():
        raise ValueError('Comment body cannot be empty.')

    ticket = Ticket.objects.get(ticket_number=ticket_number)
    comment = TicketComment.objects.create(ticket=ticket, author=user, body=body)
    return {'comment_id': comment.id, 'ticket_number': ticket.ticket_number}


# ---------------------------------------------------------------------------
# HR module — leave request decisions
# ---------------------------------------------------------------------------


@agent_tool(
    name='decide_leave_request',
    description='Approve or reject a pending leave request, identified by its id.',
    schema={
        'type': 'object',
        'properties': {
            'leave_request_id': {'type': 'integer', 'description': 'Leave request id'},
            'decision': {'type': 'string', 'enum': ['approve', 'reject']},
        },
        'required': ['leave_request_id', 'decision'],
    },
)
def decide_leave_request(user: User, leave_request_id: int, decision: str) -> dict[str, Any]:
    _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can decide leave requests.')

    decision_name = (decision or '').strip().lower()
    if decision_name not in ('approve', 'reject'):
        raise ValueError("decision must be 'approve' or 'reject'.")

    leave_request = LeaveRequest.objects.select_related('employee').get(id=int(leave_request_id))
    hr_services.decide_leave_request(leave_request, approve=decision_name == 'approve', actor=user)
    return {
        'id': leave_request.id,
        'status': leave_request.status,
        'employee_username': leave_request.employee.username if leave_request.employee else None,
    }


# ---------------------------------------------------------------------------
# Cross-cutting — notifications (scoped to the requesting user)
# ---------------------------------------------------------------------------


@agent_tool(
    name='query_notifications',
    description='List notifications for the current user. Set unread_only=true to return only unread ones.',
)
def query_notifications(
    user: User,
    unread_only: bool | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    queryset = Notification.objects.filter(recipient=user)
    if unread_only is True:
        queryset = queryset.filter(is_read=False)

    notifications = queryset.order_by('-created_at')[: _normalized_limit(limit)]
    return [_serialize_notification(notification) for notification in notifications]


@agent_tool(
    name='mark_notification_read',
    description="Mark one of the current user's notifications as read, identified by its id.",
    schema={
        'type': 'object',
        'properties': {
            'notification_id': {'type': 'integer', 'description': 'Notification id'},
        },
        'required': ['notification_id'],
    },
)
def mark_notification_read(user: User, notification_id: int) -> dict[str, Any]:
    notification = Notification.objects.get(id=int(notification_id), recipient=user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return {'id': notification.id, 'is_read': notification.is_read}


def register_default_tools() -> None:
    registry = get_registry()
    if registry.get('get_dashboard_summary') is not None:
        return

    register_tool(Tool.from_callable(get_dashboard_summary))
    register_tool(Tool.from_callable(query_orders, required_permission='view_sales_reports'))
    register_tool(Tool.from_callable(query_tickets, required_permission='manage_tickets'))
    register_tool(Tool.from_callable(query_employees, required_permission='manage_employees'))
    register_tool(Tool.from_callable(query_inventory, required_permission='manage_stock'))
    register_tool(Tool.from_callable(create_ticket))
    register_tool(Tool.from_callable(create_leave_request, required_permission='process_leave_requests'))
    register_tool(Tool.from_callable(generate_report, required_permission='view_financial_reports'))
    register_tool(Tool.from_callable(query_leave_requests, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(query_attendance, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(get_leave_patterns, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(get_headcount_vs_workload, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(get_attendance_trend, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(get_expiring_contracts, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(get_payroll_anomalies, required_permission='view_hr_dashboard'))
    register_tool(Tool.from_callable(query_contracts, required_permission='manage_employees'))
    register_tool(Tool.from_callable(query_payroll, required_permission='view_payroll'))

    # Sales module
    register_tool(Tool.from_callable(query_customers, required_permission='manage_customers'))
    register_tool(Tool.from_callable(query_invoices, required_permission='manage_invoices'))
    register_tool(Tool.from_callable(update_order_status, required_permission='manage_orders'))
    register_tool(Tool.from_callable(mark_invoice_paid, required_permission='manage_invoices'))

    # Inventory module
    register_tool(Tool.from_callable(query_suppliers, required_permission='manage_suppliers'))
    register_tool(Tool.from_callable(query_stock_movements, required_permission='view_stock_movements'))
    register_tool(Tool.from_callable(adjust_stock, required_permission='manage_stock'))

    # IT module
    register_tool(Tool.from_callable(query_assets, required_permission='view_it_dashboard'))
    register_tool(Tool.from_callable(query_system_status, required_permission='view_system_status'))
    register_tool(Tool.from_callable(update_ticket_status, required_permission='manage_tickets'))
    register_tool(Tool.from_callable(add_ticket_comment, required_permission='manage_tickets'))

    # HR module
    register_tool(Tool.from_callable(decide_leave_request, required_permission='process_leave_requests'))

    # Cross-cutting — available to every role (scoped to the requesting user)
    register_tool(Tool.from_callable(query_notifications))
    register_tool(Tool.from_callable(mark_notification_read))
