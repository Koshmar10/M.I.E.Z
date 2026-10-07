"""Tests for api/views/sales.py: orders, invoices, customers and sales analytics."""

import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.models import Customer, Invoice, Order, OrderItem, Product, User

# Gives the plain pytest functions at the bottom database access (TestCase classes manage their own).
pytestmark = pytest.mark.django_db


class OrderListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_orders',
            role=User.Role.SALES,
            email='sales_orders@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_orders',
            role=User.Role.CEO,
            email='ceo_orders@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_orders',
            role=User.Role.HR,
            email='hr_orders@example.com',
        )

        self.customer_acme = Customer.objects.create(name='Acme SRL')
        self.customer_beta = Customer.objects.create(name='Beta SRL')

        self.product_a = Product.objects.create(name='Widget A', sku='WIDGET-A')
        self.product_b = Product.objects.create(name='Widget B', sku='WIDGET-B')

        self.order_1 = Order.objects.create(
            customer=self.customer_acme,
            created_by=self.sales_user,
            value_ron=Decimal('120.50'),
            status=Order.Status.PROCESSING,
            channel=Order.Channel.WEBSITE,
            notes='Priority handling',
        )
        self.order_2 = Order.objects.create(
            customer=self.customer_beta,
            created_by=self.sales_user,
            value_ron=Decimal('80.00'),
            status=Order.Status.SHIPPED,
            channel=Order.Channel.EMAG,
        )
        self.order_3 = Order.objects.create(
            customer=self.customer_acme,
            created_by=self.sales_user,
            value_ron=Decimal('40.00'),
            status=Order.Status.PROCESSING,
            channel=Order.Channel.DIRECT,
        )

        OrderItem.objects.create(
            order=self.order_1, product=self.product_a, quantity=2, unit_price_ron=Decimal('30.00')
        )
        OrderItem.objects.create(
            order=self.order_1, product=self.product_b, quantity=1, unit_price_ron=Decimal('60.50')
        )

    def test_order_number_is_auto_generated_with_hash_format(self):
        assert re.search(r'^#\d{4}$', self.order_1.order_number)

    def test_orders_list_supports_search_status_channel_and_includes_totals(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/orders/?search=Acme&status=PROCESSING&channel=WEBSITE')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_count'] == 1
        assert Decimal(response.data['total_ron_sum']) == Decimal('120.50')
        assert len(response.data['results']) == 1

        row = response.data['results'][0]
        assert 'order_number' in row
        assert row['customer_name'] == 'Acme SRL'
        assert Decimal(row['value_ron']) == Decimal('120.50')
        assert row['status'] == Order.Status.PROCESSING
        assert row['channel'] == Order.Channel.WEBSITE

    def test_orders_list_is_paginated_and_includes_total_sum_for_filtered_queryset(self):
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/orders/?search=SRL&page_size=2')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_count'] == 3
        assert Decimal(response.data['total_ron_sum']) == Decimal('240.50')
        assert len(response.data['results']) == 2

    def test_order_detail_includes_line_items_for_modal(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get(f'/api/orders/{self.order_1.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['order_number'] == self.order_1.order_number
        assert response.data['customer_name'] == 'Acme SRL'
        assert len(response.data['items']) == 2
        assert 'line_total_ron' in response.data['items'][0]

    def test_orders_endpoints_forbid_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        list_response = self.client.get('/api/orders/')
        detail_response = self.client.get(f'/api/orders/{self.order_1.id}/')

        assert list_response.status_code == status.HTTP_403_FORBIDDEN
        assert detail_response.status_code == status.HTTP_403_FORBIDDEN


class SalesDashboardKpiTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_kpi',
            role=User.Role.SALES,
            email='sales_kpi@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_kpi',
            role=User.Role.CEO,
            email='ceo_kpi@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_kpi',
            role=User.Role.HR,
            email='hr_kpi@example.com',
        )
        self.customer = Customer.objects.create(name='KPI Customer')

    def _create_order(self, *, amount, order_date, status_value):
        return Order.objects.create(
            customer=self.customer,
            created_by=self.sales_user,
            value_ron=Decimal(amount),
            date=order_date,
            status=status_value,
            channel=Order.Channel.WEBSITE,
        )

    def test_sales_dashboard_kpis_uses_today_yesterday_and_weekly_cancellations(self):
        self.client.force_authenticate(user=self.sales_user)

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())
        week_return_date = today - timedelta(days=1) if today.weekday() >= 1 else today

        self._create_order(amount='120.00', order_date=today, status_value=Order.Status.PROCESSING)
        self._create_order(amount='80.00', order_date=today, status_value=Order.Status.PROCESSING)
        self._create_order(amount='30.00', order_date=today, status_value=Order.Status.CANCELLED)

        self._create_order(amount='100.00', order_date=yesterday, status_value=Order.Status.DELIVERED)

        self._create_order(amount='15.00', order_date=week_return_date, status_value=Order.Status.CANCELLED)
        self._create_order(
            amount='22.00', order_date=start_of_week - timedelta(days=1), status_value=Order.Status.CANCELLED
        )

        response = self.client.get('/api/sales/dashboard/')

        today_orders = Order.objects.filter(date=today).count()
        today_revenue = Order.objects.filter(date=today).aggregate(total=Sum('value_ron'))['total'] or Decimal('0')
        yesterday_orders = Order.objects.filter(date=yesterday).count()
        yesterday_revenue = Order.objects.filter(date=yesterday).aggregate(total=Sum('value_ron'))['total'] or Decimal(
            '0'
        )
        processing_orders = Order.objects.filter(status=Order.Status.PROCESSING).count()
        returns_week = Order.objects.filter(
            status=Order.Status.CANCELLED,
            date__gte=start_of_week,
            date__lte=today,
        ).count()

        def pct_change(today_value, yesterday_value):
            today_numeric = float(today_value or 0)
            yesterday_numeric = float(yesterday_value or 0)
            if yesterday_numeric == 0:
                return 100.0 if today_numeric > 0 else 0.0
            return round(((today_numeric - yesterday_numeric) / yesterday_numeric) * 100, 2)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['orders_today'] == today_orders
        assert Decimal(response.data['revenue_today_ron']) == today_revenue
        assert response.data['pending_orders'] == processing_orders
        assert response.data['returns_this_week'] == returns_week
        assert response.data['pct_changes']['orders'] == pct_change(today_orders, yesterday_orders)
        assert response.data['pct_changes']['revenue'] == pct_change(today_revenue, yesterday_revenue)

    def test_sales_dashboard_kpis_allows_ceo(self):
        self.client.force_authenticate(user=self.ceo_user)
        response = self.client.get('/api/sales/dashboard/')
        assert response.status_code == status.HTTP_200_OK

    def test_sales_dashboard_kpis_forbids_other_roles(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get('/api/sales/dashboard/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


class SalesAnalyticsTask3Tests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_task3',
            role=User.Role.SALES,
            email='sales_task3@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_task3',
            role=User.Role.CEO,
            email='ceo_task3@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_task3',
            role=User.Role.HR,
            email='hr_task3@example.com',
        )

        self.customer = Customer.objects.create(name='Task3 Customer')
        self.product_a = Product.objects.create(name='Widget A', sku='TASK3-A')
        self.product_b = Product.objects.create(name='Widget B', sku='TASK3-B')
        self.product_c = Product.objects.create(name='Widget C', sku='TASK3-C')

    def _create_order_with_item(self, *, order_date, product, quantity):
        order = Order.objects.create(
            customer=self.customer,
            created_by=self.sales_user,
            value_ron=Decimal('10.00'),
            date=order_date,
            status=Order.Status.DELIVERED,
            channel=Order.Channel.WEBSITE,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price_ron=Decimal('10.00'),
        )
        return order

    def test_daily_orders_returns_last_seven_days_with_zero_filled_gaps(self):
        self.client.force_authenticate(user=self.sales_user)

        today = timezone.localdate()
        five_days_ago = today - timedelta(days=5)
        two_days_ago = today - timedelta(days=2)

        self._create_order_with_item(order_date=five_days_ago, product=self.product_a, quantity=1)
        self._create_order_with_item(order_date=five_days_ago, product=self.product_b, quantity=1)
        self._create_order_with_item(order_date=two_days_ago, product=self.product_a, quantity=1)

        response = self.client.get('/api/sales/daily-orders/')

        assert response.status_code == status.HTTP_200_OK
        assert 'days' in response.data
        assert len(response.data['days']) == 7

        counts_by_date = {row['date']: row['orders_count'] for row in response.data['days']}
        assert counts_by_date[five_days_ago.isoformat()] == 2
        assert counts_by_date[two_days_ago.isoformat()] == 1
        assert counts_by_date[today.isoformat()] == 0

    def test_top_products_uses_current_iso_week_and_sorts_by_units_sold(self):
        self.client.force_authenticate(user=self.ceo_user)

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        previous_week_day = week_start - timedelta(days=1)

        self._create_order_with_item(order_date=today, product=self.product_a, quantity=5)
        self._create_order_with_item(order_date=today, product=self.product_b, quantity=2)
        self._create_order_with_item(order_date=week_start, product=self.product_b, quantity=3)
        self._create_order_with_item(order_date=previous_week_day, product=self.product_c, quantity=100)

        response = self.client.get('/api/sales/top-products/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['week_start'] == week_start.isoformat()
        assert response.data['week_end'] == week_end.isoformat()

        products = response.data['products']
        assert len(products) == 2
        assert products[0]['product_name'] == 'Widget A'
        assert products[0]['units_sold'] == 5
        assert products[1]['product_name'] == 'Widget B'
        assert products[1]['units_sold'] == 5

    def test_task3_endpoints_forbid_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        daily_response = self.client.get('/api/sales/daily-orders/')
        top_response = self.client.get('/api/sales/top-products/')

        assert daily_response.status_code == status.HTTP_403_FORBIDDEN
        assert top_response.status_code == status.HTTP_403_FORBIDDEN


class InvoiceListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_invoices',
            role=User.Role.SALES,
            email='sales_invoices@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_invoices',
            role=User.Role.HR,
            email='hr_invoices@example.com',
        )
        self.customer = Customer.objects.create(name='Invoice Customer')
        today = timezone.localdate()

        order_a = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('100.00'))
        order_b = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('200.00'))
        order_c = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('300.00'))

        Invoice.objects.filter(order=order_a).update(status=Invoice.Status.PAID, amount_ron=Decimal('100.00'))
        Invoice.objects.filter(order=order_b).update(
            status=Invoice.Status.ISSUED, due_date=today - timedelta(days=1), amount_ron=Decimal('200.00')
        )
        Invoice.objects.filter(order=order_c).update(
            status=Invoice.Status.ISSUED, due_date=today + timedelta(days=7), amount_ron=Decimal('300.00')
        )

    def test_get_invoices_returns_summary_totals(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/invoices/')

        assert response.status_code == status.HTTP_200_OK
        assert 'paid_total' in response.data
        assert 'pending_total' in response.data
        assert 'overdue_total' in response.data
        assert Decimal(response.data['paid_total']) == Decimal('100.00')
        assert Decimal(response.data['overdue_total']) == Decimal('200.00')
        assert Decimal(response.data['pending_total']) == Decimal('300.00')

    def test_get_invoices_summary_totals_unaffected_by_status_filter(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/invoices/?status=Paid')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_count'] == 1
        assert Decimal(response.data['paid_total']) == Decimal('100.00')
        assert Decimal(response.data['overdue_total']) == Decimal('200.00')

    def test_get_invoices_forbids_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get('/api/invoices/')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_order_creation_auto_creates_invoice_via_signal(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.post(
            '/api/orders/',
            {
                'customer': self.customer.id,
                'value_ron': '450.00',
                'date': timezone.localdate().isoformat(),
                'status': Order.Status.PROCESSING,
                'channel': Order.Channel.WEBSITE,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get(id=response.data['id'])
        assert Invoice.objects.filter(order=order).exists()
        invoice = Invoice.objects.get(order=order)
        assert invoice.invoice_number.startswith('INV-')
        assert invoice.amount_ron == Decimal('450.00')


class CustomerListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_cust', role=User.Role.SALES, email='sales_cust@example.com'
        )
        self.hr_user = User.objects.create_user(username='hr_cust', role=User.Role.HR, email='hr_cust@example.com')

        self.customer_a = Customer.objects.create(name='Alpha Corp', tier=Customer.Tier.GOLD)
        self.customer_b = Customer.objects.create(name='Beta Ltd', tier=Customer.Tier.SILVER)

        Order.objects.create(
            customer=self.customer_a,
            created_by=self.sales_user,
            value_ron=Decimal('500.00'),
            status=Order.Status.PROCESSING,
        )
        Order.objects.create(
            customer=self.customer_a,
            created_by=self.sales_user,
            value_ron=Decimal('300.00'),
            status=Order.Status.PROCESSING,
        )
        Order.objects.create(
            customer=self.customer_b,
            created_by=self.sales_user,
            value_ron=Decimal('100.00'),
            status=Order.Status.PROCESSING,
        )

    def test_customer_list_returns_orders_count_and_tier(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/')

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        alpha = next(r for r in results if r['name'] == 'Alpha Corp')
        assert alpha['orders_count'] == 2
        assert alpha['tier'] == Customer.Tier.GOLD

    def test_customer_list_sorted_by_total_value_desc(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/')

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        values = [Decimal(r['total_value_ron']) for r in results]
        assert values == sorted(values, reverse=True)

    def test_customer_list_forbids_non_sales_role(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get('/api/customers/')

        assert response.status_code == status.HTTP_403_FORBIDDEN


class CustomerDetailViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_detail', role=User.Role.SALES, email='sales_detail@example.com'
        )
        self.hr_user = User.objects.create_user(username='hr_detail', role=User.Role.HR, email='hr_detail@example.com')

        self.customer = Customer.objects.create(name='Detail Corp', contact_name='Jane Doe', tier=Customer.Tier.BRONZE)
        self.order = Order.objects.create(
            customer=self.customer, created_by=self.sales_user, value_ron=Decimal('250.00'), status=Order.Status.SHIPPED
        )

    def test_customer_detail_returns_order_history(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Detail Corp'
        assert response.data['contact_name'] == 'Jane Doe'
        assert response.data['tier'] == Customer.Tier.BRONZE
        assert len(response.data['orders']) == 1
        assert response.data['orders'][0]['order_number'] == self.order.order_number

    def test_customer_detail_returns_404_for_missing_id(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/99999/')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_customer_detail_forbids_non_sales_role(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── pytest-style tests ────────────────────────────────────────────────────────


def _authed_sales_client():
    user = baker.make(
        User,
        role=User.Role.SALES,
        username='sales_test_user',
        email='sales_test_user@example.com',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _prior_year_day(day):
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day - timedelta(days=365)


def test_post_orders_valid_payload_creates_invoice_via_signal():
    client, _ = _authed_sales_client()
    customer = baker.make(Customer)

    payload = {
        'customer': customer.id,
        'value_ron': '123.45',
        'date': timezone.localdate().isoformat(),
        'status': Order.Status.PROCESSING,
        'channel': Order.Channel.EMAG,
        'notes': 'Created from pytest',
    }

    response = client.post('/api/orders/', payload, format='json')

    assert response.status_code == 201
    order_id = response.data['id']
    order = Order.objects.get(id=order_id)

    invoice = Invoice.objects.get(order=order)
    assert invoice.amount_ron == Decimal('123.45')
    assert invoice.invoice_number.startswith('INV-')


def test_get_orders_returns_paginated_list_with_total_ron_sum():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('10.00'))
    baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('20.00'))
    baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('5.00'))

    response = client.get('/api/orders/?page_size=2')

    assert response.status_code == 200
    assert response.data['total_count'] == 3
    assert Decimal(response.data['total_ron_sum']) == Decimal('35.00')
    assert len(response.data['results']) == 2


def test_get_orders_with_status_processing_filters_correctly():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    baker.make(Order, customer=customer, created_by=user, status=Order.Status.PROCESSING)
    baker.make(Order, customer=customer, created_by=user, status=Order.Status.SHIPPED)

    response = client.get('/api/orders/?status=Processing')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert all(item['status'] == Order.Status.PROCESSING for item in response.data['results'])


def test_get_orders_with_channel_emag_filters_correctly():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.EMAG)
    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.WEBSITE)

    response = client.get('/api/orders/?channel=eMAG')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert all(item['channel'] == Order.Channel.EMAG for item in response.data['results'])


def test_get_customers_sorted_by_total_value_desc_with_annotation():
    client, user = _authed_sales_client()

    customer_a = baker.make(Customer, name='Alpha')
    customer_b = baker.make(Customer, name='Beta')

    baker.make(Order, customer=customer_a, created_by=user, value_ron=Decimal('100.00'))
    baker.make(Order, customer=customer_a, created_by=user, value_ron=Decimal('50.00'))
    baker.make(Order, customer=customer_b, created_by=user, value_ron=Decimal('40.00'))

    response = client.get('/api/customers/')

    assert response.status_code == 200
    results = response.data['results']
    assert results[0]['name'] == 'Alpha'
    assert Decimal(results[0]['total_value_ron']) == Decimal('150.00')
    assert results[1]['name'] == 'Beta'
    assert Decimal(results[1]['total_value_ron']) == Decimal('40.00')


def test_get_invoices_computes_overdue_status_correctly():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)
    today = timezone.localdate()

    overdue_order = baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('10.00'))
    paid_order = baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('20.00'))
    future_order = baker.make(Order, customer=customer, created_by=user, value_ron=Decimal('30.00'))

    overdue_invoice = baker.make(
        Invoice,
        order=overdue_order,
        invoice_number='INV-90001',
        amount_ron=Decimal('10.00'),
        due_date=today - timedelta(days=1),
        status=Invoice.Status.ISSUED,
    )
    paid_invoice = baker.make(
        Invoice,
        order=paid_order,
        invoice_number='INV-90002',
        amount_ron=Decimal('20.00'),
        due_date=today - timedelta(days=2),
        status=Invoice.Status.PAID,
    )
    future_invoice = baker.make(
        Invoice,
        order=future_order,
        invoice_number='INV-90003',
        amount_ron=Decimal('30.00'),
        due_date=today + timedelta(days=2),
        status=Invoice.Status.ISSUED,
    )

    response = client.get('/api/invoices/?page_size=20')

    assert response.status_code == 200
    by_number = {row['invoice_number']: row for row in response.data['results']}

    assert by_number[overdue_invoice.invoice_number]['effective_status'] == 'OVERDUE'
    assert by_number[paid_invoice.invoice_number]['effective_status'] == Invoice.Status.PAID
    assert by_number[future_invoice.invoice_number]['effective_status'] == Invoice.Status.ISSUED


