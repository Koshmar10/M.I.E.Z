"""Inventory: products and stock levels, stock movements, suppliers, dashboard and stock flow."""

from datetime import date, timedelta

from django.db.models import (
    F,
    Q,
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Product,
    StockMovement,
    Supplier,
    User,
)
from ..serializers.inventory import ProductSerializer, StockMovementSerializer, SupplierSerializer


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
