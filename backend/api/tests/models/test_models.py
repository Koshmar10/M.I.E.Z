"""Tests for api/models/."""

from datetime import date

import pytest
from django.db import IntegrityError
from model_bakery import baker

from api.models import (
    Attendance,
    Customer,
    Notification,
    Order,
    OrderItem,
    PayrollEntry,
    Product,
    SystemStatistic,
    Ticket,
    TicketComment,
    Workflow,
    WorkflowLog,
)


def test_customer_str_is_its_name():
    assert str(baker.make(Customer, name='Acme SRL')) == 'Acme SRL'


def test_product_unique_sku():
    baker.make(Product, sku='W-001')
    with pytest.raises(IntegrityError):
        baker.make(Product, sku='W-001')


def test_product_availability_for_stock_thresholds():
    assert Product(stock_count=0, min_stock=10).availability == 'Out of Stock'
    assert Product(stock_count=5, min_stock=10).availability == 'Low Stock'
    assert Product(stock_count=10, min_stock=10).availability == 'In Stock'


def test_order_and_items():
    order = baker.make(Order, order_number='ORD-1')
    product = baker.make(Product)
    assert str(order) == 'ORD-1'

    baker.make(OrderItem, order=order, product=product)
    assert order.items.count() == 1

    # unique_together(order, product)
    with pytest.raises(IntegrityError):
        baker.make(OrderItem, order=order, product=product)


def test_attendance_unique_per_user_per_day(it_user):
    baker.make(Attendance, employee=it_user, date=date(2026, 1, 1), status=Attendance.Status.PRESENT)
    with pytest.raises(IntegrityError):
        baker.make(Attendance, employee=it_user, date=date(2026, 1, 1), status=Attendance.Status.ABSENT)


def test_payroll_entry_unique_per_month(sales_user):
    baker.make(PayrollEntry, employee=sales_user, month=date(2026, 1, 1))
    with pytest.raises(IntegrityError):
        baker.make(PayrollEntry, employee=sales_user, month=date(2026, 1, 1))


def test_notification_is_unread_by_default(ceo_user):
    assert not baker.make(Notification, recipient=ceo_user).is_read


def test_ticket_and_comment():
    ticket = baker.make(Ticket)
    assert ticket.comments.count() == 0
    baker.make(TicketComment, ticket=ticket)
    assert ticket.comments.count() == 1


def test_workflow_and_log():
    workflow = baker.make(Workflow)
    baker.make(WorkflowLog, workflow=workflow)
    assert workflow.logs.count() == 1


def test_system_statistic_unique_name():
    baker.make(SystemStatistic, name='open_tickets')
    with pytest.raises(IntegrityError):
        baker.make(SystemStatistic, name='open_tickets')
