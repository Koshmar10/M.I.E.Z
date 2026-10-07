"""Tests for api/views/legacy.py."""

from django.test import Client, TestCase


class IsEvenTests(TestCase):
    def setUp(self):
        self.client = Client()

    # ── Success cases ──────────────────────────────────────────

    def test_even_number(self):
        response = self.client.get('/api/is_even/', {'number': 4})
        assert response.status_code == 200
        assert response.json()['even'] == True

    def test_odd_number(self):
        response = self.client.get('/api/is_even/', {'number': 3})
        assert response.status_code == 200
        assert response.json()['even'] == False

    def test_zero(self):
        response = self.client.get('/api/is_even/', {'number': 0})
        assert response.status_code == 200
        assert response.json()['even'] == True

    def test_negative_even(self):
        response = self.client.get('/api/is_even/', {'number': -2})
        assert response.status_code == 200
        assert response.json()['even'] == True

    def test_negative_odd(self):
        response = self.client.get('/api/is_even/', {'number': -7})
        assert response.status_code == 200
        assert response.json()['even'] == False

    # ── Fail cases ─────────────────────────────────────────────

    def test_missing_number(self):
        response = self.client.get('/api/is_even/')
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_string_input(self):
        response = self.client.get('/api/is_even/', {'number': 'abc'})
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_float_string(self):
        response = self.client.get('/api/is_even/', {'number': '2.5'})
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_post_not_allowed(self):
        response = self.client.post('/api/is_even/', {'number': 2})
        assert response.status_code == 405  # method not allowed
