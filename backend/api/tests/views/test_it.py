"""Tests for api/views/it.py: tickets, assets and IT dashboards."""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from api.models import Asset, Department, Ticket, User


def _ticket_timed(created_hours_ago: float, resolved: bool = True, **fields) -> Ticket:
    """A ticket created `created_hours_ago` hours ago and, if `resolved`, resolved now."""
    now = timezone.now()
    ticket = baker.make(Ticket, status=Ticket.Status.RESOLVED if resolved else Ticket.Status.OPEN, **fields)
    Ticket.objects.filter(id=ticket.id).update(
        created_at=now - timedelta(hours=created_hours_ago), resolved_at=now if resolved else None
    )
    return ticket


# ── IT dashboard ─────────────────────────────────────────────────────────────


def test_it_dashboard_only_for_ceo_and_it(hr_client, ceo_client, it_client):
    assert hr_client.get('/api/it/dashboard/').status_code == 403
    assert ceo_client.get('/api/it/dashboard/').status_code == 200
    assert it_client.get('/api/it/dashboard/').status_code == 200


def test_dashboard_metrics(ceo_client):
    baker.make(Ticket, status=Ticket.Status.OPEN)
    baker.make(Ticket, status=Ticket.Status.OPEN, priority=Ticket.Priority.URGENT)
    baker.make(Ticket, status=Ticket.Status.IN_PROGRESS)
    _ticket_timed(created_hours_ago=2)  # SLA met
    _ticket_timed(created_hours_ago=6)  # SLA missed

    data = ceo_client.get('/api/it/dashboard/').data

    assert data['open_ticket'] == 2
    assert data['ceo_it_summary']['critical_open'] == 1
    assert data['ceo_it_summary']['avg_resolution_time_hrs'] == 4.0
    assert data['ceo_it_summary']['sla_met_percentage'] == 50.0


def test_get_it_dashboard_avg_resolution_time_hours_computed_correctly(ceo_client):
    _ticket_timed(created_hours_ago=2)
    _ticket_timed(created_hours_ago=6)

    response = ceo_client.get('/api/it/dashboard/')

    assert response.status_code == 200
    assert response.data['ceo_it_summary']['avg_resolution_time_hrs'] == 4.0


def test_get_it_dashboard_sla_compliance_counts_tickets_resolved_within_4_hours(ceo_client):
    _ticket_timed(created_hours_ago=3)
    _ticket_timed(created_hours_ago=7)

    response = ceo_client.get('/api/it/dashboard/')

    assert response.status_code == 200
    assert response.data['ceo_it_summary']['sla_met_percentage'] == 50.0


def test_model_auto_resolve_timestamp():
    ticket = baker.make(Ticket, status=Ticket.Status.OPEN)
    assert ticket.resolved_at is None

    ticket.status = Ticket.Status.RESOLVED
    ticket.resolved_at = timezone.now()
    ticket.save()

    assert ticket.resolved_at is not None


def test_ticket_trend_returns_last_six_weeks_with_opened_and_closed_counts(ceo_client):
    now = timezone.now()
    this_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    one_week_ago = this_week - timedelta(weeks=1)
    five_weeks_ago = this_week - timedelta(weeks=5)
    six_weeks_ago = this_week - timedelta(weeks=6)
    for created_at, resolved_at in [
        (this_week + timedelta(days=1), None),
        (one_week_ago + timedelta(days=2), one_week_ago + timedelta(days=3)),
        (five_weeks_ago + timedelta(days=1), this_week + timedelta(days=2)),
        (six_weeks_ago + timedelta(days=1), six_weeks_ago + timedelta(days=2)),  # outside the window
    ]:
        ticket = baker.make(Ticket)
        Ticket.objects.filter(id=ticket.id).update(created_at=created_at, resolved_at=resolved_at)

    response = ceo_client.get('/api/it/ticket-trend/')

    assert response.status_code == 200
    weeks = response.data['weeks']
    assert len(weeks) == 6
    assert weeks[0]['week_start'] == five_weeks_ago.date().isoformat()
    assert weeks[-1]['week_start'] == this_week.date().isoformat()
    counts = {row['week_start']: (row['opened_count'], row['closed_count']) for row in weeks}
    assert counts[five_weeks_ago.date().isoformat()] == (1, 0)
    assert counts[one_week_ago.date().isoformat()] == (1, 1)
    assert counts[this_week.date().isoformat()] == (1, 1)


def test_ticket_trend_forbidden_for_non_it_and_non_ceo(hr_client):
    assert hr_client.get('/api/it/ticket-trend/').status_code == 403


