"""Tests for api/views/inventory.py."""

from datetime import date

from model_bakery import baker

from api.models import Product, StockMovement


def test_get_products_returns_list_with_expected_fields(ceo_client):
    baker.make(Product, _quantity=5)

    response = ceo_client.get('/api/inventory/products/')

    assert response.status_code == 200
    assert len(response.data) == 5
    assert {
        'id',
        'name',
        'sku',
        'category',
        'stock_count',
        'min_stock',
        'unit_price_ron',
        'status',
        'shortfall',
    } <= response.data[0].keys()


def test_get_products_with_low_status_filter_returns_only_low_stock_items(ceo_client):
    baker.make(Product, stock_count=5, min_stock=10, name='Low Item')
    baker.make(Product, stock_count=15, min_stock=10, name='Healthy Item')

    response = ceo_client.get('/api/inventory/products/', {'status': 'LOW'})

    assert response.status_code == 200
    assert [(p['name'], p['status']) for p in response.data] == [('Low Item', 'LOW')]


def test_get_products_with_out_status_filter_returns_only_depleted_items(ceo_client):
    baker.make(Product, stock_count=0, min_stock=10, name='Out Item')
    baker.make(Product, stock_count=1, min_stock=10, name='Low Item')

    response = ceo_client.get('/api/inventory/products/', {'status': 'OUT'})

    assert response.status_code == 200
    assert [(p['name'], p['status']) for p in response.data] == [('Out Item', 'OUT')]


def test_get_inventory_dashboard_returns_correct_kpi_aggregates(ceo_client):
    out_of_stock = baker.make(Product, stock_count=0, min_stock=10)
    baker.make(Product, stock_count=3, min_stock=10)  # low
    baker.make(Product, stock_count=20, min_stock=10)  # ok
    baker.make(
        StockMovement, product=out_of_stock, movement_type=StockMovement.Type.INBOUND, expected_date=date.today()
    )

    response = ceo_client.get('/api/inventory/dashboard/')

    assert response.status_code == 200
    assert response.data['total_products'] == 3
    assert response.data['low_stock_count'] == 1
    assert response.data['out_of_stock_count'] == 1
    assert response.data['deliveries_today'] == 1


def test_post_stock_movement_inbound_increments_product_stock(inventory_client):
    product = baker.make(Product, stock_count=10)

    response = inventory_client.post(
        '/api/inventory/stock-movements/',
        {'product': product.id, 'movement_type': 'INBOUND', 'quantity': 20, 'notes': 'Large delivery'},
        format='json',
    )

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.stock_count == 30


def test_post_stock_movement_write_off_decrements_product_stock_down_to_zero(inventory_client):
    product = baker.make(Product, stock_count=10)

    inventory_client.post(
        '/api/inventory/stock-movements/',
        {'product': product.id, 'movement_type': 'WRITE_OFF', 'quantity': 4, 'notes': 'partial'},
        format='json',
    )
    product.refresh_from_db()
    assert product.stock_count == 6

    inventory_client.post(
        '/api/inventory/stock-movements/',
        {'product': product.id, 'movement_type': 'WRITE_OFF', 'quantity': 100, 'notes': 'full'},
        format='json',
    )
    product.refresh_from_db()
    assert product.stock_count == 0


def test_post_stock_movement_adjustment_sets_stock_exactly(inventory_client):
    product = baker.make(Product, stock_count=10)

    response = inventory_client.post(
        '/api/inventory/stock-movements/',
        {'product': product.id, 'movement_type': 'ADJUSTMENT', 'quantity': 55, 'notes': 'adjustment'},
        format='json',
    )

    assert response.status_code == 201
    product.refresh_from_db()
    assert product.stock_count == 55


def test_post_stock_movement_with_zero_quantity_returns_400(inventory_client):
    product = baker.make(Product, stock_count=10)

    response = inventory_client.post(
        '/api/inventory/stock-movements/',
        {'product': product.id, 'movement_type': 'INBOUND', 'quantity': 0},
        format='json',
    )

    assert response.status_code == 400
    assert 'quantity' in response.data['field_errors']