def test_get_invoices_status_overdue_returns_only_overdue():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)
    today = timezone.localdate()

    overdue_order = baker.make(Order, customer=customer, created_by=user)
    non_overdue_order = baker.make(Order, customer=customer, created_by=user)

    baker.make(
        Invoice,
        order=overdue_order,
        invoice_number='INV-91001',
        due_date=today - timedelta(days=1),
        status=Invoice.Status.ISSUED,
    )
    baker.make(
        Invoice,
        order=non_overdue_order,
        invoice_number='INV-91002',
        due_date=today + timedelta(days=1),
        status=Invoice.Status.ISSUED,
    )

    response = client.get('/api/invoices/?status=Overdue&page_size=20')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert all(row['effective_status'] == 'OVERDUE' for row in response.data['results'])


def test_product_availability_mapping_for_stock_thresholds():
    out = baker.make(Product, stock_count=0)
    low = baker.make(Product, stock_count=5)
    in_stock = baker.make(Product, stock_count=10)

    assert out.availability == 'Out of Stock'
    assert low.availability == 'Low Stock'
    assert in_stock.availability == 'In Stock'


def test_get_sales_channel_split_percentages_sum_to_100():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.EMAG)
    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.EMAG)
    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.WEBSITE)
    baker.make(Order, customer=customer, created_by=user, channel=Order.Channel.DIRECT)

    response = client.get('/api/sales/channel-split/')

    assert response.status_code == 200
    total_pct = sum(float(item['percentage']) for item in response.data['channels'])
    assert round(total_pct, 2) == 100.0


