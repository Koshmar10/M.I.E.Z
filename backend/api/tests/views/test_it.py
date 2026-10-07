"""Tests for api/views/it.py: tickets, assets and IT dashboards."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Asset, Ticket, User


class ITDashboardTests(APITestCase):
    def setUp(self):
        self.ceo = User.objects.create_user(username='ceo', role=User.Role.CEO, email='ceo@example.com')
        self.hr_user = User.objects.create_user(username='hr', role=User.Role.HR, email='hr@example.com')
        self.it_user = User.objects.create_user(username='it', role=User.Role.IT, email='it@example.com')

        self.now = timezone.now()

    def test_access_control(self):
        """Only CEO and IT should access the IT dashboard"""
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get('/api/it/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.ceo)
        response = self.client.get('/api/it/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.it_user)
        response = self.client.get('/api/it/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_metrics(self):
        """Test that counts and SLA math are correct"""
        self.client.force_authenticate(user=self.ceo)

        # Create workload
        Ticket.objects.create(ticket_number='T1', status=Ticket.Status.OPEN)
        Ticket.objects.create(ticket_number='T2', status=Ticket.Status.OPEN, priority=Ticket.Priority.URGENT)
        Ticket.objects.create(ticket_number='T3', status=Ticket.Status.IN_PROGRESS)

        # Create resolved (SLA met: 2 hours)
        t4 = Ticket.objects.create(ticket_number='T4', status=Ticket.Status.RESOLVED)
        t4.created_at = self.now - timedelta(hours=2)
        t4.resolved_at = self.now
        t4.save()

        # Create resolved (SLA missed: 6 hours)
        t5 = Ticket.objects.create(ticket_number='T5', status=Ticket.Status.RESOLVED)
        t5.created_at = self.now - timedelta(hours=6)
        t5.resolved_at = self.now
        t5.save()

        response = self.client.get('/api/it/dashboard/')
        data = response.data

        self.assertEqual(data['open_ticket'], 2)
        self.assertEqual(data['ceo_it_summary']['critical_open'], 1)
        self.assertEqual(data['ceo_it_summary']['avg_resolution_time_hrs'], 4.0)
        self.assertEqual(data['ceo_it_summary']['sla_met_percentage'], 50.0)

    def test_model_auto_resolve_timestamp(self):
        """Test that out save() method handles resolved_at correctly"""
        ticket = Ticket.objects.create(ticket_number='T99', status=Ticket.Status.OPEN)
        self.assertIsNone(ticket.resolved_at)

        ticket.status = Ticket.Status.RESOLVED
        ticket.resolved_at = timezone.now()
        ticket.save()

        self.assertIsNotNone(ticket.resolved_at)

    def test_ticket_trend_returns_last_six_weeks_with_opened_and_closed_counts(self):
        self.client.force_authenticate(user=self.ceo)

        now = timezone.now()
        current_week_start = now - timedelta(days=now.weekday())
        current_week_start = current_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        five_weeks_ago_start = current_week_start - timedelta(weeks=5)
        one_week_ago_start = current_week_start - timedelta(weeks=1)
        six_weeks_ago_start = current_week_start - timedelta(weeks=6)

        current_open = baker.make(Ticket, ticket_number='TREND-001', status=Ticket.Status.OPEN)
        week_minus_one = baker.make(Ticket, ticket_number='TREND-002', status=Ticket.Status.RESOLVED)
        created_old_resolved_now = baker.make(Ticket, ticket_number='TREND-003', status=Ticket.Status.RESOLVED)
        out_of_window = baker.make(Ticket, ticket_number='TREND-004', status=Ticket.Status.RESOLVED)

        Ticket.objects.filter(id=current_open.id).update(
            created_at=current_week_start + timedelta(days=1),
            resolved_at=None,
        )
        Ticket.objects.filter(id=week_minus_one.id).update(
            created_at=one_week_ago_start + timedelta(days=2),
            resolved_at=one_week_ago_start + timedelta(days=3),
        )
        Ticket.objects.filter(id=created_old_resolved_now.id).update(
            created_at=five_weeks_ago_start + timedelta(days=1),
            resolved_at=current_week_start + timedelta(days=2),
        )
        Ticket.objects.filter(id=out_of_window.id).update(
            created_at=six_weeks_ago_start + timedelta(days=1),
            resolved_at=six_weeks_ago_start + timedelta(days=2),
        )

        response = self.client.get('/api/it/ticket-trend/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('weeks', response.data)
        self.assertEqual(len(response.data['weeks']), 6)

        week_map = {row['week_start']: row for row in response.data['weeks']}
        self.assertEqual(
            response.data['weeks'][0]['week_start'],
            five_weeks_ago_start.date().isoformat(),
        )
        self.assertEqual(
            response.data['weeks'][-1]['week_start'],
            current_week_start.date().isoformat(),
        )

        self.assertEqual(week_map[five_weeks_ago_start.date().isoformat()]['opened_count'], 1)
        self.assertEqual(week_map[five_weeks_ago_start.date().isoformat()]['closed_count'], 0)

        self.assertEqual(week_map[one_week_ago_start.date().isoformat()]['opened_count'], 1)
        self.assertEqual(week_map[one_week_ago_start.date().isoformat()]['closed_count'], 1)

        self.assertEqual(week_map[current_week_start.date().isoformat()]['opened_count'], 1)
        self.assertEqual(week_map[current_week_start.date().isoformat()]['closed_count'], 1)

    def test_ticket_trend_forbidden_for_non_it_and_non_ceo(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get('/api/it/ticket-trend/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TicketListViewTests(APITestCase):
    def setUp(self):
        self.ceo = User.objects.create_user(username='ceo_tickets', role=User.Role.CEO, email='ceo_tickets@example.com')
        self.it_user = User.objects.create_user(
            username='it_tickets', role=User.Role.IT, email='it_tickets@example.com'
        )
        self.sales_user = User.objects.create_user(
            username='sales_tickets', role=User.Role.SALES, email='sales_tickets@example.com'
        )

        from api.models import Department

        self.it_department = Department.objects.create(name='IT Support', slug='it-support')
        self.hr_department = Department.objects.create(name='HR', slug='hr')

        Ticket.objects.create(
            ticket_number='IT-001',
            title='Laptop not booting',
            description='Device stuck on BIOS screen',
            department=self.it_department,
            status=Ticket.Status.OPEN,
            assigned_to=self.it_user,
        )
        Ticket.objects.create(
            ticket_number='IT-002',
            title='Email migration issue',
            description='Mailbox sync fails after update',
            department=self.it_department,
            status=Ticket.Status.IN_PROGRESS,
            assigned_to=self.it_user,
        )
        Ticket.objects.create(
            ticket_number='HR-001',
            title='Payroll access reset',
            description='Cannot log in to payroll portal',
            department=self.hr_department,
            status=Ticket.Status.OPEN,
            assigned_to=self.ceo,
        )

    def test_ticket_list_requires_it_or_ceo_role(self):
        self.client.force_authenticate(user=self.sales_user)
        response = self.client.get('/api/tickets/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ticket_list_includes_total_count(self):
        self.client.force_authenticate(user=self.it_user)
        response = self.client.get('/api/tickets/?page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 3)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)

    def test_ticket_list_filters_with_django_filter_params(self):
        self.client.force_authenticate(user=self.it_user)

        response = self.client.get(
            f'/api/tickets/?category={self.it_department.id}&status=OPEN&assigned_to={self.it_user.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(response.data['results'][0]['ticket_number'], 'IT-001')

    def test_ticket_list_search_filters_results(self):
        self.client.force_authenticate(user=self.it_user)

        response = self.client.get('/api/tickets/?search=mailbox')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(response.data['results'][0]['ticket_number'], 'IT-002')


class TicketApiTests(APITestCase):
    def setUp(self):
        from api.models import Department

        user_model = get_user_model()
        self.it_user = baker.make(
            user_model,
            role=user_model.Role.IT,
            username='it_test_user',
            email='it_test_user@example.com',
        )
        self.ceo_user = baker.make(
            user_model,
            role=user_model.Role.CEO,
            username='ceo_test_user',
            email='ceo_test_user@example.com',
        )
        self.hardware_department = baker.make(Department, name='Hardware', slug='hardware')

    def test_post_tickets_valid_payload_returns_201_with_new_status_and_auto_incremented_number(self):
        self.client.force_authenticate(user=self.it_user)

        first_response = self.client.post(
            '/api/tickets/',
            {
                'title': 'Laptop battery issue',
                'description': 'Battery drains in 30 minutes.',
                'priority': Ticket.Priority.HIGH,
            },
            format='json',
        )

        second_response = self.client.post(
            '/api/tickets/',
            {
                'title': 'VPN access failure',
                'description': 'Cannot connect from home network.',
                'priority': Ticket.Priority.MEDIUM,
            },
            format='json',
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(first_response.data['status'], Ticket.Status.OPEN)
        self.assertEqual(second_response.data['status'], Ticket.Status.OPEN)
        self.assertTrue(first_response.data['ticket_number'].startswith('TKT-'))
        self.assertTrue(second_response.data['ticket_number'].startswith('TKT-'))

        first_number = int(first_response.data['ticket_number'].split('-')[1])
        second_number = int(second_response.data['ticket_number'].split('-')[1])
        self.assertEqual(second_number, first_number + 1)

    def test_post_tickets_missing_title_returns_400_with_title_key(self):
        self.client.force_authenticate(user=self.it_user)

        response = self.client.post(
            '/api/tickets/',
            {
                'description': 'Keyboard keys are not working.',
                'priority': Ticket.Priority.LOW,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('title', response.data['field_errors'])

    def test_post_tickets_missing_description_returns_400(self):
        self.client.force_authenticate(user=self.it_user)

        response = self.client.post(
            '/api/tickets/',
            {
                'title': 'Monitor flickers intermittently',
                'priority': Ticket.Priority.MEDIUM,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('description', response.data['field_errors'])

    def test_get_tickets_returns_full_list_sorted_by_created_at_desc(self):
        self.client.force_authenticate(user=self.it_user)

        older = baker.make(
            Ticket,
            ticket_number='TKT-00001',
            title='Older ticket',
            description='Older issue',
            status=Ticket.Status.OPEN,
        )
        newer = baker.make(
            Ticket,
            ticket_number='TKT-00002',
            title='Newer ticket',
            description='Newer issue',
            status=Ticket.Status.OPEN,
        )

        now = timezone.now()
        Ticket.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Ticket.objects.filter(id=newer.id).update(created_at=now)

        response = self.client.get('/api/tickets/?page_size=100')

        self.assertEqual(response.status_code, 200)
        numbers = [item['ticket_number'] for item in response.data['results']]
        self.assertEqual(numbers[:2], ['TKT-00002', 'TKT-00001'])

    def test_get_tickets_with_category_filters_correctly(self):
        self.client.force_authenticate(user=self.it_user)

        from api.models import Department

        other_department = baker.make(Department, name='Software', slug='software')

        baker.make(
            Ticket,
            ticket_number='TKT-00010',
            title='Hardware issue',
            description='Disk failure',
            department=self.hardware_department,
            status=Ticket.Status.OPEN,
        )
        baker.make(
            Ticket,
            ticket_number='TKT-00011',
            title='Software issue',
            description='App crash',
            department=other_department,
            status=Ticket.Status.OPEN,
        )

        response = self.client.get('/api/tickets/?category=Hardware&page_size=100')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['ticket_number'], 'TKT-00010')

    def test_get_tickets_with_assigned_to_me_returns_only_requesting_user_tickets(self):
        self.client.force_authenticate(user=self.it_user)

        user_model = get_user_model()
        other_user = baker.make(
            user_model,
            role=user_model.Role.IT,
            username='other_it_user',
            email='other_it_user@example.com',
        )

        baker.make(
            Ticket,
            ticket_number='TKT-00020',
            title='Mine',
            description='Assigned to me',
            assigned_to=self.it_user,
            status=Ticket.Status.OPEN,
        )
        baker.make(
            Ticket,
            ticket_number='TKT-00021',
            title='Not mine',
            description='Assigned to someone else',
            assigned_to=other_user,
            status=Ticket.Status.OPEN,
        )

        response = self.client.get('/api/tickets/?assigned_to=me&page_size=100')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['ticket_number'], 'TKT-00020')

    def test_patch_ticket_status_transitions_open_to_in_progress_to_resolved_with_auto_assignment(self):
        self.client.force_authenticate(user=self.it_user)

        ticket = baker.make(
            Ticket,
            ticket_number='TKT-00030',
            title='Transition ticket',
            description='State machine test',
            status=Ticket.Status.OPEN,
        )

        to_in_progress = self.client.patch(
            f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.IN_PROGRESS}, format='json'
        )
        self.assertEqual(to_in_progress.status_code, 200)
        self.assertEqual(to_in_progress.data['status'], Ticket.Status.IN_PROGRESS)
        self.assertEqual(to_in_progress.data['assigned_to'], self.it_user.id)

        to_resolved = self.client.patch(f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.RESOLVED}, format='json')
        self.assertEqual(to_resolved.status_code, 200)
        self.assertEqual(to_resolved.data['status'], Ticket.Status.RESOLVED)

    def test_patch_ticket_sets_resolved_at_automatically_when_resolved(self):
        self.client.force_authenticate(user=self.it_user)

        ticket = baker.make(
            Ticket,
            ticket_number='TKT-00031',
            title='Resolved timestamp ticket',
            description='Resolved timestamp test',
            status=Ticket.Status.IN_PROGRESS,
            resolved_at=None,
        )

        response = self.client.patch(f'/api/tickets/{ticket.id}/', {'status': Ticket.Status.RESOLVED}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['resolved_at'])

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)

    def test_get_it_dashboard_avg_resolution_time_hours_computed_correctly(self):
        self.client.force_authenticate(user=self.ceo_user)

        now = timezone.now()

        t1 = baker.make(
            Ticket,
            ticket_number='TKT-00040',
            title='Resolved in 2h',
            description='Resolution timing test 1',
            status=Ticket.Status.RESOLVED,
        )
        t2 = baker.make(
            Ticket,
            ticket_number='TKT-00041',
            title='Resolved in 6h',
            description='Resolution timing test 2',
            status=Ticket.Status.RESOLVED,
        )

        Ticket.objects.filter(id=t1.id).update(created_at=now - timedelta(hours=2), resolved_at=now)
        Ticket.objects.filter(id=t2.id).update(created_at=now - timedelta(hours=6), resolved_at=now)

        response = self.client.get('/api/it/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ceo_it_summary']['avg_resolution_time_hrs'], 4.0)

    def test_get_it_dashboard_sla_compliance_counts_tickets_resolved_within_4_hours(self):
        self.client.force_authenticate(user=self.ceo_user)

        now = timezone.now()

        sla_met = baker.make(
            Ticket,
            ticket_number='TKT-00050',
            title='Resolved in 3h',
            description='SLA compliant',
            status=Ticket.Status.RESOLVED,
        )
        sla_missed = baker.make(
            Ticket,
            ticket_number='TKT-00051',
            title='Resolved in 7h',
            description='SLA missed',
            status=Ticket.Status.RESOLVED,
        )

        Ticket.objects.filter(id=sla_met.id).update(created_at=now - timedelta(hours=3), resolved_at=now)
        Ticket.objects.filter(id=sla_missed.id).update(created_at=now - timedelta(hours=7), resolved_at=now)

        response = self.client.get('/api/it/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ceo_it_summary']['sla_met_percentage'], 50.0)


class AssetApiTests(APITestCase):
    def setUp(self):
        self.ceo = baker.make(User, role=User.Role.CEO, username='asset_ceo', email='asset_ceo@example.com')
        self.it_user = baker.make(User, role=User.Role.IT, username='asset_it', email='asset_it@example.com')
        self.hr_user = baker.make(User, role=User.Role.HR, username='asset_hr', email='asset_hr@example.com')
        self.inventory_user = baker.make(
            User,
            role=User.Role.INVENTORY,
            username='asset_inventory',
            email='asset_inventory@example.com',
        )

        self.assets_url = reverse('asset_list_create')

    def test_list_returns_assets_for_ceo_and_it_only(self):
        baker.make(
            Asset,
            _quantity=2,
            assigned_to=self.it_user,
            status=Asset.Status.ASSIGNED,
        )

        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get(self.assets_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.it_user)
        response = self.client.get(self.assets_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(
            {
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
            }.issubset(response.data[0].keys())
        )

    def test_create_asset_returns_serialized_asset(self):
        payload = {
            'name': 'CEO Laptop',
            'serial_number': 'ASSET-TEST-001',
            'category': Asset.Category.LAPTOP,
            'assigned_to': self.ceo.id,
            'status': Asset.Status.ASSIGNED,
            'notes': 'Executive device',
        }

        self.client.force_authenticate(user=self.ceo)
        response = self.client.post(self.assets_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertEqual(response.data['serial_number'], payload['serial_number'])
        self.assertEqual(response.data['assigned_to'], self.ceo.id)
        self.assertEqual(response.data['assigned_to_username'], self.ceo.username)
        self.assertEqual(response.data['assigned_to_name'], self.ceo.get_full_name() or self.ceo.username)

    def test_create_asset_rejects_duplicate_serial_number(self):
        baker.make(Asset, serial_number='ASSET-TEST-002')

        self.client.force_authenticate(user=self.it_user)
        response = self.client.post(
            self.assets_url,
            {
                'name': 'Duplicate Asset',
                'serial_number': 'ASSET-TEST-002',
                'category': Asset.Category.MONITOR,
                'status': Asset.Status.AVAILABLE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('serial_number', response.data['field_errors'])

    def test_detail_update_and_delete_work_for_it_and_ceo(self):
        asset = baker.make(
            Asset,
            name='Old Laptop',
            serial_number='ASSET-TEST-003',
            category=Asset.Category.LAPTOP,
            assigned_to=self.it_user,
            status=Asset.Status.ASSIGNED,
        )
        detail_url = reverse('asset_detail', kwargs={'id': asset.id})

        self.client.force_authenticate(user=self.inventory_user)
        response = self.client.patch(detail_url, {'name': 'Blocked Update'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.it_user)
        response = self.client.patch(
            detail_url,
            {
                'name': 'Updated Laptop',
                'status': Asset.Status.MAINTENANCE,
                'notes': 'Needs screen replacement',
                'assigned_to': self.ceo.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Laptop')
        self.assertEqual(response.data['status'], Asset.Status.MAINTENANCE)
        self.assertEqual(response.data['assigned_to'], self.ceo.id)
        self.assertEqual(response.data['assigned_to_username'], self.ceo.username)

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Asset.objects.filter(id=asset.id).exists())

    def test_detail_returns_404_for_missing_asset(self):
        self.client.force_authenticate(user=self.ceo)
        response = self.client.get(reverse('asset_detail', kwargs={'id': 999999}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
