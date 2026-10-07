"""Tests for api/views/reports.py."""

from itertools import count

from model_bakery import baker

from api.models import Report

_report_ids = count(1)


def _report(**fields) -> Report:
    # slug defaults to '' but must be unique, so give each report its own
    return baker.make(Report, slug=f'report-{next(_report_ids)}', **fields)


def _report_file(tmp_path):
    path = tmp_path / 'report.csv'
    path.write_text('Name,Value\nAlice,100\n')
    return str(path)


# ── List ─────────────────────────────────────────────────────────────────────


def test_ceo_sees_reports_across_all_categories(ceo_client):
    _report(category='HR')
    _report(category='Sales')

    response = ceo_client.get('/api/reports/')

    assert response.status_code == 200
    assert len(response.data) == 2


def test_non_ceo_only_sees_own_category(hr_client):
    _report(category='HR')
    _report(category='Sales')

    response = hr_client.get('/api/reports/')

    assert response.status_code == 200
    assert [r['category'] for r in response.data] == ['HR']


def test_filter_by_forbidden_category_returns_403(hr_client):
    _report(category='Sales')
    assert hr_client.get('/api/reports/', {'category': 'Sales'}).status_code == 403


def test_returns_correct_metadata_fields(hr_client):
    _report(category='HR')

    response = hr_client.get('/api/reports/')

    assert response.status_code == 200
    expected = {'id', 'name', 'slug', 'category', 'period', 'file_size_kb', 'generated_at', 'file_available'}
    assert expected <= response.data[0].keys()


def test_filter_by_category(hr_client):
    _report(category='HR')
    _report(category='Sales')

    response = hr_client.get('/api/reports/', {'category': 'HR'})

    assert response.status_code == 200
    assert [r['category'] for r in response.data] == ['HR']


def test_list_unauthenticated_returns_401(api_client):
    assert api_client.get('/api/reports/').status_code == 401


# ── Download ─────────────────────────────────────────────────────────────────


def test_download_returns_file_response(hr_client, tmp_path):
    report = _report(category='HR', file_path=_report_file(tmp_path))

    response = hr_client.get(f'/api/reports/{report.id}/download/')

    assert response.status_code == 200
    assert 'text/csv' in response['Content-Type']


def test_download_returns_404_when_file_path_missing(hr_client):
    report = _report(category='HR', file_path='')
    assert hr_client.get(f'/api/reports/{report.id}/download/').status_code == 404


def test_download_returns_404_when_file_does_not_exist_on_disk(hr_client, tmp_path):
    report = _report(category='HR', file_path=str(tmp_path / 'missing.csv'))
    assert hr_client.get(f'/api/reports/{report.id}/download/').status_code == 404


def test_download_returns_404_for_unknown_report(hr_client):
    assert hr_client.get('/api/reports/99999/download/').status_code == 404


def test_download_forbidden_for_other_category(hr_client, tmp_path):
    report = _report(category='Sales', file_path=_report_file(tmp_path))
    assert hr_client.get(f'/api/reports/{report.id}/download/').status_code == 403


# ── Generate ─────────────────────────────────────────────────────────────────


def test_generate_non_ceo_gets_403(hr_client):
    report = _report()
    assert hr_client.post(f'/api/reports/generate/{report.slug}/').status_code == 403


def test_generate_unauthenticated_gets_401(api_client):
    report = _report()
    assert api_client.post(f'/api/reports/generate/{report.slug}/').status_code == 401


def test_generate_invalid_slug_returns_404(ceo_client):
    assert ceo_client.post('/api/reports/generate/does-not-exist/').status_code == 404
