from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Customer, Department, Order, OrderItem, Product, Ticket, User


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


class AuthTests(APITestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'testpass123'
        User = get_user_model()
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.login_url = reverse('login')
        self.me_url = reverse('user_me')
        self.logout_url = reverse('logout')

    def test_login_sets_cookies(self):
        data = {'username': self.username, 'password': self.password}
        response = self.client.post(self.login_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.SIMPLE_JWT['AUTH_COOKIE'], response.cookies)
        self.assertIn(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'], response.cookies)
        self.assertTrue(response.cookies[settings.SIMPLE_JWT['AUTH_COOKIE']]['httponly'])

    def test_protected_route_access(self):
        self.client.post(self.login_url, {'username': self.username, 'password': self.password})
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Ensure expected fields exist in the JSON response. The user model may not
        # always expose a `role` attribute, so assert presence of core fields.
        self.assertEqual(data.get('username'), self.username)
        self.assertIn('email', data)
        self.assertIn('message', data)

    def test_access_denied_without_cookie(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_clears_cookies(self):
        self.client.post(self.login_url, {'username': self.username, 'password': self.password})

        response = self.client.post(self.logout_url)
        access_cookie = response.cookies.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        self.assertEqual(access_cookie.value, '')


class ApiErrorSchemaTests(APITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.ceo = self.user_model.objects.create_user(
            username='ceo_error_schema',
            email='ceo_error_schema@example.com',
            role=User.Role.CEO,
        )
        self.department = Department.objects.create(name='Schema HR', slug='schema-hr')

    def test_unauthenticated_error_has_standard_schema(self):
        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)
        self.assertIn('field_errors', response.data)
        self.assertEqual(response.data['field_errors'], {})

    def test_validation_error_has_standard_schema_with_field_errors(self):
        self.client.force_authenticate(user=self.ceo)

        payload = {
            'last_name': 'Ionescu',
            'email': 'schema.employee@example.com',
            'phone': '+40123456789',
            'department': self.department.id,
            'position': 'Analyst',
            'employment_type': User.EmploymentType.FULL_TIME,
            'start_date': '2025-02-01',
            'salary_ron': '5000.00',
            'address': 'Schema Street 1',
            'is_active': True,
        }
        response = self.client.post('/api/employees/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)
        self.assertIn('field_errors', response.data)
        self.assertIn('first_name', response.data['field_errors'])

    def test_unhandled_exception_returns_standard_500_schema(self):
        self.client.force_authenticate(user=self.ceo)

        with patch('api.views.auth.UserMeView.get', side_effect=Exception('boom')):
            response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['detail'], 'Internal server error.')
        self.assertEqual(response.data['code'], 'server_error')
        self.assertEqual(response.data['field_errors'], {})


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

        from ..models import Department

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
        from ..models import Department

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

        from ..models import Department

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


class EmployeeDepartmentCrudTests(APITestCase):
    def setUp(self):
        self.ceo_user = User.objects.create_user(
            username='ceo_employee_crud',
            email='ceo_employee_crud@example.com',
            role=User.Role.CEO,
        )
        self.hr_user = User.objects.create_user(
            username='hr_employee_crud',
            email='hr_employee_crud@example.com',
            role=User.Role.HR,
        )
        self.hr_department = Department.objects.create(name='HR', slug='hr')
        self.it_department = Department.objects.create(name='IT', slug='it')

        self.valid_payload = {
            'first_name': 'Ana',
            'last_name': 'Popescu',
            'email': 'ana.popescu@example.com',
            'phone': '+40123456789',
            'department': self.hr_department.id,
            'position': 'Sales Representative',
            'employment_type': User.EmploymentType.FULL_TIME,
            'start_date': '2025-03-10',
            'salary_ron': '5500.00',
            'address': 'Str. Test 1, Bucuresti',
            'is_active': True,
        }

    def test_post_employees_valid_payload_returns_201_with_employee_object(self):
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.post('/api/employees/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], self.valid_payload['email'])
        self.assertEqual(response.data['first_name'], self.valid_payload['first_name'])
        self.assertEqual(response.data['department']['id'], self.valid_payload['department'])

    def test_post_employees_missing_required_field_returns_400_with_field_name_in_error(self):
        self.client.force_authenticate(user=self.ceo_user)
        payload = dict(self.valid_payload)
        payload.pop('first_name')

        response = self.client.post('/api/employees/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', response.data['field_errors'])

    def test_post_employees_duplicate_email_returns_400(self):
        User.objects.create_user(
            username='existing_employee_email',
            email=self.valid_payload['email'],
            role=User.Role.SALES,
        )
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.post('/api/employees/', self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data['field_errors'])

    def test_patch_employee_updates_department_and_role_for_hr_and_ceo(self):
        employee = baker.make(
            User,
            role=User.Role.SALES,
            department=self.hr_department,
            first_name='Ana',
            last_name='Popescu',
            phone='+40111111111',
            position='Sales Representative',
            is_active=True,
        )
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.patch(
            f'/api/employees/{employee.id}/',
            {
                'first_name': 'Anca',
                'last_name': 'Pop',
                'position': 'IT Specialist',
                'department': self.it_department.id,
                'phone': '+40222222222',
                'is_active': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Anca')
        self.assertEqual(response.data['last_name'], 'Pop')
        self.assertEqual(response.data['position'], 'IT Specialist')
        self.assertEqual(response.data['phone'], '+40222222222')
        self.assertFalse(response.data['is_active'])
        self.assertEqual(response.data['department']['id'], self.it_department.id)

        employee.refresh_from_db()
        self.assertEqual(employee.role, User.Role.IT)

    def test_patch_employee_denied_for_non_hr_or_ceo(self):
        employee = baker.make(User, role=User.Role.SALES, department=self.hr_department)
        sales_user = baker.make(User, role=User.Role.SALES)
        self.client.force_authenticate(user=sales_user)

        response = self.client.patch(
            f'/api/employees/{employee.id}/',
            {'first_name': 'Blocked'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_employees_returns_paginated_list_with_correct_count(self):
        baker.make(User, _quantity=3, department=self.hr_department, role=User.Role.SALES)
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/?page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], User.objects.count())
        self.assertEqual(len(response.data['results']), 2)

    def test_get_employees_department_hr_filters_correctly(self):
        baker.make(User, department=self.hr_department, role=User.Role.HR)
        baker.make(User, department=self.it_department, role=User.Role.IT)
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/?department=hr')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['department']['slug'], 'hr')

    def test_get_employees_stats_totals_computed_correctly_via_orm(self):
        self.ceo_user.is_active = False
        self.ceo_user.full_time = False
        self.ceo_user.save(update_fields=['is_active', 'full_time'])

        self.hr_user.is_active = False
        self.hr_user.full_time = False
        self.hr_user.save(update_fields=['is_active', 'full_time'])

        baker.make(
            User,
            department=self.hr_department,
            role=User.Role.HR,
            is_active=True,
            full_time=True,
        )
        baker.make(
            User,
            department=self.it_department,
            role=User.Role.IT,
            is_active=True,
            full_time=False,
        )
        baker.make(
            User,
            department=None,
            role=User.Role.SALES,
            is_active=False,
            full_time=False,
        )
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/employees/stats/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], User.objects.count())
        self.assertEqual(response.data['active'], 2)
        self.assertEqual(response.data['full_time'], 1)

        departments = {row['name']: row['count'] for row in response.data['departments']}
        self.assertEqual(departments['HR'], 1)
        self.assertEqual(departments['IT'], 1)
        self.assertEqual(departments['Unassigned'], 3)

    def test_post_departments_ceo_creates_department_returns_201(self):
        self.client.force_authenticate(user=self.ceo_user)

        payload = {
            'name': 'Finance',
            'slug': 'finance',
            'icon': 'Calculator',
        }
        response = self.client.post('/api/departments/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], payload['name'])
        self.assertTrue(Department.objects.filter(slug='finance').exists())

    def test_post_departments_non_ceo_role_returns_403(self):
        self.client.force_authenticate(user=self.hr_user)

        payload = {
            'name': 'Legal',
            'slug': 'legal',
            'icon': 'Scale',
        }
        response = self.client.post('/api/departments/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_departments_id_removes_department_returns_204(self):
        department = Department.objects.create(name='Operations', slug='operations')
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.delete(f'/api/departments/{department.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Department.objects.filter(id=department.id).exists())


class OrderListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_orders',
            role=User.Role.SALES,
            email='sales_orders@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_orders',
            role=User.Role.CEO,
            email='ceo_orders@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_orders',
            role=User.Role.HR,
            email='hr_orders@example.com',
        )

        self.customer_acme = Customer.objects.create(name='Acme SRL')
        self.customer_beta = Customer.objects.create(name='Beta SRL')

        self.product_a = Product.objects.create(name='Widget A', sku='WIDGET-A')
        self.product_b = Product.objects.create(name='Widget B', sku='WIDGET-B')

        self.order_1 = Order.objects.create(
            customer=self.customer_acme,
            created_by=self.sales_user,
            value_ron=Decimal('120.50'),
            status=Order.Status.PROCESSING,
            channel=Order.Channel.WEBSITE,
            notes='Priority handling',
        )
        self.order_2 = Order.objects.create(
            customer=self.customer_beta,
            created_by=self.sales_user,
            value_ron=Decimal('80.00'),
            status=Order.Status.SHIPPED,
            channel=Order.Channel.EMAG,
        )
        self.order_3 = Order.objects.create(
            customer=self.customer_acme,
            created_by=self.sales_user,
            value_ron=Decimal('40.00'),
            status=Order.Status.PROCESSING,
            channel=Order.Channel.DIRECT,
        )

        OrderItem.objects.create(
            order=self.order_1, product=self.product_a, quantity=2, unit_price_ron=Decimal('30.00')
        )
        OrderItem.objects.create(
            order=self.order_1, product=self.product_b, quantity=1, unit_price_ron=Decimal('60.50')
        )

    def test_order_number_is_auto_generated_with_hash_format(self):
        self.assertRegex(self.order_1.order_number, r'^#\d{4}$')

    def test_orders_list_supports_search_status_channel_and_includes_totals(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/orders/?search=Acme&status=PROCESSING&channel=WEBSITE')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(Decimal(response.data['total_ron_sum']), Decimal('120.50'))
        self.assertEqual(len(response.data['results']), 1)

        row = response.data['results'][0]
        self.assertIn('order_number', row)
        self.assertEqual(row['customer_name'], 'Acme SRL')
        self.assertEqual(Decimal(row['value_ron']), Decimal('120.50'))
        self.assertEqual(row['status'], Order.Status.PROCESSING)
        self.assertEqual(row['channel'], Order.Channel.WEBSITE)

    def test_orders_list_is_paginated_and_includes_total_sum_for_filtered_queryset(self):
        self.client.force_authenticate(user=self.ceo_user)

        response = self.client.get('/api/orders/?search=SRL&page_size=2')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 3)
        self.assertEqual(Decimal(response.data['total_ron_sum']), Decimal('240.50'))
        self.assertEqual(len(response.data['results']), 2)

    def test_order_detail_includes_line_items_for_modal(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get(f'/api/orders/{self.order_1.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_number'], self.order_1.order_number)
        self.assertEqual(response.data['customer_name'], 'Acme SRL')
        self.assertEqual(len(response.data['items']), 2)
        self.assertIn('line_total_ron', response.data['items'][0])

    def test_orders_endpoints_forbid_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        list_response = self.client.get('/api/orders/')
        detail_response = self.client.get(f'/api/orders/{self.order_1.id}/')

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(detail_response.status_code, status.HTTP_403_FORBIDDEN)


class SalesDashboardKpiTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_kpi',
            role=User.Role.SALES,
            email='sales_kpi@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_kpi',
            role=User.Role.CEO,
            email='ceo_kpi@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_kpi',
            role=User.Role.HR,
            email='hr_kpi@example.com',
        )
        self.customer = Customer.objects.create(name='KPI Customer')

    def _create_order(self, *, amount, order_date, status_value):
        return Order.objects.create(
            customer=self.customer,
            created_by=self.sales_user,
            value_ron=Decimal(amount),
            date=order_date,
            status=status_value,
            channel=Order.Channel.WEBSITE,
        )

    def test_sales_dashboard_kpis_uses_today_yesterday_and_weekly_cancellations(self):
        self.client.force_authenticate(user=self.sales_user)

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())
        week_return_date = today - timedelta(days=1) if today.weekday() >= 1 else today

        self._create_order(amount='120.00', order_date=today, status_value=Order.Status.PROCESSING)
        self._create_order(amount='80.00', order_date=today, status_value=Order.Status.PROCESSING)
        self._create_order(amount='30.00', order_date=today, status_value=Order.Status.CANCELLED)

        self._create_order(amount='100.00', order_date=yesterday, status_value=Order.Status.DELIVERED)

        self._create_order(amount='15.00', order_date=week_return_date, status_value=Order.Status.CANCELLED)
        self._create_order(
            amount='22.00', order_date=start_of_week - timedelta(days=1), status_value=Order.Status.CANCELLED
        )

        response = self.client.get('/api/sales/dashboard/')

        today_orders = Order.objects.filter(date=today).count()
        today_revenue = Order.objects.filter(date=today).aggregate(total=Sum('value_ron'))['total'] or Decimal('0')
        yesterday_orders = Order.objects.filter(date=yesterday).count()
        yesterday_revenue = Order.objects.filter(date=yesterday).aggregate(total=Sum('value_ron'))['total'] or Decimal(
            '0'
        )
        processing_orders = Order.objects.filter(status=Order.Status.PROCESSING).count()
        returns_week = Order.objects.filter(
            status=Order.Status.CANCELLED,
            date__gte=start_of_week,
            date__lte=today,
        ).count()

        def pct_change(today_value, yesterday_value):
            today_numeric = float(today_value or 0)
            yesterday_numeric = float(yesterday_value or 0)
            if yesterday_numeric == 0:
                return 100.0 if today_numeric > 0 else 0.0
            return round(((today_numeric - yesterday_numeric) / yesterday_numeric) * 100, 2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['orders_today'], today_orders)
        self.assertEqual(Decimal(response.data['revenue_today_ron']), today_revenue)
        self.assertEqual(response.data['pending_orders'], processing_orders)
        self.assertEqual(response.data['returns_this_week'], returns_week)
        self.assertEqual(response.data['pct_changes']['orders'], pct_change(today_orders, yesterday_orders))
        self.assertEqual(response.data['pct_changes']['revenue'], pct_change(today_revenue, yesterday_revenue))

    def test_sales_dashboard_kpis_allows_ceo(self):
        self.client.force_authenticate(user=self.ceo_user)
        response = self.client.get('/api/sales/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sales_dashboard_kpis_forbids_other_roles(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get('/api/sales/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SalesAnalyticsTask3Tests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_task3',
            role=User.Role.SALES,
            email='sales_task3@example.com',
        )
        self.ceo_user = User.objects.create_user(
            username='ceo_task3',
            role=User.Role.CEO,
            email='ceo_task3@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_task3',
            role=User.Role.HR,
            email='hr_task3@example.com',
        )

        self.customer = Customer.objects.create(name='Task3 Customer')
        self.product_a = Product.objects.create(name='Widget A', sku='TASK3-A')
        self.product_b = Product.objects.create(name='Widget B', sku='TASK3-B')
        self.product_c = Product.objects.create(name='Widget C', sku='TASK3-C')

    def _create_order_with_item(self, *, order_date, product, quantity):
        order = Order.objects.create(
            customer=self.customer,
            created_by=self.sales_user,
            value_ron=Decimal('10.00'),
            date=order_date,
            status=Order.Status.DELIVERED,
            channel=Order.Channel.WEBSITE,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price_ron=Decimal('10.00'),
        )
        return order

    def test_daily_orders_returns_last_seven_days_with_zero_filled_gaps(self):
        self.client.force_authenticate(user=self.sales_user)

        today = timezone.localdate()
        five_days_ago = today - timedelta(days=5)
        two_days_ago = today - timedelta(days=2)

        self._create_order_with_item(order_date=five_days_ago, product=self.product_a, quantity=1)
        self._create_order_with_item(order_date=five_days_ago, product=self.product_b, quantity=1)
        self._create_order_with_item(order_date=two_days_ago, product=self.product_a, quantity=1)

        response = self.client.get('/api/sales/daily-orders/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('days', response.data)
        self.assertEqual(len(response.data['days']), 7)

        counts_by_date = {row['date']: row['orders_count'] for row in response.data['days']}
        self.assertEqual(counts_by_date[five_days_ago.isoformat()], 2)
        self.assertEqual(counts_by_date[two_days_ago.isoformat()], 1)
        self.assertEqual(counts_by_date[today.isoformat()], 0)

    def test_top_products_uses_current_iso_week_and_sorts_by_units_sold(self):
        self.client.force_authenticate(user=self.ceo_user)

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        previous_week_day = week_start - timedelta(days=1)

        self._create_order_with_item(order_date=today, product=self.product_a, quantity=5)
        self._create_order_with_item(order_date=today, product=self.product_b, quantity=2)
        self._create_order_with_item(order_date=week_start, product=self.product_b, quantity=3)
        self._create_order_with_item(order_date=previous_week_day, product=self.product_c, quantity=100)

        response = self.client.get('/api/sales/top-products/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['week_start'], week_start.isoformat())
        self.assertEqual(response.data['week_end'], week_end.isoformat())

        products = response.data['products']
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]['product_name'], 'Widget A')
        self.assertEqual(products[0]['units_sold'], 5)
        self.assertEqual(products[1]['product_name'], 'Widget B')
        self.assertEqual(products[1]['units_sold'], 5)

    def test_task3_endpoints_forbid_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        daily_response = self.client.get('/api/sales/daily-orders/')
        top_response = self.client.get('/api/sales/top-products/')

        self.assertEqual(daily_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(top_response.status_code, status.HTTP_403_FORBIDDEN)


from api.models import Invoice


class InvoiceListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_invoices',
            role=User.Role.SALES,
            email='sales_invoices@example.com',
        )
        self.hr_user = User.objects.create_user(
            username='hr_invoices',
            role=User.Role.HR,
            email='hr_invoices@example.com',
        )
        self.customer = Customer.objects.create(name='Invoice Customer')
        today = timezone.localdate()

        order_a = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('100.00'))
        order_b = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('200.00'))
        order_c = Order.objects.create(customer=self.customer, created_by=self.sales_user, value_ron=Decimal('300.00'))

        Invoice.objects.filter(order=order_a).update(status=Invoice.Status.PAID, amount_ron=Decimal('100.00'))
        Invoice.objects.filter(order=order_b).update(
            status=Invoice.Status.ISSUED, due_date=today - timedelta(days=1), amount_ron=Decimal('200.00')
        )
        Invoice.objects.filter(order=order_c).update(
            status=Invoice.Status.ISSUED, due_date=today + timedelta(days=7), amount_ron=Decimal('300.00')
        )

    def test_get_invoices_returns_summary_totals(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/invoices/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('paid_total', response.data)
        self.assertIn('pending_total', response.data)
        self.assertIn('overdue_total', response.data)
        self.assertEqual(Decimal(response.data['paid_total']), Decimal('100.00'))
        self.assertEqual(Decimal(response.data['overdue_total']), Decimal('200.00'))
        self.assertEqual(Decimal(response.data['pending_total']), Decimal('300.00'))

    def test_get_invoices_summary_totals_unaffected_by_status_filter(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/invoices/?status=Paid')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(Decimal(response.data['paid_total']), Decimal('100.00'))
        self.assertEqual(Decimal(response.data['overdue_total']), Decimal('200.00'))

    def test_get_invoices_forbids_non_sales_roles(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get('/api/invoices/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_order_creation_auto_creates_invoice_via_signal(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.post(
            '/api/orders/',
            {
                'customer': self.customer.id,
                'value_ron': '450.00',
                'date': timezone.localdate().isoformat(),
                'status': Order.Status.PROCESSING,
                'channel': Order.Channel.WEBSITE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data['id'])
        self.assertTrue(Invoice.objects.filter(order=order).exists())
        invoice = Invoice.objects.get(order=order)
        self.assertTrue(invoice.invoice_number.startswith('INV-'))
        self.assertEqual(invoice.amount_ron, Decimal('450.00'))


class CustomerListViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_cust', role=User.Role.SALES, email='sales_cust@example.com'
        )
        self.hr_user = User.objects.create_user(username='hr_cust', role=User.Role.HR, email='hr_cust@example.com')

        self.customer_a = Customer.objects.create(name='Alpha Corp', tier=Customer.Tier.GOLD)
        self.customer_b = Customer.objects.create(name='Beta Ltd', tier=Customer.Tier.SILVER)

        Order.objects.create(
            customer=self.customer_a,
            created_by=self.sales_user,
            value_ron=Decimal('500.00'),
            status=Order.Status.PROCESSING,
        )
        Order.objects.create(
            customer=self.customer_a,
            created_by=self.sales_user,
            value_ron=Decimal('300.00'),
            status=Order.Status.PROCESSING,
        )
        Order.objects.create(
            customer=self.customer_b,
            created_by=self.sales_user,
            value_ron=Decimal('100.00'),
            status=Order.Status.PROCESSING,
        )

    def test_customer_list_returns_orders_count_and_tier(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        alpha = next(r for r in results if r['name'] == 'Alpha Corp')
        self.assertEqual(alpha['orders_count'], 2)
        self.assertEqual(alpha['tier'], Customer.Tier.GOLD)

    def test_customer_list_sorted_by_total_value_desc(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        values = [Decimal(r['total_value_ron']) for r in results]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_customer_list_forbids_non_sales_role(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get('/api/customers/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CustomerDetailViewTests(APITestCase):
    def setUp(self):
        self.sales_user = User.objects.create_user(
            username='sales_detail', role=User.Role.SALES, email='sales_detail@example.com'
        )
        self.hr_user = User.objects.create_user(username='hr_detail', role=User.Role.HR, email='hr_detail@example.com')

        self.customer = Customer.objects.create(name='Detail Corp', contact_name='Jane Doe', tier=Customer.Tier.BRONZE)
        self.order = Order.objects.create(
            customer=self.customer, created_by=self.sales_user, value_ron=Decimal('250.00'), status=Order.Status.SHIPPED
        )

    def test_customer_detail_returns_order_history(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Detail Corp')
        self.assertEqual(response.data['contact_name'], 'Jane Doe')
        self.assertEqual(response.data['tier'], Customer.Tier.BRONZE)
        self.assertEqual(len(response.data['orders']), 1)
        self.assertEqual(response.data['orders'][0]['order_number'], self.order.order_number)

    def test_customer_detail_returns_404_for_missing_id(self):
        self.client.force_authenticate(user=self.sales_user)

        response = self.client.get('/api/customers/99999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_detail_forbids_non_sales_role(self):
        self.client.force_authenticate(user=self.hr_user)

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
