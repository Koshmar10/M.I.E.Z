from django.test import TestCase, Client

class IsEvenTests(TestCase):
    def setUp(self):
        self.client = Client()

    # ── Success cases ──────────────────────────────────────────

    def test_even_number(self):
        response = self.client.get('/api/is_even/', {'number': 4})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['even'], True)

    def test_odd_number(self):
        response = self.client.get('/api/is_even/', {'number': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['even'], False)

    def test_zero(self):
        response = self.client.get('/api/is_even/', {'number': 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['even'], True)

    def test_negative_even(self):
        response = self.client.get('/api/is_even/', {'number': -2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['even'], True)

    def test_negative_odd(self):
        response = self.client.get('/api/is_even/', {'number': -7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['even'], False)

    # ── Fail cases ─────────────────────────────────────────────

    def test_missing_number(self):
        response = self.client.get('/api/is_even/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_string_input(self):
        response = self.client.get('/api/is_even/', {'number': 'abc'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_float_string(self):
        response = self.client.get('/api/is_even/', {'number': '2.5'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_post_not_allowed(self):
        response = self.client.post('/api/is_even/', {'number': 2})
        self.assertEqual(response.status_code, 405)  # method not allowed