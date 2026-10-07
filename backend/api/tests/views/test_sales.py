"""Tests for api/views/sales.py: orders, invoices, customers and sales analytics."""

import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone
from model_bakery import baker

from api.models import Customer, Invoice, Order, OrderItem, Product

# ── Orders ───────────────────────────────────────────────────────────────────


@pytest.fixture
def acme_orders():
    """Three orders: two for Acme SRL (one with two line items), one for Beta SRL."""
    acme = baker.make(Customer, name='Acme SRL')
    beta = baker.make(Customer, name='Beta SRL')
    first = baker.make(
        Order,
        customer=acme,
        value_ron=Decimal('120.50'),
        status=Order.Status.PROCESSING,
        channel=Order.Channel.WEBSITE,
    )
    baker.make(
        Order, customer=beta, value_ron=Decimal('80.00'), status=Order.Status.SHIPPED, channel=Order.Channel.EMAG
    )
    baker.make(
        Order, customer=acme, value_ron=Decimal('40.00'), status=Order.Status.PROCESSING, channel=Order.Channel.DIRECT
    )
    baker.make(OrderItem, order=first, quantity=2, unit_price_ron=Decimal('30.00'))
    baker.make(OrderItem, order=first, quantity=1, unit_price_ron=Decimal('60.50'))
    return first


def test_order_number_is_auto_generated_with_hash_format():
    order = Order.objects.create(customer=baker.make(Customer))
    assert re.search(r'^#\d{4}$', order.order_number)


def test_orders_list_supports_search_status_channel_and_includes_totals(sales_client, acme_orders):
    response = sales_client.get('/api/orders/?search=Acme&status=PROCESSING&channel=WEBSITE')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert Decimal(response.data['total_ron_sum']) == Decimal('120.50')
    row = response.data['results'][0]
    assert 'order_number' in row
    assert row['customer_name'] == 'Acme SRL'
    assert Decimal(row['value_ron']) == Decimal('120.50')
    assert row['status'] == Order.Status.PROCESSING
    assert row['channel'] == Order.Channel.WEBSITE


def test_orders_list_is_paginated_and_includes_total_sum_for_filtered_queryset(ceo_client, acme_orders):
    response = ceo_client.get('/api/orders/?search=SRL&page_size=2')

    assert response.status_code == 200
    assert response.data['total_count'] == 3
    assert Decimal(response.data['total_ron_sum']) == Decimal('240.50')
    assert len(response.data['results']) == 2


def test_get_orders_with_status_processing_filters_correctly(sales_client):
    baker.make(Order, status=Order.Status.PROCESSING)
    baker.make(Order, status=Order.Status.SHIPPED)

    response = sales_client.get('/api/orders/?status=Processing')

    assert response.status_code == 200
    assert [item['status'] for item in response.data['results']] == [Order.Status.PROCESSING]


def test_get_orders_with_channel_emag_filters_correctly(sales_client):
    baker.make(Order, channel=Order.Channel.EMAG)
    baker.make(Order, channel=Order.Channel.WEBSITE)

    response = sales_client.get('/api/orders/?channel=eMAG')

    assert response.status_code == 200
    assert [item['channel'] for item in response.data['results']] == [Order.Channel.EMAG]


def test_order_detail_includes_line_items_for_modal(sales_client, acme_orders):
    response = sales_client.get(f'/api/orders/{acme_orders.id}/')

    assert response.status_code == 200
    assert response.data['order_number'] == acme_orders.order_number
    assert response.data['customer_name'] == 'Acme SRL'
    assert len(response.data['items']) == 2
    assert 'line_total_ron' in response.data['items'][0]


def test_orders_endpoints_forbid_non_sales_roles(hr_client, acme_orders):
    assert hr_client.get('/api/orders/').status_code == 403
    assert hr_client.get(f'/api/orders/{acme_orders.id}/').status_code == 403


