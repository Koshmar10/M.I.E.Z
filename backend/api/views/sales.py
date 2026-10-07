"""Sales: orders, invoices, customers, product catalogue and sales analytics."""

from datetime import timedelta

from django.db.models import (
    Count,
    DecimalField,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDay
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Customer,
    Invoice,
    Order,
    OrderItem,
    Product,
    User,
)
from ..pagination import StandardPagination, TenPerPagePagination, TwentyPerPagePagination
from ..permissions import role_required
from ..serializers.sales import (
    CustomerDetailSerializer,
    CustomerSalesSummarySerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    SalesProductSerializer,
)
from ..services import BusinessRuleError
from ..services.sales import change_order_status, mark_invoice_paid


class OrderListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderDetailSerializer(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product').get(id=order.id)
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):
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

        paginator = TenPerPagePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data, total_ron_sum=str(total_ron_sum))


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request, id):
        order = get_object_or_404(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
            id=id,
        )
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        order = get_object_or_404(
            Order.objects.select_related('customer', 'created_by').prefetch_related('items__product'),
            id=id,
        )

        status_value = (request.data.get('status') or '').strip().upper()
        if not status_value:
            return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            change_order_status(order, status_value)
        except BusinessRuleError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalesDashboardView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    @staticmethod
    def _pct_change(today_value, yesterday_value):
        today_numeric = float(today_value or 0)
        yesterday_numeric = float(yesterday_value or 0)

        if yesterday_numeric == 0:
            return 100.0 if today_numeric > 0 else 0.0

        return round(((today_numeric - yesterday_numeric) / yesterday_numeric) * 100, 2)

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
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


class SalesProductsView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
        queryset = Product.objects.all().order_by('name')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search))

        category = request.query_params.get('category', '').strip()
        if category:
            queryset = queryset.filter(category__iexact=category)

        paginator = TwentyPerPagePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = SalesProductSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
        customers = Customer.objects.annotate(
            total_value_ron=Coalesce(
                Sum('orders__value_ron'), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            orders_count=Count('orders'),
        ).order_by('-total_value_ron', 'name')

        paginator = StandardPagination()
        paginated = paginator.paginate_queryset(customers, request)
        serializer = CustomerSalesSummarySerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request, id):
        customer = get_object_or_404(Customer.objects.prefetch_related('orders'), id=id)
        serializer = CustomerDetailSerializer(customer)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
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

        paginator = TenPerPagePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = InvoiceListSerializer(paginated, many=True)
        return paginator.get_paginated_response(
            serializer.data,
            paid_total=str(totals['paid_total'] or '0.00'),
            pending_total=str(totals['pending_total'] or '0.00'),
            overdue_total=str(totals['overdue_total'] or '0.00'),
        )


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request, id):
        invoice = get_object_or_404(
            Invoice.objects.select_related('order', 'order__customer').prefetch_related('order__items__product'),
            id=id,
        )
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        invoice = get_object_or_404(
            Invoice.objects.select_related('order', 'order__customer').prefetch_related('order__items__product'),
            id=id,
        )

        status_value = (request.data.get('status') or '').strip().upper()
        if not status_value:
            return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if status_value != Invoice.Status.PAID:
            return Response({'detail': 'Only PAID status updates are supported.'}, status=status.HTTP_400_BAD_REQUEST)

        mark_invoice_paid(invoice)

        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalesChannelSplitView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
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
    permission_classes = [IsAuthenticated, role_required(User.Role.SALES, User.Role.CEO)]

    def get(self, request):
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