# ── Ticket list and filters ──────────────────────────────────────────────────


@pytest.fixture
def it_department():
    return baker.make(Department, name='IT Support', slug='it-support')


@pytest.fixture
def listed_tickets(it_user, ceo_user, it_department):
    hr_department = baker.make(Department, name='HR', slug='hr')
    baker.make(
        Ticket,
        ticket_number='IT-001',
        description='Device stuck on BIOS screen',
        department=it_department,
        status=Ticket.Status.OPEN,
        assigned_to=it_user,
    )
    baker.make(
        Ticket,
        ticket_number='IT-002',
        description='Mailbox sync fails after update',
        department=it_department,
        status=Ticket.Status.IN_PROGRESS,
        assigned_to=it_user,
    )
    baker.make(
        Ticket,
        ticket_number='HR-001',
        description='Cannot log in to payroll portal',
        department=hr_department,
        status=Ticket.Status.OPEN,
        assigned_to=ceo_user,
    )


def test_ticket_list_requires_it_or_ceo_role(sales_client):
    assert sales_client.get('/api/tickets/').status_code == 403


def test_ticket_list_includes_total_count(it_client, listed_tickets):
    response = it_client.get('/api/tickets/?page_size=2')

    assert response.status_code == 200
    assert response.data['total_count'] == 3
    assert response.data['count'] == 3
    assert len(response.data['results']) == 2


def test_ticket_list_filters_with_django_filter_params(it_client, it_user, it_department, listed_tickets):
    response = it_client.get(f'/api/tickets/?category={it_department.id}&status=OPEN&assigned_to={it_user.id}')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert response.data['results'][0]['ticket_number'] == 'IT-001'


def test_ticket_list_search_filters_results(it_client, listed_tickets):
    response = it_client.get('/api/tickets/?search=mailbox')

    assert response.status_code == 200
    assert response.data['total_count'] == 1
    assert response.data['results'][0]['ticket_number'] == 'IT-002'


def test_get_tickets_returns_full_list_sorted_by_created_at_desc(it_client):
    now = timezone.now()
    older = baker.make(Ticket, ticket_number='TKT-00001')
    newer = baker.make(Ticket, ticket_number='TKT-00002')
    Ticket.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
    Ticket.objects.filter(id=newer.id).update(created_at=now)

    response = it_client.get('/api/tickets/?page_size=100')

    assert response.status_code == 200
    assert [item['ticket_number'] for item in response.data['results']][:2] == ['TKT-00002', 'TKT-00001']


def test_get_tickets_with_category_filters_correctly(it_client):
    baker.make(Ticket, ticket_number='TKT-00010', department=baker.make(Department, name='Hardware'))
    baker.make(Ticket, ticket_number='TKT-00011', department=baker.make(Department, name='Software'))

    response = it_client.get('/api/tickets/?category=Hardware&page_size=100')

    assert response.status_code == 200
    assert [t['ticket_number'] for t in response.data['results']] == ['TKT-00010']


def test_get_tickets_with_assigned_to_me_returns_only_requesting_user_tickets(it_client, it_user):
    baker.make(Ticket, ticket_number='TKT-00020', assigned_to=it_user)
    baker.make(Ticket, ticket_number='TKT-00021', assigned_to=baker.make(User, role=User.Role.IT))

    response = it_client.get('/api/tickets/?assigned_to=me&page_size=100')

    assert response.status_code == 200
    assert [t['ticket_number'] for t in response.data['results']] == ['TKT-00020']


# ── Ticket create and update ─────────────────────────────────────────────────


def test_post_tickets_valid_payload_returns_201_with_new_status_and_auto_incremented_number(it_client):
    first = it_client.post(
        '/api/tickets/',
        {'title': 'Laptop battery issue', 'description': 'Drains in 30 minutes.', 'priority': Ticket.Priority.HIGH},
        format='json',
    )
    second = it_client.post(
        '/api/tickets/',
        {'title': 'VPN access failure', 'description': 'Cannot connect.', 'priority': Ticket.Priority.MEDIUM},
        format='json',
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data['status'] == second.data['status'] == Ticket.Status.OPEN
    assert first.data['ticket_number'].startswith('TKT-')
    assert second.data['ticket_number'].startswith('TKT-')
    assert int(second.data['ticket_number'].split('-')[1]) == int(first.data['ticket_number'].split('-')[1]) + 1


def test_post_tickets_missing_title_returns_400_with_title_key(it_client):
    response = it_client.post(
        '/api/tickets/',
        {'description': 'Keyboard keys are not working.', 'priority': Ticket.Priority.LOW},
        format='json',
    )

    assert response.status_code == 400
    assert 'title' in response.data['field_errors']


def test_post_tickets_missing_description_returns_400(it_client):
    response = it_client.post(
        '/api/tickets/', {'title': 'Monitor flickers', 'priority': Ticket.Priority.MEDIUM}, format='json'
    )

    assert response.status_code == 400
    assert 'description' in response.data['field_errors']


def test_patch_ticket_status_transitions_open_to_in_progress_to_resolved_with_auto_assignment(it_client, it_user):
    ticket = baker.make(Ticket, status=Ticket.Status.OPEN)

    to_in_progress = it_client.patch(f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.IN_PROGRESS}, format='json')
    assert to_in_progress.status_code == 200
    assert to_in_progress.data['status'] == Ticket.Status.IN_PROGRESS
    assert to_in_progress.data['assigned_to'] == it_user.id

    to_resolved = it_client.patch(f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.RESOLVED}, format='json')
    assert to_resolved.status_code == 200
    assert to_resolved.data['status'] == Ticket.Status.RESOLVED


