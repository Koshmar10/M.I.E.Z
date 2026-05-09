"""Business tools exposed to the MIEZ Assistant agent."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from api.models import Department, LeaveRequest, Order, Product, Report, Ticket, User
from api.report_utils import generate_report_file

from .tools import Tool, agent_tool, get_registry, register_tool


def _permission_error(message: str) -> PermissionError:
    return PermissionError(message)


def _require_roles(user: User, allowed_roles: list[str], message: str) -> None:
    if user.role not in allowed_roles:
        raise _permission_error(message)


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


def _normalized_limit(limit: int | None, default_limit: int = 10) -> int:
    if limit is None:
        return default_limit
    return max(1, min(int(limit), 10))


@agent_tool(name='get_dashboard_summary', description='Get dashboard summary data by module.')
def get_dashboard_summary(module: str, user: User) -> dict[str, Any]:
    module_name = (module or '').strip().lower()
    if module_name == 'sales':
        _require_roles(user, [User.Role.CEO, User.Role.SALES], 'Only CEO and Sales can access the sales dashboard summary.')

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())

        base_queryset = Order.objects.all()
        today_stats = base_queryset.filter(date=today).aggregate(
            orders_today=Count('id'),
            revenue_today_ron=Sum('value_ron'),
        )
        yesterday_stats = base_queryset.filter(date=yesterday).aggregate(
            orders_yesterday=Count('id'),
            revenue_yesterday_ron=Sum('value_ron'),
        )

        def pct_change(current_value: Any, previous_value: Any) -> float:
            current_numeric = float(current_value or 0)
            previous_numeric = float(previous_value or 0)
            if previous_numeric == 0:
                return 100.0 if current_numeric > 0 else 0.0
            return round(((current_numeric - previous_numeric) / previous_numeric) * 100, 2)

        orders_today = today_stats['orders_today'] or 0
        revenue_today_ron = Decimal(str(today_stats['revenue_today_ron'] or 0)).quantize(Decimal('0.01'))
        orders_yesterday = yesterday_stats['orders_yesterday'] or 0
        revenue_yesterday_ron = yesterday_stats['revenue_yesterday_ron'] or 0

        return {
            'orders_today': orders_today,
            'revenue_today_ron': f'{revenue_today_ron:.2f}',
            'pending_orders': base_queryset.filter(status=Order.Status.PENDING).count(),
            'returns_this_week': base_queryset.filter(
                status=Order.Status.RETURNED,
                date__gte=start_of_week,
                date__lte=today,
            ).count(),
            'pct_changes': {
                'orders': pct_change(orders_today, orders_yesterday),
                'revenue': pct_change(revenue_today_ron, revenue_yesterday_ron),
            },
        }

    if module_name == 'hr':
        _require_roles(user, [User.Role.CEO, User.Role.HR], 'Only CEO and HR can access the HR dashboard summary.')

        today = timezone.localdate()
        month_start = today.replace(day=1)
        employees = User.objects.all()
        total_employees = employees.count()
        active_employees = employees.filter(is_active=True).count()
        full_time_employees = employees.filter(full_time=True).count()

        return {
            'total_employees': total_employees,
            'new_hires_this_month': employees.filter(start_date__gte=month_start, start_date__lte=today).count(),
            'leave_requests_this_month': LeaveRequest.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=today,
            ).count(),
            'pending_leave_requests': LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
            'full_time_employees': full_time_employees,
            'non_full_time_employees': max(total_employees - full_time_employees, 0),
            'retention_rate': round((active_employees / total_employees) * 100, 1) if total_employees else 0.0,
            'active_employees': active_employees,
        }

    raise ValueError(f'Unsupported module: {module}')


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

    tickets = queryset.order_by('-created_at')[:_normalized_limit(limit)]
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

    employees = employees.order_by('id')[:_normalized_limit(limit)]
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

    orders = queryset.order_by('-date', '-id')[:_normalized_limit(limit)]
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
        category_name = category.strip().upper()
        valid_categories = {choice[0] for choice in Product.Category.choices}
        if category_name not in valid_categories:
            raise ValueError(f'Unsupported product category: {category}')
        queryset = queryset.filter(category=category_name)

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
        return [_serialize_inventory(product) for product in products[:_normalized_limit(limit)]]

    return [_serialize_inventory(product) for product in products[:_normalized_limit(limit)]]


@agent_tool(name='create_ticket', description='Create a support ticket.')
def create_ticket(user: User, **payload: Any) -> Ticket:
    return Ticket.objects.create(
        title=payload['title'],
        description=payload.get('description', ''),
        category=payload.get('category', ''),
        priority=payload.get('priority', Ticket.Priority.MEDIUM),
        department_id=payload.get('department_id'),
        requested_for_id=payload.get('requested_for_id'),
        assigned_to_id=payload.get('assigned_to_id'),
        location=payload.get('location', ''),
        requested_by=user,
        status=Ticket.Status.OPEN,
    )


@agent_tool(name='create_leave_request', description='Create a leave request.')
def create_leave_request(user: User, **payload: Any) -> LeaveRequest:
    _require_roles(user, [User.Role.HR], 'Only HR can create leave requests through the assistant.')

    employee = payload['employee']
    if isinstance(employee, int):
        employee = User.objects.select_related('department').get(id=employee)

    return LeaveRequest.objects.create(
        employee=employee,
        department=employee.department,
        type=payload.get('type', LeaveRequest.Type.VACATION),
        from_date=payload['from_date'],
        to_date=payload['to_date'],
        reason=payload.get('reason', ''),
        status=LeaveRequest.Status.PENDING,
    )


@agent_tool(name='generate_report', description='Generate a report from an existing report definition.')
def generate_report(user: User, slug: str) -> Report:
    if user.role != User.Role.CEO and not user.is_staff:
        raise _permission_error('Only CEO or staff users can generate reports through the assistant.')

    report = Report.objects.get(slug=slug)
    generate_report_file(report, user=user)
    return report


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