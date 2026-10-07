"""Tests for api/views/inventory.py."""

from datetime import date

from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Product, StockMovement, User


class InventoryBackendTests(APITestCase):
    """Tests for Inventory module: product list, status filtering, and stock movements."""

    def setUp(self):
        self.inventory_manager = baker.make(
            User, role=User.Role.INVENTORY, username='inv_manager', email='inv_manager@example.com'
        )
        self.ceo_user = baker.make(User, role=User.Role.CEO, username='ceo_inv', email='ceo_inv@example.com')
        self.products_url = reverse('inventory_products')
        self.dashboard_url = reverse('inventory_dashboard_kpis')
        self.movements_url = reverse('stock_movements')

    def test_get_products_returns_paginated_list_with_expected_fields(self):
        # We test for 5 since there is no pagination currently
        baker.make(Product, _quantity=5)
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get(self.products_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 5)

        first = response.data[0]
        expected_keys = {
            'id',
            'name',
            'sku',
            'category',
            'stock_count',
            'min_stock',
            'unit_price_ron',
            'status',
            'shortfall',
        }
        self.assertTrue(expected_keys.issubset(first.keys()))

    def test_get_products_with_low_status_filter_returns_only_low_stock_items(self):
        # min_stock defaults to 10. Stock < 10 is LOW.
        baker.make(Product, stock_count=5, min_stock=10, name='Low Item')
        baker.make(Product, stock_count=15, min_stock=10, name='Healthy Item')

        self.client.force_authenticate(user=self.ceo_user)
        response = self.client.get(self.products_url, {'status': 'LOW'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Low Item')
        self.assertEqual(response.data[0]['status'], 'LOW')

    def test_get_products_with_out_status_filter_returns_only_depleted_items(self):
        baker.make(Product, stock_count=0, min_stock=10, name='Out Item')
        baker.make(Product, stock_count=1, min_stock=10, name='Low Item')

        self.client.force_authenticate(user=self.ceo_user)
        response = self.client.get(self.products_url, {'status': 'OUT'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data, list))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Out Item')
        self.assertEqual(response.data[0]['status'], 'OUT')

    def test_product_availability_property_logic(self):
        """Verify the model @property for human readable status."""
        p_out = Product(stock_count=0, min_stock=10)
        self.assertEqual(p_out.availability, 'Out of Stock')

        p_low = Product(stock_count=5, min_stock=10)
        self.assertEqual(p_low.availability, 'Low Stock')

        p_ok = Product(stock_count=10, min_stock=10)
        self.assertEqual(p_ok.availability, 'In Stock')

    def test_get_inventory_dashboard_returns_correct_kpi_aggregates(self):
        p1 = baker.make(Product, stock_count=0, min_stock=10)  # 1 OUT
        baker.make(Product, stock_count=3, min_stock=10)  # 1 LOW
        baker.make(Product, stock_count=20, min_stock=10)  # 1 OK

        # Delivery today, bind to p1 so we don't accidentally create a 4th product
        baker.make(StockMovement, product=p1, movement_type=StockMovement.Type.INBOUND, expected_date=date.today())

        self.client.force_authenticate(user=self.ceo_user)
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_products'], 3)
        self.assertEqual(response.data['low_stock_count'], 1)
        self.assertEqual(response.data['out_of_stock_count'], 1)
        self.assertEqual(response.data['deliveries_today'], 1)

    def test_post_stock_movement_inbound_increments_product_stock(self):
        product = baker.make(Product, stock_count=10)
        self.client.force_authenticate(user=self.inventory_manager)

        payload = {'product': product.id, 'movement_type': 'INBOUND', 'quantity': 20, 'notes': 'Large delivery'}
        response = self.client.post(self.movements_url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        product.refresh_from_db()
        self.assertEqual(product.stock_count, 30)

    def test_post_stock_movement_write_off_decrements_product_stock_down_to_zero(self):
        product = baker.make(Product, stock_count=10)
        self.client.force_authenticate(user=self.inventory_manager)

        # Test partial decrement
        self.client.post(
            self.movements_url,
            {'product': product.id, 'movement_type': 'WRITE_OFF', 'quantity': 4, 'notes': 'partial'},
            format='json',
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_count, 6)

        # Test decrement beyond zero
        self.client.post(
            self.movements_url,
            {'product': product.id, 'movement_type': 'WRITE_OFF', 'quantity': 100, 'notes': 'full'},
            format='json',
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_count, 0)

    def test_post_stock_movement_adjustment_sets_stock_exactly(self):
        product = baker.make(Product, stock_count=10)
        self.client.force_authenticate(user=self.inventory_manager)

        payload = {'product': product.id, 'movement_type': 'ADJUSTMENT', 'quantity': 55, 'notes': 'adjustment'}
        response = self.client.post(self.movements_url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        product.refresh_from_db()
        self.assertEqual(product.stock_count, 55)

    def test_post_stock_movement_with_zero_quantity_returns_400(self):
        product = baker.make(Product, stock_count=10)
        self.client.force_authenticate(user=self.inventory_manager)

        payload = {'product': product.id, 'movement_type': 'INBOUND', 'quantity': 0}
        response = self.client.post(self.movements_url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('quantity', response.data['field_errors'])
