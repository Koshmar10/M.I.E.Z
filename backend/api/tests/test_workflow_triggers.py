"""Tests that events (new orders, new tickets, stock movements) fire workflows."""

from model_bakery import baker

from api.models import Order, Product, StockMovement, Ticket, Workflow, WorkflowLog


def test_new_order_triggers_workflow():
    baker.make(Workflow, trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'])

    baker.make(Order)

    log = WorkflowLog.objects.get()
    assert log.trigger_type == 'NEW_ORDER_RECEIVED'
    assert log.success


def test_inactive_workflow_not_triggered_on_new_order():
    baker.make(Workflow, trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'], is_active=False)

    baker.make(Order)

    assert WorkflowLog.objects.count() == 0


def test_new_order_above_threshold_triggers_workflow():
    baker.make(
        Workflow, trigger_type='ORDER_EXCEEDS_THRESHOLD', trigger_config={'threshold': 1000}, actions=['EMAIL_CEO']
    )

    baker.make(Order, value_ron=500)
    assert WorkflowLog.objects.count() == 0

    baker.make(Order, value_ron=2000)
    assert WorkflowLog.objects.get().trigger_type == 'ORDER_EXCEEDS_THRESHOLD'


def test_new_it_ticket_triggers_workflow(sales_user):
    baker.make(Workflow, trigger_type='NEW_IT_TICKET', actions=['ASSIGN_TO_TEAM_LEAD'])

    baker.make(Ticket, requested_by=sales_user)

    assert WorkflowLog.objects.get().trigger_type == 'NEW_IT_TICKET'


def test_stock_below_minimum_triggers_workflow():
    baker.make(Workflow, trigger_type='STOCK_BELOW_MINIMUM', actions=['EMAIL_SUPPLIER'])
    product = baker.make(Product, stock_count=15, min_stock=10)

    # 15 - 8 leaves 7, below the minimum of 10
    baker.make(StockMovement, product=product, movement_type='OUTBOUND', quantity=8)

    assert WorkflowLog.objects.get().trigger_type == 'STOCK_BELOW_MINIMUM'


def test_stock_above_minimum_does_not_trigger():
    baker.make(Workflow, trigger_type='STOCK_BELOW_MINIMUM', actions=['EMAIL_SUPPLIER'])
    product = baker.make(Product, stock_count=15, min_stock=10)

    # 15 - 3 leaves 12, still above the minimum of 10
    baker.make(StockMovement, product=product, movement_type='OUTBOUND', quantity=3)

    assert WorkflowLog.objects.count() == 0


def test_multiple_workflows_all_triggered():
    baker.make(Workflow, trigger_type='NEW_ORDER_RECEIVED', actions=['NOTIFY_MANAGER'])
    baker.make(Workflow, trigger_type='NEW_ORDER_RECEIVED', actions=['EMAIL_CEO'])

    baker.make(Order)

    assert WorkflowLog.objects.count() == 2