def test_get_sales_revenue_trend_returns_7_entries_with_current_and_prior_year_values():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    today = timezone.localdate()
    prior_year_today = _prior_year_day(today)

    baker.make(Order, customer=customer, created_by=user, date=today, value_ron=Decimal('75.00'))
    baker.make(Order, customer=customer, created_by=user, date=prior_year_today, value_ron=Decimal('50.00'))

    response = client.get('/api/sales/revenue-trend/')

    assert response.status_code == 200
    assert 'days' in response.data
    assert len(response.data['days']) == 7
    assert all({'date', 'current_year', 'prior_year'}.issubset(entry.keys()) for entry in response.data['days'])

    today_row = next((entry for entry in response.data['days'] if entry['date'] == today.isoformat()), None)
    assert today_row is not None
    assert Decimal(today_row['current_year']) == Decimal('75.00')
    assert Decimal(today_row['prior_year']) == Decimal('50.00')


def test_get_sales_daily_orders_returns_last_7_days_with_counts():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)

    today = timezone.localdate()
    two_days_ago = today - timedelta(days=2)

    baker.make(Order, customer=customer, created_by=user, date=today)
    baker.make(Order, customer=customer, created_by=user, date=today)
    baker.make(Order, customer=customer, created_by=user, date=two_days_ago)
    baker.make(Order, customer=customer, created_by=user, date=today - timedelta(days=10))

    response = client.get('/api/sales/daily-orders/')

    assert response.status_code == 200
    assert 'days' in response.data
    assert len(response.data['days']) == 7

    by_date = {entry['date']: entry['orders_count'] for entry in response.data['days']}
    assert by_date[today.isoformat()] == 2
    assert by_date[two_days_ago.isoformat()] == 1