def test_post_orders_valid_payload_creates_invoice_via_signal(sales_client):
    payload = {
        'customer': baker.make(Customer).id,
        'value_ron': '123.45',
        'date': timezone.localdate().isoformat(),
        'status': Order.Status.PROCESSING,
        'channel': Order.Channel.EMAG,
        'notes': 'Created from pytest',
    }

    response = sales_client.post('/api/orders/', payload, format='json')

    assert response.status_code == 201
    invoice = Invoice.objects.get(order_id=response.data['id'])
    assert invoice.amount_ron == Decimal('123.45')
    assert invoice.invoice_number.startswith('INV-')


# ── Sales dashboard and analytics ────────────────────────────────────────────


def test_sales_dashboard_kpis_uses_today_yesterday_and_weekly_cancellations(sales_client):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    for amount, day, status in [
        ('120.00', today, Order.Status.PROCESSING),
        ('80.00', today, Order.Status.PROCESSING),
        ('30.00', today, Order.Status.CANCELLED),
        ('100.00', yesterday, Order.Status.DELIVERED),
        ('15.00', yesterday if today.weekday() >= 1 else today, Order.Status.CANCELLED),
        ('22.00', start_of_week - timedelta(days=1), Order.Status.CANCELLED),
    ]:
        baker.make(Order, value_ron=Decimal(amount), date=day, status=status)

    response = sales_client.get('/api/sales/dashboard/')

    today_orders = Order.objects.filter(date=today).count()
    today_revenue = Order.objects.filter(date=today).aggregate(total=Sum('value_ron'))['total'] or Decimal('0')
    yesterday_orders = Order.objects.filter(date=yesterday).count()
    yesterday_revenue = Order.objects.filter(date=yesterday).aggregate(total=Sum('value_ron'))['total'] or Decimal('0')

    def pct_change(today_value, yesterday_value):
        today_numeric, yesterday_numeric = float(today_value or 0), float(yesterday_value or 0)
        if yesterday_numeric == 0:
            return 100.0 if today_numeric > 0 else 0.0
        return round(((today_numeric - yesterday_numeric) / yesterday_numeric) * 100, 2)

    assert response.status_code == 200
    assert response.data['orders_today'] == today_orders
    assert Decimal(response.data['revenue_today_ron']) == today_revenue
    assert response.data['pending_orders'] == Order.objects.filter(status=Order.Status.PROCESSING).count()
    assert (
        response.data['returns_this_week']
        == Order.objects.filter(status=Order.Status.CANCELLED, date__gte=start_of_week, date__lte=today).count()
    )
    assert response.data['pct_changes']['orders'] == pct_change(today_orders, yesterday_orders)
    assert response.data['pct_changes']['revenue'] == pct_change(today_revenue, yesterday_revenue)


def test_sales_dashboard_kpis_allows_ceo(ceo_client):
    assert ceo_client.get('/api/sales/dashboard/').status_code == 200


def test_sales_dashboard_kpis_forbids_other_roles(hr_client):
    assert hr_client.get('/api/sales/dashboard/').status_code == 403


def test_daily_orders_returns_last_seven_days_with_zero_filled_gaps(sales_client):
    today = timezone.localdate()
    five_days_ago = today - timedelta(days=5)
    two_days_ago = today - timedelta(days=2)
    baker.make(Order, date=five_days_ago, _quantity=2)
    baker.make(Order, date=two_days_ago)
    baker.make(Order, date=today - timedelta(days=10))  # outside the window

    response = sales_client.get('/api/sales/daily-orders/')

    assert response.status_code == 200
    assert len(response.data['days']) == 7
    counts = {row['date']: row['orders_count'] for row in response.data['days']}
    assert counts[five_days_ago.isoformat()] == 2
    assert counts[two_days_ago.isoformat()] == 1
    assert counts[today.isoformat()] == 0


