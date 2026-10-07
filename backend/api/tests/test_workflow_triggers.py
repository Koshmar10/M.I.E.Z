"""Tests that events (signals, stock movements) fire workflows."""

from django.test import TestCase

from api.models import WorkflowLog
from api.tests.factories import (
    make_customer,
    make_order,
    make_product,
    make_sales_user,
    make_stock_movement,
    make_ticket,
    make_workflow,
)


class EventTriggerTests(TestCase):
    """Verify Django signals fire the workflow engine for event-based triggers."""

    def test_new_order_triggers_workflow(self):
        make_workflow(name='Order Alert', trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'])
        customer = make_customer()
        self.assertEqual(WorkflowLog.objects.count(), 0)
        make_order(customer)
        self.assertEqual(WorkflowLog.objects.count(), 1)
        log = WorkflowLog.objects.first()
        self.assertEqual(log.trigger_type, 'NEW_ORDER_RECEIVED')
        self.assertTrue(log.success)

    def test_inactive_workflow_not_triggered_on_new_order(self):
        make_workflow(
            name='Inactive Order', trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'], is_active=False
        )
        make_order(make_customer())
        self.assertEqual(WorkflowLog.objects.count(), 0)

    def test_new_order_above_threshold_triggers_workflow(self):
        make_workflow(
            name='High Value Alert',
            trigger_type='ORDER_EXCEEDS_THRESHOLD',
            trigger_config={'threshold': 1000},
            actions=['EMAIL_CEO'],
        )
        customer = make_customer()
        # Below threshold — should not trigger
        make_order(customer, value_ron=500)
        self.assertEqual(WorkflowLog.objects.count(), 0)
        # Above threshold — should trigger
        make_order(customer, value_ron=2000)
        self.assertEqual(WorkflowLog.objects.count(), 1)
        self.assertEqual(WorkflowLog.objects.first().trigger_type, 'ORDER_EXCEEDS_THRESHOLD')

    def test_new_it_ticket_triggers_workflow(self):
        make_workflow(name='Ticket Alert', trigger_type='NEW_IT_TICKET', actions=['ASSIGN_TO_TEAM_LEAD'])
        user = make_sales_user()
        self.assertEqual(WorkflowLog.objects.count(), 0)
        make_ticket(user)
        self.assertEqual(WorkflowLog.objects.count(), 1)
        log = WorkflowLog.objects.first()
        self.assertEqual(log.trigger_type, 'NEW_IT_TICKET')

    def test_stock_below_minimum_triggers_workflow(self):
        make_workflow(name='Low Stock Alert', trigger_type='STOCK_BELOW_MINIMUM', actions=['EMAIL_SUPPLIER'])
        product = make_product(stock_count=15, min_stock=10)
        # OUTBOUND of 8 leaves stock_count=7, which is < min_stock=10
        make_stock_movement(product, qty=8, movement_type='OUTBOUND')
        self.assertEqual(WorkflowLog.objects.count(), 1)
        log = WorkflowLog.objects.first()
        self.assertEqual(log.trigger_type, 'STOCK_BELOW_MINIMUM')

    def test_stock_above_minimum_does_not_trigger(self):
        make_workflow(name='Low Stock Alert 2', trigger_type='STOCK_BELOW_MINIMUM', actions=['EMAIL_SUPPLIER'])
        product = make_product(stock_count=15, min_stock=10)
        # OUTBOUND of 3 leaves stock_count=12, still above min_stock=10
        make_stock_movement(product, qty=3, movement_type='OUTBOUND')
        self.assertEqual(WorkflowLog.objects.count(), 0)

    def test_multiple_workflows_all_triggered(self):
        make_workflow(name='Alert A', trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'])
        make_workflow(name='Alert B', trigger_type='NEW_ORDER_RECEIVED', actions=['EMAIL_CEO'])
        make_order(make_customer())
        self.assertEqual(WorkflowLog.objects.count(), 2)