def test_patch_ticket_sets_resolved_at_automatically_when_resolved(it_client):
    ticket = baker.make(Ticket, status=Ticket.Status.IN_PROGRESS, resolved_at=None)

    response = it_client.patch(f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.RESOLVED}, format='json')

    assert response.status_code == 200
    assert response.data['resolved_at'] is not None
    ticket.refresh_from_db()
    assert ticket.resolved_at is not None


# ── Assets ───────────────────────────────────────────────────────────────────


def test_list_returns_assets_for_ceo_and_it_only(hr_client, it_client, it_user):
    baker.make(Asset, assigned_to=it_user, status=Asset.Status.ASSIGNED, _quantity=2)

    assert hr_client.get('/api/it/assets/').status_code == 403

    response = it_client.get('/api/it/assets/')
    assert response.status_code == 200
    assert len(response.data) == 2
    assert {
        'id',
        'name',
        'serial_number',
        'category',
        'assigned_to',
        'assigned_to_username',
        'assigned_to_name',
        'status',
        'notes',
        'created_at',
    } <= response.data[0].keys()


def test_create_asset_returns_serialized_asset(ceo_client, ceo_user):
    payload = {
        'name': 'CEO Laptop',
        'serial_number': 'ASSET-TEST-001',
        'category': Asset.Category.LAPTOP,
        'assigned_to': ceo_user.id,
        'status': Asset.Status.ASSIGNED,
        'notes': 'Executive device',
    }

    response = ceo_client.post('/api/it/assets/', payload, format='json')

    assert response.status_code == 201
    assert response.data['name'] == payload['name']
    assert response.data['serial_number'] == payload['serial_number']
    assert response.data['assigned_to'] == ceo_user.id
    assert response.data['assigned_to_username'] == ceo_user.username
    assert response.data['assigned_to_name'] == (ceo_user.get_full_name() or ceo_user.username)


def test_create_asset_rejects_duplicate_serial_number(it_client):
    baker.make(Asset, serial_number='ASSET-TEST-002')

    response = it_client.post(
        '/api/it/assets/',
        {
            'name': 'Duplicate Asset',
            'serial_number': 'ASSET-TEST-002',
            'category': Asset.Category.MONITOR,
            'status': Asset.Status.AVAILABLE,
        },
        format='json',
    )

    assert response.status_code == 400
    assert 'serial_number' in response.data['field_errors']


def test_detail_update_and_delete_work_for_it_and_ceo(inventory_client, it_client, it_user, ceo_user):
    asset = baker.make(Asset, category=Asset.Category.LAPTOP, assigned_to=it_user, status=Asset.Status.ASSIGNED)
    url = f'/api/it/assets/{asset.id}/'

    assert inventory_client.patch(url, {'name': 'Blocked Update'}, format='json').status_code == 403

    response = it_client.patch(
        url,
        {
            'name': 'Updated Laptop',
            'status': Asset.Status.MAINTENANCE,
            'notes': 'Needs screen replacement',
            'assigned_to': ceo_user.id,
        },
        format='json',
    )
    assert response.status_code == 200
    assert response.data['name'] == 'Updated Laptop'
    assert response.data['status'] == Asset.Status.MAINTENANCE
    assert response.data['assigned_to'] == ceo_user.id
    assert response.data['assigned_to_username'] == ceo_user.username

    assert it_client.delete(url).status_code == 204
    assert not Asset.objects.filter(id=asset.id).exists()


def test_detail_returns_404_for_missing_asset(ceo_client):
    assert ceo_client.get('/api/it/assets/999999/').status_code == 404