def test_top_products_uses_current_iso_week_and_sorts_by_units_sold(ceo_client):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    alpha = baker.make(Product, name='Alpha Product', sku='ALPHA-001')
    beta = baker.make(Product, name='Beta Product', sku='BETA-001')
    baker.make(OrderItem, order=baker.make(Order, date=today), product=alpha, quantity=3)
    baker.make(OrderItem, order=baker.make(Order, date=week_start), product=alpha, quantity=2)
    baker.make(OrderItem, order=baker.make(Order, date=today), product=beta, quantity=4)
    baker.make(OrderItem, order=baker.make(Order, date=week_start - timedelta(days=1)), product=beta, quantity=99)

    response = ceo_client.get('/api/sales/top-products/')

    assert response.status_code == 200
    assert response.data['week_start'] == week_start.isoformat()
    assert response.data['week_end'] == (week_start + timedelta(days=6)).isoformat()
    assert [(p['product_sku'], p['units_sold']) for p in response.data['products']] == [
        ('ALPHA-001', 5),
        ('BETA-001', 4),
    ]


def test_analytics_endpoints_forbid_non_sales_roles(hr_client):
    assert hr_client.get('/api/sales/daily-orders/').status_code == 403
    assert hr_client.get('/api/sales/top-products/').status_code == 403


def test_get_sales_channel_split_percentages_sum_to_100(sales_client):
    for channel in [Order.Channel.EMAG, Order.Channel.EMAG, Order.Channel.WEBSITE, Order.Channel.DIRECT]:
        baker.make(Order, channel=channel)

    response = sales_client.get('/api/sales/channel-split/')

    assert response.status_code == 200
    assert round(sum(float(item['percentage']) for item in response.data['channels']), 2) == 100.0


def test_get_sales_revenue_trend_returns_7_entries_with_current_and_prior_year_values(sales_client):
    today = timezone.localdate()
    try:
        prior_year_today = today.replace(year=today.year - 1)
    except ValueError:  # 29 February
        prior_year_today = today - timedelta(days=365)
    baker.make(Order, date=today, value_ron=Decimal('75.00'))
    baker.make(Order, date=prior_year_today, value_ron=Decimal('50.00'))

    response = sales_client.get('/api/sales/revenue-trend/')

    assert response.status_code == 200
    assert len(response.data['days']) == 7
    assert all({'date', 'current_year', 'prior_year'} <= entry.keys() for entry in response.data['days'])
    today_row = next(entry for entry in response.data['days'] if entry['date'] == today.isoformat())
    assert Decimal(today_row['current_year']) == Decimal('75.00')
    assert Decimal(today_row['prior_year']) == Decimal('50.00')


# ── Invoices ─────────────────────────────────────────────────────────────────


@pytest.fixture
def three_invoices():
    """One paid (100), one overdue (200) and one pending (300) invoice, created by the order signal."""
    today = timezone.localdate()
    for amount, status, due_date in [
        ('100.00', Invoice.Status.PAID, None),
        ('200.00', Invoice.Status.ISSUED, today - timedelta(days=1)),
        ('300.00', Invoice.Status.ISSUED, today + timedelta(days=7)),
    ]:
        order = baker.make(Order, value_ron=Decimal(amount))
        fields = {'status': status, 'amount_ron': Decimal(amount)}
        if due_date:
            fields['due_date'] = due_date
        Invoice.objects.filter(order=order).update(**fields)


def test_get_invoices_returns_summary_totals(sales_client, three_invoices):
    response = sales_client.get('/api/invoices/')

    assert response.status_code == 200
    assert Decimal(response.data['paid_total']) == Decimal('100.00')
    assert Decimal(response.data['overdue_total']) == Decimal('200.00')
    assert Decimal(response.data['pending_total']) == Decimal('300.00')


def test_get_invoices_summary_totals_unaffected_by_status_filter(sales_client, three_invoices):
    response = sales_client.get('/api/invoices/?status=Paid')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert Decimal(response.data['paid_total']) == Decimal('100.00')
    assert Decimal(response.data['overdue_total']) == Decimal('200.00')


def test_get_invoices_forbids_non_sales_roles(hr_client):
    assert hr_client.get('/api/invoices/').status_code == 403