def test_get_sales_top_products_returns_current_iso_week_ranked_by_units_sold():
    client, user = _authed_sales_client()
    customer = baker.make(Customer)
    product_a = baker.make(Product, name='Alpha Product', sku='ALPHA-001')
    product_b = baker.make(Product, name='Beta Product', sku='BETA-001')

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    previous_week_day = week_start - timedelta(days=1)

    order_today = baker.make(Order, customer=customer, created_by=user, date=today)
    order_week_start = baker.make(Order, customer=customer, created_by=user, date=week_start)
    order_previous_week = baker.make(Order, customer=customer, created_by=user, date=previous_week_day)

    baker.make(OrderItem, order=order_today, product=product_a, quantity=3)
    baker.make(OrderItem, order=order_week_start, product=product_a, quantity=2)
    baker.make(OrderItem, order=order_today, product=product_b, quantity=4)
    baker.make(OrderItem, order=order_previous_week, product=product_a, quantity=99)

    response = client.get('/api/sales/top-products/')

    assert response.status_code == 200
    assert response.data['week_start'] == week_start.isoformat()
    assert response.data['week_end'] == week_end.isoformat()
    assert 'products' in response.data

    products = response.data['products']
    by_sku = {entry['product_sku']: entry for entry in products}

    assert by_sku['ALPHA-001']['units_sold'] == 5
    assert by_sku['BETA-001']['units_sold'] == 4
