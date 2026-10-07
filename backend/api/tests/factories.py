"""Small helpers that create users, workflows and business objects for tests."""

from api.models import Customer, Order, Product, StockMovement, Ticket, User, Workflow


def make_ceo(**kw):
    name = kw.get('username', 'ceo')
    return User.objects.create_user(username=name, email=f'{name}@test.com', password='pass', role='CEO')


def make_hr(**kw):
    name = kw.get('username', 'hr')
    return User.objects.create_user(username=name, email=f'{name}@test.com', password='pass', role='HR')


def make_it(**kw):
    name = kw.get('username', 'it')
    return User.objects.create_user(username=name, email=f'{name}@test.com', password='pass', role='IT')


def make_workflow(**kw):
    return Workflow.objects.create(
        name=kw.get('name', 'Test Workflow'),
        trigger_type=kw.get('trigger_type', 'DAILY_AT_TIME'),
        trigger_config=kw.get('trigger_config', {'time': '08:00'}),
        actions=kw.get('actions', ['NOTIFY_MANAGER']),
        is_active=kw.get('is_active', True),
    )


def make_customer():
    return Customer.objects.create(name='Test Customer')


def make_sales_user():
    name = 'sales_trig'
    return User.objects.create_user(username=name, email=f'{name}@test.com', password='pass', role='SALES')


def make_order(customer, created_by=None, value_ron=500):
    return Order.objects.create(customer=customer, created_by=created_by, value_ron=value_ron)


def make_ticket(requested_by):
    return Ticket.objects.create(
        ticket_number=Ticket._generate_ticket_number(),
        title='Test issue',
        requested_by=requested_by,
    )


def make_product(stock_count=20, min_stock=10):
    return Product.objects.create(
        name='Widget',
        sku=f'SKU-{Product.objects.count()}',
        stock_count=stock_count,
        min_stock=min_stock,
    )


def make_stock_movement(product, qty, movement_type='OUTBOUND'):
    return StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=qty,
    )