def test_get_invoices_computes_overdue_status_correctly(sales_client):
    today = timezone.localdate()
    overdue = baker.make(Invoice, due_date=today - timedelta(days=1), status=Invoice.Status.ISSUED)
    paid = baker.make(Invoice, due_date=today - timedelta(days=2), status=Invoice.Status.PAID)
    upcoming = baker.make(Invoice, due_date=today + timedelta(days=2), status=Invoice.Status.ISSUED)

    response = sales_client.get('/api/invoices/?page_size=20')

    assert response.status_code == 200
    effective = {row['invoice_number']: row['effective_status'] for row in response.data['results']}
    assert effective[overdue.invoice_number] == 'OVERDUE'
    assert effective[paid.invoice_number] == Invoice.Status.PAID
    assert effective[upcoming.invoice_number] == Invoice.Status.ISSUED


def test_get_invoices_status_overdue_returns_only_overdue(sales_client):
    today = timezone.localdate()
    baker.make(Invoice, due_date=today - timedelta(days=1), status=Invoice.Status.ISSUED)
    baker.make(Invoice, due_date=today + timedelta(days=1), status=Invoice.Status.ISSUED)

    response = sales_client.get('/api/invoices/?status=Overdue&page_size=20')

    assert response.status_code == 200
    assert [row['effective_status'] for row in response.data['results']] == ['OVERDUE']


# ── Customers ────────────────────────────────────────────────────────────────


def test_customer_list_returns_orders_count_and_tier(sales_client):
    alpha = baker.make(Customer, name='Alpha Corp', tier=Customer.Tier.GOLD)
    baker.make(Order, customer=alpha, _quantity=2)
    baker.make(Order, customer=baker.make(Customer, tier=Customer.Tier.SILVER))

    response = sales_client.get('/api/customers/')

    assert response.status_code == 200
    row = next(r for r in response.data['results'] if r['name'] == 'Alpha Corp')
    assert row['orders_count'] == 2
    assert row['tier'] == Customer.Tier.GOLD


def test_get_customers_sorted_by_total_value_desc_with_annotation(sales_client):
    alpha = baker.make(Customer, name='Alpha')
    beta = baker.make(Customer, name='Beta')
    baker.make(Order, customer=alpha, value_ron=Decimal('100.00'))
    baker.make(Order, customer=alpha, value_ron=Decimal('50.00'))
    baker.make(Order, customer=beta, value_ron=Decimal('40.00'))

    response = sales_client.get('/api/customers/')

    assert response.status_code == 200
    assert [(r['name'], Decimal(r['total_value_ron'])) for r in response.data['results']] == [
        ('Alpha', Decimal('150.00')),
        ('Beta', Decimal('40.00')),
    ]


def test_customer_list_forbids_non_sales_role(hr_client):
    assert hr_client.get('/api/customers/').status_code == 403


def test_customer_detail_returns_order_history(sales_client):
    customer = baker.make(Customer, name='Detail Corp', contact_name='Jane Doe', tier=Customer.Tier.BRONZE)
    order = baker.make(Order, customer=customer)

    response = sales_client.get(f'/api/customers/{customer.id}/')

    assert response.status_code == 200
    assert response.data['name'] == 'Detail Corp'
    assert response.data['contact_name'] == 'Jane Doe'
    assert response.data['tier'] == Customer.Tier.BRONZE
    assert [o['order_number'] for o in response.data['orders']] == [order.order_number]


def test_customer_detail_returns_404_for_missing_id(sales_client):
    assert sales_client.get('/api/customers/99999/').status_code == 404


def test_customer_detail_forbids_non_sales_role(hr_client):
    customer = baker.make(Customer)
    assert hr_client.get(f'/api/customers/{customer.id}/').status_code == 403


# ── Products ─────────────────────────────────────────────────────────────────


def test_product_availability_mapping_for_stock_thresholds():
    assert baker.make(Product, stock_count=0).availability == 'Out of Stock'
    assert baker.make(Product, stock_count=5).availability == 'Low Stock'
    assert baker.make(Product, stock_count=10).availability == 'In Stock'
