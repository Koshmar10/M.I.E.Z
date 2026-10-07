from collections import OrderedDict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.core.cache import cache
from django.db.models import (
    Avg,
    Case,
    Count,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .agent import AgentRunner, get_registry
from .management.commands.generate_hr_digest import DigestGenerator
from .models import (
    Asset,
    Attendance,
    Contract,
    ConversationMessage,
    ConversationSession,
    Customer,
    Department,
    Invoice,
    LeaveRequest,
    Notification,
    Order,
    OrderItem,
    PayrollEntry,
    Product,
    Report,
    StockMovement,
    Supplier,
    SystemStatus,
    Ticket,
    User,
    Workflow,
    WorkflowLog,
)
from .notifications import notify_role
from .serializers import (
    AssetSerializer,
    AssistantChatRequestSerializer,
    AssistantChatResponseSerializer,
    ConversationSessionListSerializer,
    ConversationSessionSerializer,
    CustomerDetailSerializer,
    CustomerSalesSummarySerializer,
    DepartmentSerializer,
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeUpdateSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    NotificationSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    ProductSerializer,
    ReportSerializer,
    SalesProductSerializer,
    StockMovementSerializer,
    SupplierSerializer,
    SystemStatusSerializer,
    TicketCreateSerializer,
    TicketSerializer,
    TicketUpdateSerializer,
    WorkflowLogSerializer,
    WorkflowSerializer,
    WorkflowWriteSerializer,
)

IT_SLA_THRESHOLD_HOURS = 48


# Which roles may read reports of a given category. CEO always sees everything;
# reports with a blank/unknown category are CEO-only.
REPORT_CATEGORY_ROLES = {
    Report.Category.SALES: {User.Role.CEO, User.Role.SALES},
    Report.Category.FINANCE: {User.Role.CEO},
    Report.Category.INVENTORY: {User.Role.CEO, User.Role.INVENTORY},
    Report.Category.HR: {User.Role.CEO, User.Role.HR},
    Report.Category.IT: {User.Role.CEO, User.Role.IT},
}


def _allowed_report_categories(user):
    """Return the set of report categories the user is permitted to read."""
    if user.role == User.Role.CEO:
        return set(Report.Category.values)
    return {category for category, roles in REPORT_CATEGORY_ROLES.items() if user.role in roles}


def _can_access_report(user, report):
    if user.role == User.Role.CEO:
        return True
    return user.role in REPORT_CATEGORY_ROLES.get(report.category, set())


# Create your views here.
@require_GET
def is_even(request):
    try:
        number = int(request.GET.get('number'))
        result = number % 2 == 0
        return JsonResponse({'even': result})
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid or missing number parameter'}, status=400)


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            acces_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                value=acces_token,
                httponly=True,
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite='Lax',
                path='/',
            )
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
                value=refresh_token,
                httponly=True,
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite='Lax',
                path='/api/auth/refresh/',
            )
        return response


class RefreshTokenView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        if refresh:
            request.data['refresh'] = refresh

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get('access')
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                value=access_token,
                httponly=True,
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite='Lax',
                path='/',
            )
            response.data = {'detail': 'Refresh success'}
        return response


from rest_framework_simplejwt.tokens import RefreshToken


