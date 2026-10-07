"""Tests for api/models/."""

from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from api.models import (
    Attendance,
    Contract,
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
    SystemStatistic,
    Ticket,
    TicketComment,
    Workflow,
    WorkflowLog,
)

User = get_user_model()


class ERPModelsTestCase(TestCase):
    def setUp(self):
        self.ceo = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='password',
            role=User.Role.CEO,
        )
        self.it_user = User.objects.create_user(
            username='it.user',
            email='it@example.com',
            password='password',
            role=User.Role.IT,
        )
        self.sales_user = User.objects.create_user(
            username='sales.user',
            email='sales@example.com',
            password='password',
            role=User.Role.SALES,
        )
        self.hr_department = Department.objects.create(name='Human Resources', slug='hr', icon='Users')

    def test_customer_create(self):
        customer = Customer.objects.create(name='Acme SRL', contact_email='client@acme.ro')
        self.assertEqual(str(customer), 'Acme SRL')

    def test_product_unique_sku(self):
        Product.objects.create(name='Widget', sku='W-001')
        with self.assertRaises(IntegrityError):
            Product.objects.create(name='Widget 2', sku='W-001')

    def test_order_and_items(self):
        customer = Customer.objects.create(name='Acme SRL')
        product = Product.objects.create(name='Widget', sku='W-001', unit_price_ron=10, stock_count=5)

        order = Order.objects.create(
            order_number='ORD-1',
            customer=customer,
            created_by=self.sales_user,
            status=Order.Status.PROCESSING,
        )
        self.assertEqual(str(order), 'ORD-1')

        OrderItem.objects.create(order=order, product=product, quantity=2, unit_price_ron=10)
        self.assertEqual(order.items.count(), 1)

        # unique_together(order, product)
        with self.assertRaises(IntegrityError):
            OrderItem.objects.create(order=order, product=product, quantity=1, unit_price_ron=10)

    def test_invoice_create(self):
        customer = Customer.objects.create(name='Acme SRL')
        order = Order.objects.create(order_number='ORD-2', customer=customer, created_by=self.sales_user)
        invoice = Invoice.objects.create(
            invoice_number='INV-1',
            order=order,
            issued_by=self.sales_user,
            amount_ron=99.99,
        )
        self.assertEqual(invoice.order, order)

    def test_attendance_unique_per_user_per_day(self):
        Attendance.objects.create(employee=self.it_user, date=date(2026, 1, 1), status=Attendance.Status.PRESENT)
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(employee=self.it_user, date=date(2026, 1, 1), status=Attendance.Status.ABSENT)

    def test_leave_request_relations(self):
        leave = LeaveRequest.objects.create(
            employee=self.it_user,
            department=self.hr_department,
            type=LeaveRequest.Type.VACATION,
            from_date=date(2026, 1, 10),
            to_date=date(2026, 1, 12),
            status=LeaveRequest.Status.PENDING,
        )
        self.assertEqual(leave.employee, self.it_user)
        self.assertEqual(leave.department, self.hr_department)

    def test_contract_create(self):
        contract = Contract.objects.create(
            contract_number='CTR-1',
            employee=self.it_user,
            department=self.hr_department,
            type=Contract.Type.EMPLOYMENT,
            start_date=date(2026, 1, 1),
            salary_ron=5000,
        )
        self.assertEqual(contract.employee, self.it_user)

    def test_payroll_entry_unique_per_month(self):
        PayrollEntry.objects.create(
            employee=self.sales_user,
            month=date(2026, 1, 1),
            gross_salary_ron=1000,
            net_salary_ron=800,
        )
        with self.assertRaises(IntegrityError):
            PayrollEntry.objects.create(
                employee=self.sales_user,
                month=date(2026, 1, 1),
                gross_salary_ron=1000,
                net_salary_ron=800,
            )

    def test_notification_create(self):
        notification = Notification.objects.create(recipient=self.ceo, title='Hello', body='World')
        self.assertEqual(notification.recipient, self.ceo)
        self.assertFalse(notification.is_read)

    def test_ticket_and_comment(self):
        ticket = Ticket.objects.create(
            ticket_number='T-1',
            title='Printer broken',
            requested_by=self.ceo,
            assigned_to=self.it_user,
            priority=Ticket.Priority.HIGH,
            status=Ticket.Status.OPEN,
        )
        self.assertEqual(ticket.comments.count(), 0)
        TicketComment.objects.create(ticket=ticket, author=self.it_user, body='On it')
        self.assertEqual(ticket.comments.count(), 1)

    def test_workflow_and_log(self):
        workflow = Workflow.objects.create(name='Auto-assign IT tickets', trigger_type='NEW_IT_TICKET')
        WorkflowLog.objects.create(
            workflow=workflow,
            trigger_type='NEW_IT_TICKET',
            actions_log=[{'action': 'NOTIFY_MANAGER', 'success': True, 'message': 'ok'}],
            success=True,
        )
        self.assertEqual(workflow.logs.count(), 1)

    def test_system_statistic_unique_name(self):
        SystemStatistic.objects.create(name='open_tickets', value={'count': 3})
        with self.assertRaises(IntegrityError):
            SystemStatistic.objects.create(name='open_tickets', value={'count': 4})

    def test_report_create(self):
        report = Report.objects.create(
            name='Weekly sales',
            category='sales',
            period='2026-W01',
            file_path='/tmp/report.csv',
            generated_by=self.ceo,
        )
        self.assertEqual(report.generated_by, self.ceo)
