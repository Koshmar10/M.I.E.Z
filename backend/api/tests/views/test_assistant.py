"""Tests for api/views/assistant.py: the assistant chat endpoint."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.agent.runner import AgentRunner
from api.models import User


class AssistantChatEndpointTests(TestCase):
    """Test suite for the /api/assistant/chat/ endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.endpoint = '/api/assistant/chat/'

        self.anthropic_patch = patch.object(
            AgentRunner,
            '_call_anthropic',
            return_value={'response': 'mocked anthropic response', 'tool_calls_made': []},
        )
        self.mock_anthropic = self.anthropic_patch.start()

        # Create test users with different roles
        self.ceo_user = User.objects.create_user(
            username='ceo_user',
            email='ceo@miez.com',
            password='testpass123',
            role=User.Role.CEO,
        )

        self.hr_user = User.objects.create_user(
            username='hr_user',
            email='hr@miez.com',
            password='testpass123',
            role=User.Role.HR,
        )

        self.sales_user = User.objects.create_user(
            username='sales_user',
            email='sales@miez.com',
            password='testpass123',
            role=User.Role.SALES,
        )

        self.it_user = User.objects.create_user(
            username='it_user',
            email='it@miez.com',
            password='testpass123',
            role=User.Role.IT,
        )

        self.inventory_user = User.objects.create_user(
            username='inventory_user',
            email='inventory@miez.com',
            password='testpass123',
            role=User.Role.INVENTORY,
        )

        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        self.anthropic_patch.stop()

    def test_requires_authentication(self):
        """Test that endpoint requires authentication."""
        response = self.client.post(self.endpoint, {'message': 'Hello'}, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_chat_request(self):
        """Test successful chat request."""
        self.client.force_authenticate(user=self.ceo_user)

        payload = {
            'message': 'What is the sales status?',
            'history': [
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi there!'},
            ],
        }

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'response' in response.data
        assert 'tool_calls_made' in response.data
        assert isinstance(response.data['tool_calls_made'], list)
        assert response.data['response'] == 'mocked anthropic response'

    def test_chat_without_history(self):
        """Test chat request without conversation history."""
        self.client.force_authenticate(user=self.hr_user)

        payload = {
            'message': 'List all employees',
        }

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_200_OK

    def test_empty_message_validation(self):
        """Test that empty message is rejected."""
        self.client.force_authenticate(user=self.sales_user)

        payload = {'message': '', 'history': []}

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'message' in response.data

    def test_message_length_validation(self):
        """Test that excessively long message is rejected."""
        self.client.force_authenticate(user=self.ceo_user)

        # Create message exceeding 4000 character limit
        long_message = 'a' * 4001

        payload = {'message': long_message}

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'message' in response.data

    def test_invalid_history_format(self):
        """Test that invalid history format is rejected."""
        self.client.force_authenticate(user=self.hr_user)

        payload = {
            'message': 'Hello',
            'history': [
                {'invalid_field': 'value'},  # Missing role and content
            ],
        }

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced (20 requests per minute)."""
        self.client.force_authenticate(user=self.sales_user)

        payload = {'message': 'Test message'}

        # Make 20 successful requests
        for i in range(20):
            response = self.client.post(self.endpoint, payload, format='json')
            assert response.status_code == status.HTTP_200_OK

        # 21st request should be rate limited
        response = self.client.post(self.endpoint, payload, format='json')
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert 'detail' in response.data
        assert 'rate_limit' in response.data

    def test_rate_limit_per_user(self):
        """Test that rate limit is per-user, not global."""
        payload = {'message': 'Test message'}

        # First user makes request
        self.client.force_authenticate(user=self.ceo_user)
        response1 = self.client.post(self.endpoint, payload, format='json')
        assert response1.status_code == status.HTTP_200_OK

        # Different user should not be affected by first user's rate limit
        self.client.force_authenticate(user=self.hr_user)
        response2 = self.client.post(self.endpoint, payload, format='json')
        assert response2.status_code == status.HTTP_200_OK

    def test_chat_with_all_roles(self):
        """Test that all user roles can access the endpoint."""
        payload = {'message': 'Tell me about my dashboard'}

        for user, role_name in [
            (self.ceo_user, 'CEO'),
            (self.hr_user, 'HR'),
            (self.sales_user, 'SALES'),
            (self.it_user, 'IT'),
            (self.inventory_user, 'INVENTORY'),
        ]:
            cache.clear()  # Clear rate limit for each user
            self.client.force_authenticate(user=user)

            response = self.client.post(self.endpoint, payload, format='json')
            assert response.status_code == status.HTTP_200_OK, f'Failed for {role_name} role'

    def test_response_structure(self):
        """Test that response has correct structure."""
        self.client.force_authenticate(user=self.ceo_user)

        payload = {'message': 'What are sales trends?'}

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)
        assert 'response' in response.data
        assert 'tool_calls_made' in response.data

        # Check types
        assert isinstance(response.data['response'], str)
        assert isinstance(response.data['tool_calls_made'], list)

    def test_missing_message_field(self):
        """Test that missing message field is rejected."""
        self.client.force_authenticate(user=self.hr_user)

        payload = {'history': []}  # Missing message

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'message' in response.data

    def test_whitespace_only_message(self):
        """Test that whitespace-only message is rejected."""
        self.client.force_authenticate(user=self.sales_user)

        payload = {'message': '   \n\t  '}

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_history_with_invalid_role(self):
        """Test that invalid role in history is rejected."""
        self.client.force_authenticate(user=self.ceo_user)

        payload = {
            'message': 'Hello',
            'history': [
                {'role': 'invalid_role', 'content': 'test'},
            ],
        }

        response = self.client.post(self.endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
