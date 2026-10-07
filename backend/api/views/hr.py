"""HR: dashboards, attendance, leave requests, contracts, payroll and the AI HR digest."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import (
    Count,
    Q,
)
from django.db.models.functions import TruncMonth, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..management.commands.generate_hr_digest import DigestGenerator
from ..models import (
    Attendance,
    Contract,
    Department,
    LeaveRequest,
    PayrollEntry,
    Report,
    User,
)
from ..notifications import notify_role
from ..permissions import role_required
from ..serializers.reports import ReportSerializer
from ..services import BusinessRuleError
from ..services.hr import decide_leave_request


class HrDashboardView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO)]

    @staticmethod
    def _department_matches_role(department, role_keyword):
        slug = (getattr(department, 'slug', '') or '').strip().lower()
        name = (getattr(department, 'name', '') or '').strip().lower()
        keyword = role_keyword.lower().strip()
        return keyword in slug or keyword in name

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    @staticmethod
    def _month_end(value_date):
        next_month = (value_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        return next_month - timedelta(days=1)

    @staticmethod
    def _days_until(today, target_date):
        return (target_date - today).days

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def patch(self, request, id):
        leave_request = get_object_or_404(LeaveRequest, id=id)
        try:
            decide_leave_request(leave_request, approve=True, actor=request.user)
        except BusinessRuleError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'id': leave_request.id, 'status': leave_request.status}, status=status.HTTP_200_OK)


class LeaveRequestRejectView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def patch(self, request, id):
        leave_request = get_object_or_404(LeaveRequest, id=id)
        try:
            decide_leave_request(leave_request, approve=False, actor=request.user)
        except BusinessRuleError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'id': leave_request.id, 'status': leave_request.status}, status=status.HTTP_200_OK)


class ContractListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request, id):
        today = timezone.localdate()
        contract = get_object_or_404(Contract.objects.select_related('employee', 'department'), id=id)
        return Response(ContractListView._serialize_contract(contract, today), status=status.HTTP_200_OK)

    def patch(self, request, id):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    @staticmethod
    def _format_money(value):
        return str(Decimal(str(value or 0)).quantize(Decimal('0.01')))

    def get(self, request):
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


class LatestHrDigestView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
        report = Report.objects.filter(category=Report.Category.HR).order_by('-generated_at').first()
        if not report:
            return Response({'detail': 'No digests found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HrDigestGenerateView(APIView):
    """Generate weekly HR digest with insights and create notifications for critical issues."""

    permission_classes = [IsAuthenticated, role_required(User.Role.CEO)]

    def post(self, request):
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


class RunInsightsAgentView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def post(self, request):
        from datetime import date

        from django.core.cache import cache

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
