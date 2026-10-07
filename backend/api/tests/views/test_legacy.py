"""Tests for api/views/legacy.py."""

import pytest


@pytest.mark.parametrize(('number', 'even'), [(4, True), (3, False), (0, True), (-2, True), (-7, False)])
def test_is_even(client, number, even):
    response = client.get('/api/is_even/', {'number': number})
    assert response.status_code == 200
    assert response.json()['even'] is even


@pytest.mark.parametrize('params', [{}, {'number': 'abc'}, {'number': '2.5'}])
def test_is_even_rejects_missing_or_non_integer_input(client, params):
    response = client.get('/api/is_even/', params)
    assert response.status_code == 400
    assert 'error' in response.json()


def test_is_even_post_not_allowed(client):
    response = client.post('/api/is_even/', {'number': 2})
    assert response.status_code == 405
