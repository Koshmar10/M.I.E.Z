"""IT: tickets, assets, system status and IT dashboards."""

from collections import OrderedDict
from datetime import timedelta

from django.db.models import (
    Avg,
    Case,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Asset,
    SystemStatus,
    Ticket,
    User,
)
from ..serializers.it import (
    AssetSerializer,
    SystemStatusSerializer,
    TicketCreateSerializer,
    TicketSerializer,
    TicketUpdateSerializer,
)

IT_SLA_THRESHOLD_HOURS = 48


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


class SystemStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only CEO and IT can view system status
        if request.user.role not in [User.Role.CEO, User.Role.IT]:
            raise PermissionDenied('Only CEO or IT team can view system status.')

        systems = SystemStatus.objects.all()
        serializer = SystemStatusSerializer(systems, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
