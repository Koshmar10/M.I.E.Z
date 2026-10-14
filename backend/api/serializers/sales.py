"""Serializers for the sales catalogue, orders, customers and invoices."""

from django.utils import timezone
from rest_framework import serializers

from ..models import (
    Customer,
    Invoice,
    Order,
    OrderItem,
    Product,
)


class SalesProductSerializer(serializers.ModelSerializer):
    availability = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'category', 'unit_price_ron', 'stock_count', 'availability']

    def get_availability(self, obj):
        return obj.availability


class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'customer_name',
            'value_ron',
            'date',
            'status',
            'channel',
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'value_ron',
            'date',
            'status',
            'channel',
            'notes',
        ]
        read_only_fields = ['id', 'order_number']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class OrderItemDetailSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    line_total_ron = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'quantity',
            'unit_price_ron',
            'line_total_ron',
        ]

    def get_line_total_ron(self, obj):
        return obj.quantity * obj.unit_price_ron


class OrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'customer_name',
            'created_by',
            'created_by_username',
            'value_ron',
            'date',
            'status',
            'channel',
            'notes',
            'created_at',
            'updated_at',
            'items',
        ]


class CustomerSalesSummarySerializer(serializers.ModelSerializer):
    total_value_ron = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    orders_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'contact_name',
            'location',
            'tier',
            'orders_count',
            'total_value_ron',
        ]


class CustomerOrderHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'value_ron',
            'date',
            'status',
            'channel',
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    orders = CustomerOrderHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'contact_name',
            'contact_email',
            'contact_phone',
            'address',
            'location',
            'tier',
            'notes',
            'created_at',
            'updated_at',
            'orders',
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.name', read_only=True)
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'order',
            'order_number',
            'customer_name',
            'amount_ron',
            'status',
            'effective_status',
            'issued_date',
            'due_date',
        ]

    def get_effective_status(self, obj):
        today = timezone.localdate()
        if obj.due_date and obj.due_date < today and obj.status != Invoice.Status.PAID:
            return 'OVERDUE'
        return obj.status


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal_ron = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price_ron', 'subtotal_ron']

    def get_subtotal_ron(self, obj):
        return obj.quantity * obj.unit_price_ron


class InvoiceDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.name', read_only=True)
    line_items = InvoiceLineItemSerializer(source='order.items', many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'order',
            'order_number',
            'customer_name',
            'issued_date',
            'due_date',
            'status',
            'amount_ron',
            'line_items',
        ]