class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass

        response = Response({'detail': 'Logout successful'}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
        response.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        return response


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'role': request.user.role,
                'message': 'Authenticated',
            }
        )

    def patch(self, request):
        user = request.user
        data = request.data
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone' in data:
            user.phone = data['phone']
        if 'address' in data:
            user.address = data['address']

        user.save(update_fields=['first_name', 'last_name', 'phone', 'address'])
        return JsonResponse(
            {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'address': user.address,
                'detail': 'Profile updated successfully.',
            }
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'detail': 'Both current and new passwords are required.'}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return Response({'detail': 'Incorrect current password.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)  # Keeps the user logged in
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class DepartmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view departments.'}, status=status.HTTP_403_FORBIDDEN)

        departments = Department.objects.all()
        serializer = DepartmentSerializer(departments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEOs can create departments.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InventoryFlowView(APIView):
    """Return nodes and links for a Sankey flow diagram of stock movements."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        movements = list(StockMovement.objects.select_related('product', 'supplier').order_by('-created_at')[:100])

        if movements:
            start_date = min(m.created_at for m in movements)
            end_date = max(m.created_at for m in movements)
        else:
            days = int(request.query_params.get('days', 7))
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

        nodes = []
        node_map = {}

        def get_node(type_, name_):
            key = (type_, name_)
            if key not in node_map:
                node_map[key] = len(nodes)
                nodes.append({'name': name_, 'type': type_})
            return node_map[key]

        wh_idx = get_node('warehouse', 'Main Warehouse')

        from collections import defaultdict

        inbound_agg = defaultdict(int)
        outbound_agg = defaultdict(int)

        for m in movements:
            val = int(m.quantity or 0)
            if val <= 0:
                continue

            prod = m.product.name if m.product else 'Unknown Product'

            if m.movement_type == StockMovement.Type.INBOUND:
                sup = m.supplier.name if m.supplier else 'Unknown Supplier'
                inbound_agg[(sup, prod)] += val
            elif m.movement_type == StockMovement.Type.OUTBOUND:
                outbound_agg[(prod, 'Sales Orders')] += val
            elif m.movement_type == StockMovement.Type.ADJUSTMENT:
                outbound_agg[(prod, 'Adjustments')] += val
            elif m.movement_type == StockMovement.Type.WRITE_OFF:
                outbound_agg[(prod, 'Returns')] += val

        links = []
        for (sup, prod), val in inbound_agg.items():
            s_idx = get_node('supplier', sup)
            p_idx = get_node('product', prod)
            links.append(
                {'source': s_idx, 'target': p_idx, 'value': val, 'items': f'{prod} × {val}', 'product_name': prod}
            )
            links.append({'source': p_idx, 'target': wh_idx, 'value': val, 'items': 'Processing...'})

        for (prod, dest), val in outbound_agg.items():
            d_idx = get_node('out', dest)
            links.append(
                {'source': wh_idx, 'target': d_idx, 'value': val, 'items': f'{prod} × {val}', 'product_name': prod}
            )

        return Response(
            {
                'nodes': nodes,
                'links': links,
                'date_range': {'start': start_date.date().isoformat(), 'end': end_date.date().isoformat()},
            },
            status=status.HTTP_200_OK,
        )


class DepartmentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEOs can remove departments.'}, status=status.HTTP_403_FORBIDDEN)

        department = get_object_or_404(Department, id=id)
        department.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmployeeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR, User.Role.IT]:
            return Response({'detail': 'Only CEO, HR, and IT can view employees.'}, status=status.HTTP_403_FORBIDDEN)

        queryset = User.objects.select_related('department').all().order_by('id')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(username__icontains=search)
            )

        department_filter = request.query_params.get('department')
        if department_filter:
            if department_filter.isdigit():
                queryset = queryset.filter(department_id=int(department_filter))
            else:
                queryset = queryset.filter(department__slug=department_filter)

        is_active_filter = request.query_params.get('is_active')
        if is_active_filter is not None:
            normalized = is_active_filter.strip().lower()
            if normalized in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
            elif normalized in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)

        paginator = EmployeePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = EmployeeListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can create employees.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        response_serializer = EmployeeListSerializer(employee)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AssetListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response({'detail': 'Only IT and CEO can view assets.'}, status=status.HTTP_403_FORBIDDEN)

        assets = Asset.objects.select_related('assigned_to').all().order_by('-created_at')
        serializer = AssetSerializer(assets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response({'detail': 'Only IT and CEO can create assets.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AssetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = serializer.save()
        return Response(AssetSerializer(asset).data, status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response({'detail': 'Only IT and CEO can view assets.'}, status=status.HTTP_403_FORBIDDEN)

        asset = get_object_or_404(Asset.objects.select_related('assigned_to'), id=id)
        serializer = AssetSerializer(asset)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response({'detail': 'Only IT and CEO can update assets.'}, status=status.HTTP_403_FORBIDDEN)

        asset = get_object_or_404(Asset.objects.select_related('assigned_to'), id=id)
        serializer = AssetSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AssetSerializer(asset).data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response({'detail': 'Only IT and CEO can delete assets.'}, status=status.HTTP_403_FORBIDDEN)

        asset = get_object_or_404(Asset, id=id)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view employee details.'}, status=status.HTTP_403_FORBIDDEN)

        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeListSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response(
                {'detail': 'Only CEO and HR can update employee details.'}, status=status.HTTP_403_FORBIDDEN
            )

        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeUpdateSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmployeeListSerializer(employee).data, status=status.HTTP_200_OK)


class EmployeeStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view employee stats.'}, status=status.HTTP_403_FORBIDDEN)

        base = User.objects.select_related('department').all()

        stats = base.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            full_time=Count('id', filter=Q(full_time=True)),
        )

        department_rows = base.values('department__name').annotate(count=Count('id')).order_by('department__name')

        departments = []
        for row in department_rows:
            departments.append(
                {
                    'name': row['department__name'] or 'Unassigned',
                    'count': row['count'],
                }
            )

        return Response(
            {
                'total': stats['total'],
                'active': stats['active'],
                'full_time': stats['full_time'],
                'departments': departments,
            },
            status=status.HTTP_200_OK,
        )


class HrDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view HR dashboard KPIs.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        month_start = today.replace(day=1)

        employees = User.objects.all()
        total_employees = employees.count()
        active_employees = employees.filter(is_active=True).count()
        full_time_employees = employees.filter(full_time=True).count()

        new_hires_this_month = employees.filter(start_date__gte=month_start, start_date__lte=today).count()

        leave_requests_this_month = LeaveRequest.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=today,
        ).count()
        pending_leave_requests = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count()

        non_full_time = max(total_employees - full_time_employees, 0)
        retention_rate = round((active_employees / total_employees) * 100, 1) if total_employees else 0.0

        return Response(
            {
                'total_employees': total_employees,
                'new_hires_this_month': new_hires_this_month,
                'leave_requests_this_month': leave_requests_this_month,
                'pending_leave_requests': pending_leave_requests,
                'full_time_employees': full_time_employees,
                'non_full_time_employees': non_full_time,
                'retention_rate': retention_rate,
                'active_employees': active_employees,
                'latest_digest': (
                    lambda: (
                        lambda r: (
                            {
                                'report_id': r.id,
                                'summary': (r.digest_data.get('summary_line') if r.digest_data else None),
                            }
                            if r
                            else None
                        )
                    )(Report.objects.filter(category=Report.Category.HR).order_by('-generated_at').first())
                )(),
            },
            status=status.HTTP_200_OK,
        )


class CeoHrSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _department_matches_role(department, role_keyword):
        slug = (getattr(department, 'slug', '') or '').strip().lower()
        name = (getattr(department, 'name', '') or '').strip().lower()
        keyword = role_keyword.lower().strip()
        return keyword in slug or keyword in name

    def get(self, request):
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEO can view HR summary.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()

        current_leaves = LeaveRequest.objects.filter(
            status=LeaveRequest.Status.APPROVED,
            from_date__lte=today,
            to_date__gte=today,
        )

        leave_by_department = {
            row['department_id']: row['count']
            for row in (current_leaves.values('department_id').annotate(count=Count('id')))
        }

        department_headcount = []
        departments = Department.objects.order_by('name')
        for department in departments:
            mapped_role = None
            if self._department_matches_role(department, 'it'):
                mapped_role = User.Role.IT
            elif self._department_matches_role(department, 'sales'):
                mapped_role = User.Role.SALES
            elif self._department_matches_role(department, 'hr'):
                mapped_role = User.Role.HR
            elif self._department_matches_role(department, 'inventory'):
                mapped_role = User.Role.INVENTORY

            users_qs = User.objects.filter(department=department)
            leaves_qs = current_leaves.filter(department=department)

            if mapped_role is not None:
                users_qs = User.objects.filter(
                    Q(department=department) | (Q(department__isnull=True) & Q(role=mapped_role))
                )
                leaves_qs = current_leaves.filter(
                    Q(department=department) | (Q(department__isnull=True) & Q(employee__role=mapped_role))
                )

            total = users_qs.count()
            on_leave = leaves_qs.count()
            active = users_qs.filter(is_active=True).count()
            active_now = max(active - on_leave, 0)
            utilisation_pct = round((active_now / total) * 100, 1) if total else 0.0

            department_headcount.append(
                {
                    'department': department.name,
                    'total': total,
                    'active': active_now,
                    'on_leave': on_leave,
                    'utilisation_pct': utilisation_pct,
                }
            )

        six_weeks_ago = today - timedelta(weeks=5)
        week_start = six_weeks_ago - timedelta(days=six_weeks_ago.weekday())

        attendance_rows = (
            Attendance.objects.filter(date__gte=week_start, date__lte=today)
            .annotate(week=TruncWeek('date'))
            .values('week')
            .annotate(
                total=Count('id'),
                attended=Count('id', filter=Q(status__in=[Attendance.Status.PRESENT, Attendance.Status.REMOTE])),
            )
            .order_by('week')
        )

        attendance_by_week = {}
        for row in attendance_rows:
            week_value = row['week']
            week_date = week_value.date() if hasattr(week_value, 'date') else week_value
            key = week_date.isoformat()

            total_count = row['total'] or 0
            attended_count = row['attended'] or 0
            rate = round((attended_count / total_count) * 100, 1) if total_count else 0.0

            attendance_by_week[key] = rate

        attendance_rate_weeks = []
        for index in range(6):
            current_week = week_start + timedelta(weeks=index)
            week_key = current_week.isoformat()
            attendance_rate_weeks.append(
                {
                    'week_start': week_key,
                    'attendance_rate': attendance_by_week.get(week_key, 0.0),
                }
            )

        return Response(
            {
                'department_headcount': department_headcount,
                'attendance_rate_weeks': attendance_rate_weeks,
                'latest_digest': self._latest_digest_summary(),
            },
            status=status.HTTP_200_OK,
        )

    def _latest_digest_summary(self):
        try:
            report = Report.objects.filter(category=Report.Category.HR).order_by('-generated_at').first()
            if not report or not report.digest_data:
                return None
            summary = (
                report.digest_data.get('summary_line')
                or report.digest_data.get('summary')
                or report.digest_data.get('period')
            )
            return {'report_id': report.id, 'summary': summary}
        except Exception:
            return None


class HrUpcomingEventsView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _month_end(value_date):
        next_month = (value_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        return next_month - timedelta(days=1)

    @staticmethod
    def _days_until(today, target_date):
        return (target_date - today).days

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view upcoming events.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        horizon_days = max(7, min(int(request.query_params.get('days', 30) or 30), 90))
        cutoff = today + timedelta(days=horizon_days)

        events = []

        upcoming_contracts = (
            Contract.objects.select_related('employee', 'department')
            .filter(end_date__isnull=False, end_date__gte=today, end_date__lte=cutoff)
            .order_by('end_date', 'employee__first_name', 'employee__last_name', 'id')
        )
        for contract in upcoming_contracts:
            event_date = contract.end_date
            days_until = self._days_until(today, event_date)
            employee_name = (
                f'{contract.employee.first_name} {contract.employee.last_name}'.strip() or contract.employee.username
            )
            events.append(
                {
                    'id': f'contract-{contract.id}',
                    'type': 'CONTRACT_EXPIRY',
                    'date': event_date.isoformat(),
                    'days_until': days_until,
                    'is_warning': days_until <= 7,
                    'title': f'Contract expiry: {employee_name}',
                    'description': f'{contract.department.name if contract.department else "No department"} · {contract.contract_number}',
                    'dot_color': 'red',
                    'link': '/hr/contracts',
                }
            )

        upcoming_new_hires = (
            User.objects.select_related('department')
            .filter(start_date__gte=today, start_date__lte=cutoff)
            .order_by('start_date', 'first_name', 'last_name', 'id')
        )
        for employee in upcoming_new_hires:
            event_date = employee.start_date
            days_until = self._days_until(today, event_date)
            full_name = f'{employee.first_name} {employee.last_name}'.strip() or employee.username
            department = employee.department.name if employee.department else 'No department'
            events.append(
                {
                    'id': f'onboarding-{employee.id}',
                    'type': 'ONBOARDING',
                    'date': event_date.isoformat(),
                    'days_until': days_until,
                    'is_warning': days_until <= 7,
                    'title': f'New employee onboarding: {full_name}',
                    'description': department,
                    'dot_color': 'blue',
                    'link': None,
                }
            )

        month_start = date(today.year, today.month, 1)
        unpaid_payrolls = (
            PayrollEntry.objects.filter(paid=False, month__gte=month_start, month__lte=cutoff)
            .annotate(month_bucket=TruncMonth('month'))
            .values('month_bucket')
            .annotate(unpaid_count=Count('id'))
            .order_by('month_bucket')
        )
        for row in unpaid_payrolls:
            month_bucket = row['month_bucket']
            if month_bucket is None:
                continue

            bucket_date = month_bucket.date() if hasattr(month_bucket, 'date') else month_bucket
            event_date = self._month_end(bucket_date)
            if event_date < today or event_date > cutoff:
                continue

            days_until = self._days_until(today, event_date)
            month_label = event_date.strftime('%B %Y')
            unpaid_count = row['unpaid_count']
            events.append(
                {
                    'id': f'payroll-{bucket_date.strftime("%Y-%m")}',
                    'type': 'PAYROLL_PROCESSING',
                    'date': event_date.isoformat(),
                    'days_until': days_until,
                    'is_warning': days_until <= 7,
                    'title': f'Payroll processing: {month_label}',
                    'description': f'{unpaid_count} unpaid payroll entr{"y" if unpaid_count == 1 else "ies"}',
                    'dot_color': 'blue',
                    'link': None,
                }
            )

        events.sort(key=lambda item: (item['date'], item['type'], item['title']))

        return Response({'events': events, 'window_days': horizon_days}, status=status.HTTP_200_OK)


class HrAttendanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view attendance.'}, status=status.HTTP_403_FORBIDDEN)

        week_raw = request.query_params.get('week')
        today = timezone.localdate()

        if week_raw:
            parsed_week_start = None
            try:
                parsed_week_start = datetime.strptime(week_raw, '%Y-%m-%d').date()
            except ValueError:
                try:
                    parsed_week_start = datetime.strptime(f'{week_raw}-1', '%G-W%V-%u').date()
                except ValueError:
                    return Response(
                        {'detail': 'Invalid week format. Use YYYY-MM-DD or YYYY-Www.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            week_start = parsed_week_start - timedelta(days=parsed_week_start.weekday())
        else:
            week_start = today - timedelta(days=today.weekday())

        days = [week_start + timedelta(days=offset) for offset in range(7)]
        week_end = days[-1]

        attendance_rows = Attendance.objects.filter(date__gte=week_start, date__lte=week_end).select_related('employee')
        by_key = {(row.employee_id, row.date.isoformat()): row.status for row in attendance_rows}

        employees = User.objects.select_related('department').all().order_by('id')
        employee_grid = []
        for employee in employees:
            statuses = {}
            for day in days:
                day_key = day.isoformat()
                statuses[day_key] = by_key.get((employee.id, day_key))

            full_name = f'{employee.first_name} {employee.last_name}'.strip() or employee.username
            employee_grid.append(
                {
                    'employee_id': employee.id,
                    'employee_name': full_name,
                    'department': employee.department.name if employee.department else None,
                    'statuses': statuses,
                }
            )

        return Response(
            {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'days': [d.isoformat() for d in days],
                'grid': employee_grid,
            },
            status=status.HTTP_200_OK,
        )


class LeaveRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view leave requests.'}, status=status.HTTP_403_FORBIDDEN)

        status_filter = (request.query_params.get('status') or '').strip().upper()

        leave_requests = (
            LeaveRequest.objects.select_related('employee', 'employee__department', 'department', 'approved_by')
            .all()
            .order_by('-created_at', '-id')
        )

        if status_filter and status_filter != 'ALL':
            leave_requests = leave_requests.filter(status=status_filter)

        rows = []
        for leave_request in leave_requests:
            employee_name = (
                f'{leave_request.employee.first_name} {leave_request.employee.last_name}'.strip()
                or leave_request.employee.username
            )
            department = leave_request.department or leave_request.employee.department
            days = (leave_request.to_date - leave_request.from_date).days + 1

            rows.append(
                {
                    'id': leave_request.id,
                    'employee': {
                        'id': leave_request.employee_id,
                        'name': employee_name,
                        'username': leave_request.employee.username,
                    },
                    'department': None
                    if department is None
                    else {
                        'id': department.id,
                        'name': department.name,
                        'slug': department.slug,
                    },
                    'type': leave_request.type,
                    'from_date': leave_request.from_date.isoformat(),
                    'to_date': leave_request.to_date.isoformat(),
                    'days': max(1, days),
                    'status': leave_request.status,
                    'reason': leave_request.reason,
                    'approved_by': None
                    if leave_request.approved_by is None
                    else {
                        'id': leave_request.approved_by_id,
                        'name': f'{leave_request.approved_by.first_name} {leave_request.approved_by.last_name}'.strip()
                        or leave_request.approved_by.username,
                        'username': leave_request.approved_by.username,
                    },
                    'created_at': leave_request.created_at.isoformat(),
                }
            )

        return Response(rows, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can create leave requests.'}, status=status.HTTP_403_FORBIDDEN)

        employee_id = request.data.get('employee')
        leave_type = request.data.get('type', LeaveRequest.Type.VACATION)
        from_date_raw = request.data.get('from_date')
        to_date_raw = request.data.get('to_date')
        reason = request.data.get('reason', '')

        if not employee_id or not from_date_raw or not to_date_raw:
            return Response(
                {'detail': 'employee, from_date and to_date are required.'}, status=status.HTTP_400_BAD_REQUEST
            )

        employee = get_object_or_404(User.objects.select_related('department'), id=employee_id)

        try:
            from_date_value = date.fromisoformat(from_date_raw)
            to_date_value = date.fromisoformat(to_date_raw)
        except ValueError:
            return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        leave_request = LeaveRequest.objects.create(
            employee=employee,
            department=employee.department,
            type=leave_type,
            from_date=from_date_value,
            to_date=to_date_value,
            reason=reason,
            status=LeaveRequest.Status.PENDING,
        )

        return Response(
            {
                'id': leave_request.id,
                'employee': leave_request.employee_id,
                'type': leave_request.type,
                'from_date': leave_request.from_date.isoformat(),
                'to_date': leave_request.to_date.isoformat(),
                'status': leave_request.status,
            },
            status=status.HTTP_201_CREATED,
        )


class LeaveRequestApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can approve leave requests.'}, status=status.HTTP_403_FORBIDDEN)

        leave_request = get_object_or_404(LeaveRequest, id=id)
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.approved_by = request.user
        leave_request.save(update_fields=['status', 'approved_by', 'updated_at'])

        return Response({'id': leave_request.id, 'status': leave_request.status}, status=status.HTTP_200_OK)


class LeaveRequestRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can reject leave requests.'}, status=status.HTTP_403_FORBIDDEN)

        leave_request = get_object_or_404(LeaveRequest, id=id)
        leave_request.status = LeaveRequest.Status.REJECTED
        leave_request.approved_by = request.user
        leave_request.save(update_fields=['status', 'approved_by', 'updated_at'])

        return Response({'id': leave_request.id, 'status': leave_request.status}, status=status.HTTP_200_OK)


class ContractListView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _computed_status(contract, today):
        if contract.end_date is None:
            return 'ACTIVE'
        if contract.end_date < today:
            return 'EXPIRED'
        if contract.end_date <= today + timedelta(days=30):
            return 'EXPIRING'
        return 'ACTIVE'

    @staticmethod
    def _serialize_contract(contract, today):
        return {
            'id': contract.id,
            'contract_number': contract.contract_number,
            'employee': contract.employee_id,
            'employee_name': (
                f'{contract.employee.first_name} {contract.employee.last_name}'.strip() or contract.employee.username
            ),
            'department': contract.department.name if contract.department else None,
            'type': contract.type,
            'start_date': contract.start_date.isoformat(),
            'end_date': contract.end_date.isoformat() if contract.end_date else None,
            'salary_ron': str(contract.salary_ron),
            'status': ContractListView._computed_status(contract, today),
        }

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view contracts.'}, status=status.HTTP_403_FORBIDDEN)

        status_filter = (request.query_params.get('status') or '').strip().lower()
        today = timezone.localdate()

        contracts = Contract.objects.select_related('employee', 'department').all().order_by('id')
        rows = []
        for contract in contracts:
            computed_status = self._computed_status(contract, today)

            if status_filter == 'expiring' and computed_status != 'EXPIRING':
                continue

            rows.append(self._serialize_contract(contract, today))

        return Response({'contracts': rows}, status=status.HTTP_200_OK)


class ContractDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view contract details.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        contract = get_object_or_404(Contract.objects.select_related('employee', 'department'), id=id)
        return Response(ContractListView._serialize_contract(contract, today), status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can edit contracts.'}, status=status.HTTP_403_FORBIDDEN)

        contract = get_object_or_404(Contract.objects.select_related('employee', 'department'), id=id)
        update_fields = []

        if 'type' in request.data:
            type_value = (request.data.get('type') or '').strip().upper()
            if type_value not in Contract.Type.values:
                return Response({'detail': 'Invalid contract type.'}, status=status.HTTP_400_BAD_REQUEST)
            contract.type = type_value
            update_fields.append('type')

        if 'start_date' in request.data:
            try:
                contract.start_date = date.fromisoformat(request.data['start_date'])
            except (ValueError, TypeError):
                return Response({'detail': 'Invalid start_date. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
            update_fields.append('start_date')

        if 'end_date' in request.data:
            end_raw = request.data.get('end_date')
            if end_raw in (None, ''):
                contract.end_date = None
            else:
                try:
                    contract.end_date = date.fromisoformat(end_raw)
                except (ValueError, TypeError):
                    return Response(
                        {'detail': 'Invalid end_date. Use YYYY-MM-DD or null.'}, status=status.HTTP_400_BAD_REQUEST
                    )
            update_fields.append('end_date')

        if 'salary_ron' in request.data:
            try:
                salary = Decimal(str(request.data.get('salary_ron')))
            except (InvalidOperation, TypeError):
                return Response({'detail': 'salary_ron must be a number.'}, status=status.HTTP_400_BAD_REQUEST)
            if salary < 0:
                return Response({'detail': 'salary_ron cannot be negative.'}, status=status.HTTP_400_BAD_REQUEST)
            contract.salary_ron = salary
            update_fields.append('salary_ron')

        if 'department' in request.data:
            dept_raw = request.data.get('department')
            if dept_raw in (None, ''):
                contract.department = None
            else:
                department = get_object_or_404(Department, id=dept_raw)
                contract.department = department
            update_fields.append('department')

        if contract.end_date is not None and contract.end_date < contract.start_date:
            return Response({'detail': 'end_date cannot be before start_date.'}, status=status.HTTP_400_BAD_REQUEST)

        if update_fields:
            contract.save(update_fields=update_fields + ['updated_at'])

        today = timezone.localdate()
        contract = Contract.objects.select_related('employee', 'department').get(id=contract.id)
        return Response(ContractListView._serialize_contract(contract, today), status=status.HTTP_200_OK)


class PayrollListView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _format_money(value):
        return str(Decimal(str(value or 0)).quantize(Decimal('0.01')))

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view payroll.'}, status=status.HTTP_403_FORBIDDEN)

        month_raw = request.query_params.get('month')
        if not month_raw:
            return Response(
                {'detail': 'month query parameter is required (YYYY-MM).'}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            month_start = date.fromisoformat(f'{month_raw}-01')
        except ValueError:
            return Response({'detail': 'Invalid month format. Use YYYY-MM.'}, status=status.HTTP_400_BAD_REQUEST)

        bonus_override = None
        deductions_override = None
        if 'bonus' in request.query_params or 'deductions' in request.query_params:
            bonus_raw = request.query_params.get('bonus', '0')
            deductions_raw = request.query_params.get('deductions', '0')
            try:
                bonus_override = Decimal(str(bonus_raw))
                deductions_override = Decimal(str(deductions_raw))
            except (InvalidOperation, TypeError):
                return Response(
                    {'detail': 'bonus and deductions must be numeric values.'}, status=status.HTTP_400_BAD_REQUEST
                )

        entries = (
            PayrollEntry.objects.select_related('employee', 'employee__department')
            .filter(
                month__year=month_start.year,
                month__month=month_start.month,
            )
            .order_by('id')
        )

        rows = []
        total_base = Decimal('0.00')
        total_bonus = Decimal('0.00')
        total_deductions = Decimal('0.00')
        total_net = Decimal('0.00')
        processed_count = 0

        for entry in entries:
            base = Decimal(entry.gross_salary_ron or 0)
            recorded_net = Decimal(entry.net_salary_ron or 0)

            if bonus_override is not None and deductions_override is not None:
                bonus_value = bonus_override
                deductions_value = deductions_override
                net = base + bonus_value - deductions_value
            else:
                bonus_value = Decimal('0.00')
                deductions_value = max(Decimal('0.00'), base - recorded_net)
                net = recorded_net

            total_base += base
            total_bonus += bonus_value
            total_deductions += deductions_value
            total_net += net
            if entry.paid:
                processed_count += 1

            rows.append(
                {
                    'id': entry.id,
                    'employee': entry.employee_id,
                    'employee_name': (
                        f'{entry.employee.first_name} {entry.employee.last_name}'.strip() or entry.employee.username
                    ),
                    'department': entry.employee.department.name if entry.employee.department else None,
                    'month': month_start.isoformat(),
                    'base_salary_ron': self._format_money(base),
                    'bonus_ron': self._format_money(bonus_value),
                    'deductions_ron': self._format_money(deductions_value),
                    'net_salary_ron': self._format_money(net),
                    'recorded_net_salary_ron': self._format_money(recorded_net),
                    'status': 'PROCESSED' if entry.paid else 'PENDING',
                    'is_paid': bool(entry.paid),
                }
            )

        summary = {
            'total_employees': len(rows),
            'processed_count': processed_count,
            'pending_count': len(rows) - processed_count,
            'total_base_ron': self._format_money(total_base),
            'total_bonus_ron': self._format_money(total_bonus),
            'total_deductions_ron': self._format_money(total_deductions),
            'total_net_ron': self._format_money(total_net),
        }

        return Response({'month': month_raw, 'summary': summary, 'payroll': rows}, status=status.HTTP_200_OK)


class SupplierListView(APIView):
    """Return list of suppliers (for frontend receive form)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # allow inventory and CEO to list suppliers
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        qs = Supplier.objects.all().order_by('name')
        serializer = SupplierSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InventoryProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class InventoryProductsView(APIView):
    """Return products with search, category, and status filters. Supports conditional pagination."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response(
                {'detail': 'Only Inventory Managers and CEO can view products.'}, status=status.HTTP_403_FORBIDDEN
            )

        search = request.query_params.get('search', '').strip()
        category = request.query_params.get('category', 'All').strip()
        statuses = request.query_params.getlist('status')

        qs = Product.objects.all().order_by('name')

        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))

        if category and category.lower() != 'all':
            qs = qs.filter(category__iexact=category)

        if statuses:
            statuses_up = [s.upper() for s in statuses if s.upper() != 'ALL']
            if statuses_up:
                # We need to build a Q object for the statuses
                status_query = Q()
                for s in statuses_up:
                    if s == 'OUT':
                        status_query |= Q(stock_count__lte=0)
                    elif s == 'LOW':
                        status_query |= Q(stock_count__lt=F('min_stock'), stock_count__gt=0)
                    elif s == 'OK':
                        status_query |= Q(stock_count__gte=F('min_stock'), stock_count__gt=0)
                qs = qs.filter(status_query)

        # Only paginate if 'page' is requested
        if 'page' in request.query_params:
            paginator = InventoryProductPagination()
            page = paginator.paginate_queryset(qs, request)
            iterable = page
            is_paginated = True
        else:
            iterable = qs
            is_paginated = False
            paginator = None

        products = []
        for p in iterable:
            stock = int(p.stock_count or 0)
            minimum = int(p.min_stock or 0)

            if stock <= 0:
                status_val = 'OUT'
            elif stock < minimum:
                status_val = 'LOW'
            else:
                status_val = 'OK'

            products.append(
                {
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku,
                    'category': p.category,
                    'stock_count': stock,
                    'min_stock': minimum,
                    'unit_price_ron': float(p.unit_price_ron or 0),
                    'status': status_val,
                    'shortfall': max(0, minimum - stock),
                }
            )

        if is_paginated:
            return paginator.get_paginated_response(products)
        return Response(products, status=status.HTTP_200_OK)

    def post(self, request):
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventoryProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        product = get_object_or_404(Product, id=id)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StockMovementCreateView(APIView):
    """Create inbound/outbound stock movement. POST only."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # List stock movements with pagination and filters
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        qs = StockMovement.objects.select_related('product', 'supplier', 'created_by').all().order_by('-created_at')

        # Filters: ?type=, ?product= (id or sku), ?date_from=YYYY-MM-DD, ?date_to=YYYY-MM-DD
        types = request.query_params.getlist('type')
        if types:
            types_up = [t.upper() for t in types if t]
            qs = qs.filter(movement_type__in=types_up)

        product = request.query_params.get('product')
        if product:
            if product.isdigit():
                qs = qs.filter(product_id=int(product))
            else:
                qs = qs.filter(product__sku=product)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        try:
            if date_from:
                df = date.fromisoformat(date_from)
                qs = qs.filter(created_at__date__gte=df)
            if date_to:
                dt = date.fromisoformat(date_to)
                qs = qs.filter(created_at__date__lte=dt)
        except Exception:
            # ignore parse errors and return unfiltered by date
            pass

        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginated = paginator.paginate_queryset(qs, request)
        serializer = StockMovementSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Only inventory role allowed
        if getattr(request.user, 'role', None) not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        serializer = StockMovementSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        movement = serializer.save()

        # Return created movement and updated product data
        product = movement.product
        product_data = ProductSerializer(product).data

        return Response(
            {'movement': StockMovementSerializer(movement).data, 'product': product_data},
            status=status.HTTP_201_CREATED,
        )


class DashboardItView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response(
                {'detail': 'Access denied. Only IT and CEO can view this dashboard.'}, status=status.HTTP_403_FORBIDDEN
            )

        now = timezone.now()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        base_stats = Ticket.objects.aggregate(
            open_ticket=Count('id', filter=Q(status=Ticket.Status.OPEN)),
            in_progress=Count('id', filter=Q(status=Ticket.Status.IN_PROGRESS)),
            resolved_this_week=Count('id', filter=Q(status=Ticket.Status.RESOLVED, resolved_at__gte=start_of_week)),
            critical_open=Count(
                'id', filter=Q(status=Ticket.Status.OPEN, priority__in=[Ticket.Priority.HIGH, Ticket.Priority.URGENT])
            ),
        )

        resolved_qs = Ticket.objects.filter(status=Ticket.Status.RESOLVED, resolved_at__gte=start_of_week).annotate(
            duration=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        )

        perf_metrics = resolved_qs.aggregate(
            avg_res_time=Avg('duration'),
            sla_met_count=Count('id', filter=Q(duration__lte=timedelta(hours=4))),
        )

        avg_hrs = 0
        if perf_metrics['avg_res_time']:
            avg_hrs = round(perf_metrics['avg_res_time'].total_seconds() / 3600, 2)

        sla_pct = 0
        total_resolved = base_stats['resolved_this_week']
        if total_resolved > 0:
            sla_pct = round((perf_metrics['sla_met_count'] / total_resolved) * 100, 2)

        return Response(
            {
                'open_ticket': base_stats['open_ticket'],
                'in_progress': base_stats['in_progress'],
                'resolved_this_week': total_resolved,
                'ceo_it_summary': {
                    'avg_resolution_time_hrs': avg_hrs,
                    'sla_met_percentage': sla_pct,
                    'critical_open': base_stats['critical_open'],
                },
            },
            status=status.HTTP_200_OK,
        )


class ItTicketTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response(
                {'detail': 'Access denied. Only IT and CEO can view ticket trends.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        current_week_start = now - timedelta(days=now.weekday())
        current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = current_week_start - timedelta(weeks=5)
        window_end = current_week_start + timedelta(weeks=1)

        opened_rows = (
            Ticket.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
            .annotate(week=TruncWeek('created_at'))
            .values('week')
            .annotate(opened_count=Count('id'))
            .order_by('week')
        )

        closed_rows = (
            Ticket.objects.filter(
                resolved_at__isnull=False,
                resolved_at__gte=window_start,
                resolved_at__lt=window_end,
            )
            .annotate(week=TruncWeek('resolved_at'))
            .values('week')
            .annotate(closed_count=Count('id'))
            .order_by('week')
        )

        opened_by_week = {row['week'].date().isoformat(): row['opened_count'] for row in opened_rows}
        closed_by_week = {row['week'].date().isoformat(): row['closed_count'] for row in closed_rows}

        weeks = []
        for week_index in range(6):
            week_start = window_start + timedelta(weeks=week_index)
            week_key = week_start.date().isoformat()
            weeks.append(
                {
                    'week_start': week_key,
                    'opened_count': opened_by_week.get(week_key, 0),
                    'closed_count': closed_by_week.get(week_key, 0),
                }
            )

        return Response({'weeks': weeks}, status=status.HTTP_200_OK)


class TechnicianStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            return Response(
                {'detail': 'Access denied. Only IT and CEO can view technician stats.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            days = int(request.query_params.get('days', 30))
        except (TypeError, ValueError):
            days = 30

        if days <= 0:
            days = 30

        window_start = timezone.now() - timedelta(days=days)
        sla_threshold = timedelta(hours=IT_SLA_THRESHOLD_HOURS)

        resolved_rows = (
            Ticket.objects.filter(
                assigned_to__role=User.Role.IT,
                status=Ticket.Status.RESOLVED,
                resolved_at__gte=window_start,
                assigned_to__isnull=False,
            )
            .annotate(
                resolution_time=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField()),
            )
            .annotate(
                sla_met=Case(
                    When(resolution_time__lte=sla_threshold, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            .values('assigned_to_id', 'assigned_to__username')
            .annotate(
                resolved_count=Count('id'),
                avg_resolution_time=Avg('resolution_time'),
                sla_met_count=Sum('sla_met'),
            )
            .order_by('assigned_to__username')
        )

        rows_by_user = {row['assigned_to_id']: row for row in resolved_rows}

        technicians = []
        for tech in User.objects.filter(role=User.Role.IT).order_by('username'):
            row = rows_by_user.get(tech.id)
            resolved_count = int(row['resolved_count']) if row else 0
            avg_duration = row['avg_resolution_time'] if row and row['avg_resolution_time'] is not None else None
            sla_met_count = int(row['sla_met_count']) if row and row['sla_met_count'] is not None else 0

            avg_resolution_hours = 0.0
            if avg_duration is not None:
                avg_resolution_hours = round(avg_duration.total_seconds() / 3600, 2)

            sla_percent = 0.0
            if resolved_count > 0:
                sla_percent = round((sla_met_count / resolved_count) * 100, 2)

            technicians.append(
                {
                    'user_id': tech.id,
                    'username': tech.username,
                    'resolved_count': resolved_count,
                    'avg_resolution_hours': avg_resolution_hours,
                    'sla_percent': sla_percent,
                }
            )

        return Response(
            {
                'days': days,
                'sla_threshold_hours': IT_SLA_THRESHOLD_HOURS,
                'technicians': technicians,
            },
            status=status.HTTP_200_OK,
        )


class TicketPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ('total_count', self.page.paginator.count),
                    ('count', self.page.paginator.count),
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )


class OrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10

    def get_paginated_response(self, data, total_ron_sum):
        return Response(
            OrderedDict(
                [
                    ('total_count', self.page.paginator.count),
                    ('total_ron_sum', str(total_ron_sum)),
                    ('count', self.page.paginator.count),
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )


class InvoicePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ('total_count', self.page.paginator.count),
                    ('count', self.page.paginator.count),
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )


class TicketFilterSet(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    category = filters.CharFilter(method='filter_category')
    status = filters.CharFilter(field_name='status')
    assigned_to = filters.CharFilter(method='filter_assigned_to')

    class Meta:
        model = Ticket
        fields = ['search', 'category', 'status', 'assigned_to']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value) | Q(ticket_number__icontains=value)
        )

    def filter_category(self, queryset, name, value):
        if value.isdigit():
            return queryset.filter(department_id=int(value))

        return queryset.filter(Q(department__name__iexact=value) | Q(department__slug__iexact=value))

    def filter_assigned_to(self, queryset, name, value):
        request = getattr(self, 'request', None)
        if value == 'me' and request and request.user and request.user.is_authenticated:
            return queryset.filter(assigned_to=request.user)

        if value.isdigit():
            return queryset.filter(assigned_to_id=int(value))

        return queryset.none()


class TicketListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = TicketFilterSet

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TicketCreateSerializer
        return TicketSerializer

    def get_queryset(self):
        request = self.request
        if request.user.role not in [User.Role.IT, User.Role.CEO]:
            raise PermissionDenied('Only IT technicians and CEO can view tickets.')

        return (
            Ticket.objects.select_related('department', 'requested_by', 'assigned_to', 'requested_for')
            .all()
            .order_by('-created_at')
        )

    def create(self, request, *args, **kwargs):
        """Allow any authenticated user to create a ticket"""
        return super().create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        # call parent to get paginated response
        response = super().list(request, *args, **kwargs)

        assigned_to = request.query_params.get('assigned_to')
        if assigned_to == 'me' and request.user and request.user.is_authenticated:
            base_qs = Ticket.objects.filter(assigned_to=request.user)
            in_progress_count = base_qs.filter(status=Ticket.Status.IN_PROGRESS).count()
            assigned_count = base_qs.count()
            resolved_count = base_qs.filter(status=Ticket.Status.RESOLVED).count()

            # attach a technician summary to the response payload
            try:
                # response.data is a dict-like from DRF
                response.data['technician_summary'] = {
                    'in_progress_count': in_progress_count,
                    'assigned_count': assigned_count,
                    'resolved_count': resolved_count,
                }
            except Exception:
                # best-effort: if response.data isn't mutable, skip
                pass

        return response


class TicketDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketUpdateSerializer
    http_method_names = ['patch']
    lookup_field = 'id'
    queryset = Ticket.objects.select_related('department', 'requested_by', 'assigned_to').all()

    def get_queryset(self):
        return Ticket.objects.select_related('department', 'requested_by', 'assigned_to').all()

    def patch(self, request, *args, **kwargs):
        if request.user.role not in [User.Role.IT, User.Role.CEO]:
            raise PermissionDenied('Only IT technicians and CEO can update tickets.')
        return self.partial_update(request, *args, **kwargs)


class LatestHrDigestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        report = Report.objects.filter(category=Report.Category.HR).order_by('-generated_at').first()
        if not report:
            return Response({'detail': 'No digests found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can create orders.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderDetailSerializer(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product').get(id=order.id)
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view orders.'}, status=status.HTTP_403_FORBIDDEN)

        queryset = Order.objects.select_related('customer').all().order_by('-date', '-id')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(order_number__icontains=search) | Q(customer__name__icontains=search))

        status_filter = request.query_params.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        channel_filter = request.query_params.get('channel', '').strip()
        if channel_filter:
            queryset = queryset.filter(channel__iexact=channel_filter)

        totals = queryset.aggregate(total_ron_sum=Sum('value_ron'))
        total_ron_sum = totals['total_ron_sum'] or 0

        paginator = OrderPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data, total_ron_sum)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view orders.'}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
            id=id,
        )
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can update orders.'}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
            id=id,
        )

        status_value = (request.data.get('status') or '').strip().upper()
        if not status_value:
            return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = {choice[0] for choice in Order.Status.choices}
        if status_value not in valid_statuses:
            return Response({'detail': 'Invalid status value.'}, status=status.HTTP_400_BAD_REQUEST)

        allowed_transitions = {
            Order.Status.PROCESSING: [Order.Status.SHIPPED, Order.Status.CANCELLED],
            Order.Status.SHIPPED: [Order.Status.DELIVERED],
            Order.Status.DELIVERED: [],
            Order.Status.CANCELLED: [],
        }

        if status_value != order.status:
            allowed_next = allowed_transitions.get(order.status, [])
            if status_value not in allowed_next:
                return Response({'detail': 'Invalid status transition.'}, status=status.HTTP_400_BAD_REQUEST)

        if status_value != order.status:
            order.status = status_value
            order.save(update_fields=['status', 'updated_at'])

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalesDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _pct_change(today_value, yesterday_value):
        today_numeric = float(today_value or 0)
        yesterday_numeric = float(yesterday_value or 0)

        if yesterday_numeric == 0:
            return 100.0 if today_numeric > 0 else 0.0

        return round(((today_numeric - yesterday_numeric) / yesterday_numeric) * 100, 2)

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view sales KPI dashboard.'}, status=status.HTTP_403_FORBIDDEN
            )

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

        pending_orders = base_queryset.filter(status=Order.Status.PROCESSING).aggregate(count=Count('id'))['count'] or 0

        returns_this_week = (
            base_queryset.filter(
                status=Order.Status.CANCELLED,
                date__gte=start_of_week,
                date__lte=today,
            ).aggregate(count=Count('id'))['count']
            or 0
        )

        orders_today = today_stats['orders_today'] or 0
        revenue_today_ron = today_stats['revenue_today_ron'] or 0
        orders_yesterday = yesterday_stats['orders_yesterday'] or 0
        revenue_yesterday_ron = yesterday_stats['revenue_yesterday_ron'] or 0

        data = {
            'orders_today': orders_today,
            'revenue_today_ron': str(revenue_today_ron),
            'pending_orders': pending_orders,
            'returns_this_week': returns_this_week,
            'pct_changes': {
                'orders': self._pct_change(orders_today, orders_yesterday),
                'revenue': self._pct_change(revenue_today_ron, revenue_yesterday_ron),
            },
        }
        return Response(data, status=status.HTTP_200_OK)


class SalesDailyOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view daily orders analytics.'}, status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        aggregated = (
            Order.objects.filter(date__gte=start_date, date__lte=today)
            .annotate(day=TruncDay('date'))
            .values('day')
            .annotate(orders_count=Count('id'))
            .order_by('day')
        )

        by_day = {}
        for row in aggregated:
            day_value = row['day']
            if hasattr(day_value, 'date'):
                day_value = day_value.date()
            by_day[day_value.isoformat()] = row['orders_count']

        days = []
        for index in range(7):
            current_day = start_date + timedelta(days=index)
            day_key = current_day.isoformat()
            days.append(
                {
                    'date': day_key,
                    'orders_count': by_day.get(day_key, 0),
                }
            )

        return Response({'days': days}, status=status.HTTP_200_OK)


class SalesTopProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view top products analytics.'}, status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        products = (
            OrderItem.objects.annotate(order_day=TruncDay('order__date'))
            .filter(order__date__gte=week_start, order__date__lte=week_end)
            .values('product', 'product__name', 'product__sku')
            .annotate(
                units_sold=Sum('quantity'),
                order_lines=Count('id'),
                selling_days=Count('order_day', distinct=True),
            )
            .order_by('-units_sold', 'product__name')[:5]
        )

        data = [
            {
                'product_id': row['product'],
                'product_name': row['product__name'],
                'product_sku': row['product__sku'],
                'units_sold': row['units_sold'] or 0,
            }
            for row in products
        ]

        return Response(
            {
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'products': data,
            },
            status=status.HTTP_200_OK,
        )


class InventoryDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.INVENTORY, User.Role.CEO]:
            return Response(
                {'detail': 'Only Inventory Managers and CEO can view this dashboard.'}, status=status.HTTP_403_FORBIDDEN
            )

        total_products = Product.objects.count()
        low_stock_count = Product.objects.filter(stock_count__lt=F('min_stock'), stock_count__gt=0).count()
        out_of_stock_count = Product.objects.filter(stock_count=0).count()
        deliveries_today = StockMovement.objects.filter(
            movement_type=StockMovement.Type.INBOUND, expected_date=date.today()
        ).count()

        return Response(
            {
                'total_products': total_products,
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count,
                'deliveries_today': deliveries_today,
            },
            status=status.HTTP_200_OK,
        )


class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ('total_count', self.page.paginator.count),
                    ('count', self.page.paginator.count),
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )


class SalesProductsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view the product catalogue.'}, status=status.HTTP_403_FORBIDDEN
            )

        queryset = Product.objects.all().order_by('name')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search))

        category = request.query_params.get('category', '').strip()
        if category:
            queryset = queryset.filter(category__iexact=category)

        paginator = ProductPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = SalesProductSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view customers.'}, status=status.HTTP_403_FORBIDDEN)

        customers = Customer.objects.annotate(
            total_value_ron=Coalesce(
                Sum('orders__value_ron'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            orders_count=Count('orders'),
        ).order_by('-total_value_ron', 'name')

        paginator = CustomerPagination()
        paginated = paginator.paginate_queryset(customers, request)
        serializer = CustomerSalesSummarySerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view customers.'}, status=status.HTTP_403_FORBIDDEN)

        customer = get_object_or_404(Customer.objects.prefetch_related('orders'), id=id)
        serializer = CustomerDetailSerializer(customer)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view invoices.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        all_invoices = Invoice.objects.all()

        totals = all_invoices.aggregate(
            paid_total=Sum('amount_ron', filter=Q(status=Invoice.Status.PAID)),
            pending_total=Sum(
                'amount_ron',
                filter=Q(status__in=[Invoice.Status.DRAFT, Invoice.Status.ISSUED])
                & (Q(due_date__gte=today) | Q(due_date__isnull=True)),
            ),
            overdue_total=Sum(
                'amount_ron',
                filter=Q(due_date__lt=today) & ~Q(status=Invoice.Status.PAID),
            ),
        )

        queryset = all_invoices.select_related('order', 'order__customer').order_by('-issued_date', '-id')

        status_filter = request.query_params.get('status', '').strip().upper()
        if status_filter:
            if status_filter == 'OVERDUE':
                queryset = queryset.filter(due_date__lt=today).exclude(status=Invoice.Status.PAID)
            else:
                queryset = queryset.filter(status__iexact=status_filter)

        paginator = InvoicePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = InvoiceListSerializer(paginated, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)
        paginated_response.data['paid_total'] = str(totals['paid_total'] or '0.00')
        paginated_response.data['pending_total'] = str(totals['pending_total'] or '0.00')
        paginated_response.data['overdue_total'] = str(totals['overdue_total'] or '0.00')
        return paginated_response


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can view invoices.'}, status=status.HTTP_403_FORBIDDEN)

        invoice = get_object_or_404(
            Invoice.objects.select_related('order', 'order__customer').prefetch_related('order__items__product'),
            id=id,
        )
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response({'detail': 'Only Sales and CEO can update invoices.'}, status=status.HTTP_403_FORBIDDEN)

        invoice = get_object_or_404(
            Invoice.objects.select_related('order', 'order__customer').prefetch_related('order__items__product'),
            id=id,
        )

        status_value = (request.data.get('status') or '').strip().upper()
        if not status_value:
            return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if status_value != Invoice.Status.PAID:
            return Response({'detail': 'Only PAID status updates are supported.'}, status=status.HTTP_400_BAD_REQUEST)

        if invoice.status != Invoice.Status.PAID:
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=['status', 'updated_at'])

        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalesChannelSplitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view channel split analytics.'}, status=status.HTTP_403_FORBIDDEN
            )

        rows = Order.objects.values('channel').annotate(orders_count=Count('id')).order_by('channel')
        total_orders = sum(row['orders_count'] for row in rows)

        channels = []
        running_pct = 0.0
        for index, row in enumerate(rows):
            if total_orders == 0:
                pct = 0.0
            elif index == len(rows) - 1:
                pct = round(100.0 - running_pct, 2)
            else:
                pct = round((row['orders_count'] / total_orders) * 100, 2)
                running_pct += pct

            channels.append(
                {
                    'channel': row['channel'],
                    'orders_count': row['orders_count'],
                    'percentage': pct,
                }
            )

        return Response({'channels': channels}, status=status.HTTP_200_OK)


class SalesRevenueTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.SALES, User.Role.CEO]:
            return Response(
                {'detail': 'Only Sales and CEO can view revenue trend analytics.'}, status=status.HTTP_403_FORBIDDEN
            )

        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        rows = []
        for index in range(7):
            current_day = start_date + timedelta(days=index)
            try:
                prior_year_day = current_day.replace(year=current_day.year - 1)
            except ValueError:
                prior_year_day = current_day - timedelta(days=365)

            current_total = Order.objects.filter(date=current_day).aggregate(total=Sum('value_ron'))['total'] or 0
            prior_year_total = Order.objects.filter(date=prior_year_day).aggregate(total=Sum('value_ron'))['total'] or 0

            rows.append(
                {
                    'date': current_day.isoformat(),
                    'current_year': str(current_total),
                    'prior_year': str(prior_year_total),
                }
            )

        return Response({'days': rows}, status=status.HTTP_200_OK)


class ReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        allowed_categories = _allowed_report_categories(request.user)
        reports = Report.objects.filter(category__in=allowed_categories).order_by('-generated_at')
        category = request.query_params.get('category')
        if category:
            if category not in allowed_categories:
                return Response(
                    {'detail': 'You do not have access to reports in this category.'}, status=status.HTTP_403_FORBIDDEN
                )
            reports = reports.filter(category=category)
        return Response(ReportSerializer(reports, many=True).data)


class ReportDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        from pathlib import Path

        report = get_object_or_404(Report, id=id)
        if not _can_access_report(request.user, report):
            return Response({'detail': 'You do not have access to this report.'}, status=status.HTTP_403_FORBIDDEN)
        if not report.file_path:
            return Response({'detail': 'File not available.'}, status=status.HTTP_404_NOT_FOUND)
        path = Path(report.file_path)
        if not path.exists():
            return Response({'detail': 'File not found on server.'}, status=status.HTTP_404_NOT_FOUND)

        # Determine content type based on file extension
        ext = path.suffix.lower()
        if ext == '.pdf':
            content_type = 'application/pdf'
        elif ext == '.csv':
            content_type = 'text/csv'
        else:
            content_type = 'application/octet-stream'

        return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=True, filename=path.name)


class ReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        from .agent import AgentRunner, get_registry

        if request.user.role != User.Role.CEO and not request.user.is_staff:
            raise PermissionDenied('Only CEO or admin can generate reports.')
        report = get_object_or_404(Report, slug=slug)
        directives = (request.data.get('directives') or '').strip()

        directives_line = f' Additional focus: {directives}.' if directives else ''
        message = (
            f'Generate the {report.name} report (slug: "{report.slug}", category: {report.category}, period: {report.period}).'
            f' Step 1: use the available query tools to gather all relevant real data from the app for this report category.'
            f' Step 2: call generate_report with slug="{report.slug}" and pass the collected data serialised as a JSON string in context_data.'
            f'{directives_line}'
        )

        agent = AgentRunner(user=request.user, current_page='/reports')
        agent.register_tools(get_registry().get_all())
        result = agent.run(message=message, history=[])

        report.refresh_from_db()
        return Response(
            {
                'response': result.get('response')
                or f'The {report.name} report has been generated and is ready to view.',
                'report': ReportSerializer(report).data,
            },
            status=status.HTTP_200_OK,
        )


class ReportViewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        from pathlib import Path

        report = get_object_or_404(Report, id=id)
        if not _can_access_report(request.user, report):
            return Response({'detail': 'You do not have access to this report.'}, status=status.HTTP_403_FORBIDDEN)
        if not report.file_path:
            return Response({'detail': 'Report not generated yet.'}, status=status.HTTP_404_NOT_FOUND)
        path = Path(report.file_path)
        if not path.exists():
            return Response({'detail': 'File not found on server.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'html': path.read_text(encoding='utf-8'), 'filename': path.name})


class SystemStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only CEO and IT can view system status
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            raise PermissionDenied('Only CEO or IT team can view system status.')

        systems = SystemStatus.objects.all()
        serializer = SystemStatusSerializer(systems, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssistantChatView(APIView):
    """
    API endpoint for the MIEZ Assistant chat functionality.

    POST /api/assistant/chat/
    - Accepts a user message and conversation history
    - Instantiates AgentRunner with role-specific system prompt and tools
    - Returns agent response and any tool calls made
    - Rate limited: 20 requests per user per minute
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Handle chat message POST request.

        Request body:
        {
            "message": "user message",
            "history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

        Response:
        {
            "response": "agent response text",
            "tool_calls_made": [
                {"tool_name": "...", "arguments": {...}},
                ...
            ]
        }
        """
        # Check rate limit
        if not self._check_rate_limit(request.user):
            return Response(
                {
                    'detail': 'Rate limit exceeded. Maximum 20 requests per minute per user.',
                    'rate_limit': {
                        'limit': 20,
                        'window_seconds': 60,
                    },
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Validate request
        serializer = AssistantChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message = serializer.validated_data['message']
        session_id = request.data.get('session_id')

        try:
            # Resolve or create session
            if session_id:
                session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
            else:
                session = ConversationSession.objects.create(user=request.user)

            # Build history from DB
            db_messages = session.messages.values('role', 'content')
            history = [{'role': m['role'], 'content': m['content']} for m in db_messages]

            # Persist user message
            ConversationMessage.objects.create(session=session, role='user', content=message)

            # Run agent
            current_page = serializer.validated_data.get('current_page', '')
            agent = AgentRunner(user=request.user, current_page=current_page)
            agent.register_tools(get_registry().get_all())
            result = agent.run(message=message, history=history)

            reply = result.get('response', '')

            # Persist assistant response
            ConversationMessage.objects.create(session=session, role='assistant', content=reply)
            session.save()  # bump updated_at

            response_serializer = AssistantChatResponseSerializer(data=result)
            if not response_serializer.is_valid():
                return Response(
                    {'detail': 'Invalid agent response format'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            data = response_serializer.data
            data['session_id'] = session.id
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'detail': f'Error processing chat: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _check_rate_limit(self, user) -> bool:
        """
        Check rate limit for user: max 20 requests per minute.

        Args:
            user: Django User object

        Returns:
            True if within limit, False if exceeded
        """
        cache_key = f'assistant_chat_rate_limit_{user.id}'
        request_count = cache.get(cache_key, 0)

        if request_count >= 20:
            return False

        # Increment and set 60-second expiry
        cache.set(cache_key, request_count + 1, timeout=60)
        return True


class HrDigestGenerateView(APIView):
    """Generate weekly HR digest with insights and create notifications for critical issues."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only CEO can request digest generation
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEO can request HR digest generation.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Generate the digest
            generator = DigestGenerator()
            digest = generator.generate()

            # Save as Report record
            report = Report.objects.create(
                name=f'HR Weekly Digest - {generator.week_start.strftime("%Y-%m-%d")}',
                slug=f'hr-digest-{generator.week_start.strftime("%Y%m%d")}',
                category=Report.Category.HR,
                period=digest['period'],
                file_path='',
                file_size_kb=0,
                generated_by=request.user,
                generated_at=generator.generated_at,
                digest_data=digest,
            )

            # Create notification for HR Manager if critical issues exist
            critical_insights = digest.get('critical', [])
            if critical_insights:
                self._notify_hr_managers(digest)
            else:
                # Log entry: No anomalies detected
                pass

            return Response(
                {
                    'success': True,
                    'digest': digest,
                    'report_id': report.id,
                    'notifications_sent': len(critical_insights) > 0,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {'detail': f'Error generating digest: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _notify_hr_managers(self, digest):
        """Create notifications for active HR Managers with critical issue summary."""
        summary = digest['summary_line']
        critical_count = len(digest.get('critical', []))
        notify_role(
            User.Role.HR,
            title=f'Critical HR Issues Detected ({critical_count})',
            body=summary,
            notification_type='WARNING',
            link='/reports?category=HR',
        )


class ConversationSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = ConversationSession.objects.filter(user=request.user).prefetch_related('messages')
        serializer = ConversationSessionListSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        session = ConversationSession.objects.create(user=request.user)
        serializer = ConversationSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConversationSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
        serializer = ConversationSessionSerializer(session)
        return Response(serializer.data)

    def delete(self, request, session_id):
        session = get_object_or_404(ConversationSession, id=session_id, user=request.user)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkflowListView(APIView):
    permission_classes = [IsAuthenticated]

    def _check_role(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Forbidden.'}, status=403)
        return None

    def get(self, request):
        if err := self._check_role(request):
            return err
        workflows = Workflow.objects.all().order_by('name')
        return Response(WorkflowSerializer(workflows, many=True).data)

    def post(self, request):
        if err := self._check_role(request):
            return err
        ser = WorkflowWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        workflow = ser.save()
        return Response(WorkflowSerializer(workflow).data, status=201)


class WorkflowDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_workflow(self, id):
        return get_object_or_404(Workflow, id=id)

    def _check_role(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Forbidden.'}, status=403)
        return None

    def patch(self, request, id):
        if err := self._check_role(request):
            return err
        workflow = self._get_workflow(id)
        ser = WorkflowWriteSerializer(workflow, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        workflow = ser.save()
        return Response(WorkflowSerializer(workflow).data)

    def delete(self, request, id):
        if err := self._check_role(request):
            return err
        workflow = self._get_workflow(id)
        workflow.delete()
        return Response(status=204)


class WorkflowToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Forbidden.'}, status=403)
        workflow = get_object_or_404(Workflow, id=id)
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response({'detail': 'is_active required.'}, status=400)
        workflow.is_active = bool(is_active)
        workflow.save(update_fields=['is_active', 'updated_at'])
        return Response({'id': workflow.id, 'is_active': workflow.is_active})


class WorkflowTriggersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{'value': v, 'label': l} for v, l in Workflow.TriggerType.choices])


class WorkflowActionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{'value': v, 'label': l} for v, l in Workflow.ActionType.choices])


class WorkflowLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'CEO':
            return Response({'detail': 'Forbidden.'}, status=403)
        logs = WorkflowLog.objects.select_related('workflow').order_by('-triggered_at')[:100]
        return Response(WorkflowLogSerializer(logs, many=True).data)


class RunInsightsAgentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from datetime import date

        from django.core.cache import cache

        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response(
                {'detail': 'Forbidden. Only CEO and HR Manager can run insights.'}, status=status.HTTP_403_FORBIDDEN
            )

        cache_key = f'run_insights_agent_{request.user.id}_{date.today().isoformat()}'
        count = cache.get(cache_key, 0)

        if count >= 3:
            return Response(
                {'detail': 'Rate limit exceeded: max 3 manual triggers per day.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        cache.set(cache_key, count + 1, timeout=86400)

        self._spawn_agent()

        return Response({'status': 'running', 'estimated_time': '~15 seconds'}, status=status.HTTP_200_OK)

    def _spawn_agent(self):
        """Run the HR agent in a background thread.

        Isolated in its own method so tests can patch it instead of spawning a
        real thread (running the agent for real writes Workflow/WorkflowLog,
        which deadlocks the shared SQLite test database).
        """
        import threading

        from django.core.management import call_command
        from django.db import connection

        def run_agent():
            try:
                call_command('run_hr_agent')
            finally:
                # Each thread gets its own DB connection; close it so we don't
                # leak connections held open for the life of the process.
                connection.close()

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        unread_count = qs.filter(is_read=False).count()
        page_size = min(int(request.query_params.get('page_size', 20)), 50)
        page = max(int(request.query_params.get('page', 1)), 1)
        total = qs.count()
        results = qs[(page - 1) * page_size : page * page_size]
        serializer = NotificationSerializer(results, many=True)
        return Response(
            {
                'count': total,
                'unread_count': unread_count,
                'results': serializer.data,
            }
        )


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        notification = get_object_or_404(Notification, id=id, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'id': notification.id, 'is_read': True})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        marked = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'marked_read': marked})
