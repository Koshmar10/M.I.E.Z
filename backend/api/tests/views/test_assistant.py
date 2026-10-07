"""Tests for api/views/assistant.py: the assistant chat endpoint."""

from unittest.mock import patch

import pytest
from django.core.cache import cache

from api.agent.runner import AgentRunner

URL = '/api/assistant/chat/'


@pytest.fixture(autouse=True)
def fake_anthropic():
    """Never call the real Claude API, and start every test with an empty rate-limit cache."""
    cache.clear()
    reply = {'response': 'mocked anthropic response', 'tool_calls_made': []}
    with patch.object(AgentRunner, '_call_anthropic', return_value=reply):
        yield


def test_requires_authentication(api_client):
    assert api_client.post(URL, {'message': 'Hello'}, format='json').status_code == 401


def test_valid_chat_request(ceo_client):
    payload = {
        'message': 'What is the sales status?',
        'history': [{'role': 'user', 'content': 'Hello'}, {'role': 'assistant', 'content': 'Hi there!'}],
    }

    response = ceo_client.post(URL, payload, format='json')

    assert response.status_code == 200
    assert response.data['response'] == 'mocked anthropic response'
    assert response.data['tool_calls_made'] == []


def test_chat_without_history(hr_client):
    assert hr_client.post(URL, {'message': 'List all employees'}, format='json').status_code == 200


@pytest.mark.parametrize(
    ('payload', 'error_field'),
    [
        ({'message': '', 'history': []}, 'message'),
        ({'message': 'a' * 4001}, 'message'),  # over the 4000-character limit
        ({'history': []}, 'message'),
        ({'message': '   \n\t  '}, None),
        ({'message': 'Hello', 'history': [{'invalid_field': 'value'}]}, None),
        ({'message': 'Hello', 'history': [{'role': 'invalid_role', 'content': 'test'}]}, None),
    ],
)
def test_invalid_payload_is_rejected(sales_client, payload, error_field):
    response = sales_client.post(URL, payload, format='json')

    assert response.status_code == 400
    if error_field:
        assert error_field in response.data


def test_rate_limit_enforcement(sales_client):
    for _ in range(20):
        assert sales_client.post(URL, {'message': 'Test message'}, format='json').status_code == 200

    response = sales_client.post(URL, {'message': 'Test message'}, format='json')

    assert response.status_code == 429
    assert 'detail' in response.data
    assert 'rate_limit' in response.data


def test_rate_limit_per_user(ceo_client, hr_client):
    assert ceo_client.post(URL, {'message': 'Test message'}, format='json').status_code == 200
    assert hr_client.post(URL, {'message': 'Test message'}, format='json').status_code == 200


def test_chat_with_all_roles(ceo_client, hr_client, sales_client, it_client, inventory_client):
    for client in (ceo_client, hr_client, sales_client, it_client, inventory_client):
        response = client.post(URL, {'message': 'Tell me about my dashboard'}, format='json')
        assert response.status_code == 200
