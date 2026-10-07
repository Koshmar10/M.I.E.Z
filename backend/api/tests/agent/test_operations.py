"""Tests for the assistant tools in api/agent/operations.py."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from api.agent.operations import (
    create_leave_request,
    create_ticket,
    generate_report,
    get_attendance_trend,
    get_dashboard_summary,
    get_headcount_vs_workload,
    get_leave_patterns,
    query_employees,
    query_inventory,
    query_orders,
    query_tickets,
)
from api.models import (
    Attendance,
    Customer,
    Department,
    LeaveRequest,
    Order,
    Product,
    Report,
    Ticket,
    User,
)


class AssistantToolTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='Sales', slug='sales')
        self.hr_department = Department.objects.create(name='Human Resources', slug='hr')

        self.ceo = User.objects.create_user(username='ceo', email='ceo@example.com', role=User.Role.CEO)
        self.hr_user = User.objects.create_user(
            username='hr', email='hr@example.com', role=User.Role.HR, department=self.hr_department
        )
        self.hr_manager = User.objects.create_user(
            username='hr-manager',
            email='hr-manager@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            position='HR Manager',
        )
        self.sales_user = User.objects.create_user(
            username='sales', email='sales@example.com', role=User.Role.SALES, department=self.department
        )
        self.it_user = User.objects.create_user(username='it', email='it@example.com', role=User.Role.IT)

    def _kpi(self, summary, label):
        return next(k['value'] for k in summary['kpis'] if k['label'] == label)

    def test_get_dashboard_summary_sales_returns_standard_envelope(self):
        customer = Customer.objects.create(name='Acme Corp')
        today = timezone.localdate()

        Order.objects.create(
            customer=customer,
            created_by=self.sales_user,
            value_ron='100.00',
            date=today,
            status=Order.Status.PROCESSING,
        )

        summary = get_dashboard_summary(module='sales', user=self.sales_user)

        self.assertEqual(set(summary.keys()), {'module', 'kpis', 'generated_at'})
        self.assertEqual(summary['module'], 'sales')
        self.assertIsInstance(summary['kpis'], list)
        self.assertTrue(all('label' in k and 'value' in k for k in summary['kpis']))
        self.assertEqual(self._kpi(summary, 'Orders Today'), 1)
        self.assertEqual(self._kpi(summary, 'Revenue Today (RON)'), '100.00')

    def test_get_dashboard_summary_hr_returns_standard_envelope(self):
        summary = get_dashboard_summary(module='hr', user=self.hr_user)

        self.assertEqual(set(summary.keys()), {'module', 'kpis', 'generated_at'})
        self.assertEqual(summary['module'], 'hr')
        self.assertIsInstance(summary['kpis'], list)

    def test_get_dashboard_summary_it_returns_standard_envelope(self):
        Ticket.objects.create(
            ticket_number='TKT-D-001', title='Open ticket', status=Ticket.Status.OPEN, requested_by=self.it_user
        )

        summary = get_dashboard_summary(module='it', user=self.it_user)

        self.assertEqual(set(summary.keys()), {'module', 'kpis', 'generated_at'})
        self.assertEqual(summary['module'], 'it')
        self.assertEqual(self._kpi(summary, 'Open Tickets'), 1)

    def test_get_dashboard_summary_inventory_returns_standard_envelope(self):
        inventory_user = User.objects.create_user(username='inv', email='inv@example.com', role=User.Role.INVENTORY)
        Product.objects.create(name='Widget', sku='WGT-01', stock_count=0, min_stock=5, unit_price_ron='9.99')

        summary = get_dashboard_summary(module='inventory', user=inventory_user)

        self.assertEqual(set(summary.keys()), {'module', 'kpis', 'generated_at'})
        self.assertEqual(summary['module'], 'inventory')
        self.assertEqual(self._kpi(summary, 'Out of Stock'), 1)

    def test_get_dashboard_summary_ceo_can_access_any_module(self):
        for mod in ['sales', 'hr', 'it', 'inventory']:
            summary = get_dashboard_summary(module=mod, user=self.ceo)
            self.assertEqual(summary['module'], mod)

    def test_get_dashboard_summary_hr_denied_for_sales_role(self):
        with self.assertRaises(PermissionError):
            get_dashboard_summary(module='hr', user=self.sales_user)

    def test_get_dashboard_summary_invalid_module_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_dashboard_summary(module='finance', user=self.ceo)

    def test_query_tickets_new_returns_only_open_tickets(self):
        ticket_one = Ticket.objects.create(
            ticket_number='TKT-00001', title='Printer issue', status=Ticket.Status.OPEN, requested_by=self.it_user
        )
        Ticket.objects.create(
            ticket_number='TKT-00002',
            title='Network issue',
            status=Ticket.Status.IN_PROGRESS,
            requested_by=self.it_user,
        )

        results = query_tickets(status='NEW', user=self.it_user)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], ticket_one.id)
        self.assertTrue(all(item['status'] == 'NEW' for item in results))

    def test_query_tickets_filters_priority_assigned_and_limit(self):
        assigned = User.objects.create_user(
            username='assigned-tech', email='assigned-tech@example.com', role=User.Role.IT
        )
        for index in range(12):
            Ticket.objects.create(
                ticket_number=f'TKT-2{index:04d}',
                title=f'Ticket {index}',
                status=Ticket.Status.OPEN,
                priority=Ticket.Priority.HIGH,
                assigned_to=assigned,
                requested_by=self.it_user,
            )

        Ticket.objects.create(
            ticket_number='TKT-99998',
            title='Non matching priority',
            status=Ticket.Status.OPEN,
            priority=Ticket.Priority.LOW,
            assigned_to=assigned,
            requested_by=self.it_user,
        )

        results = query_tickets(
            user=self.it_user,
            status='NEW',
            priority='HIGH',
            assigned_to=assigned.id,
            limit=50,
        )

        self.assertEqual(len(results), 10)
        self.assertTrue(all(item['status'] == 'NEW' for item in results))

    def test_query_orders_filters_and_caps_at_ten(self):
        customer_target = Customer.objects.create(name='Acme Retail')
        customer_other = Customer.objects.create(name='Other Corp')

        for _ in range(12):
            Order.objects.create(
                customer=customer_target,
                created_by=self.sales_user,
                value_ron='250.00',
                status=Order.Status.PROCESSING,
                channel=Order.Channel.WEBSITE,
            )

        Order.objects.create(
            customer=customer_target,
            created_by=self.sales_user,
            value_ron='100.00',
            status=Order.Status.SHIPPED,
            channel=Order.Channel.WEBSITE,
        )
        Order.objects.create(
            customer=customer_other,
            created_by=self.sales_user,
            value_ron='100.00',
            status=Order.Status.PROCESSING,
            channel=Order.Channel.DIRECT,
        )

        results = query_orders(
            user=self.sales_user,
            status='PROCESSING',
            channel='WEBSITE',
            customer='Acme',
            limit=20,
        )

        self.assertEqual(len(results), 10)
        self.assertTrue(all(item['status'] == Order.Status.PROCESSING for item in results))
        self.assertTrue(all(item['channel'] == Order.Channel.WEBSITE for item in results))
        self.assertTrue(all('Acme' in item['customer_name'] for item in results))

    def test_query_employees_denied_for_sales_role(self):
        with self.assertRaises(PermissionError):
            query_employees(user=self.sales_user)

    def test_query_employees_filters_department_role_active_and_limit(self):
        for index in range(12):
            User.objects.create_user(
                username=f'sales-emp-{index}',
                email=f'sales-emp-{index}@example.com',
                role=User.Role.SALES,
                department=self.department,
                is_active=True,
            )

        User.objects.create_user(
            username='sales-inactive',
            email='sales-inactive@example.com',
            role=User.Role.SALES,
            department=self.department,
            is_active=False,
        )
        User.objects.create_user(
            username='hr-active',
            email='hr-active@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            is_active=True,
        )

        results = query_employees(
            user=self.hr_user,
            department=self.department.slug,
            role='SALES',
            is_active=True,
            limit=99,
        )

        self.assertEqual(len(results), 10)
        self.assertTrue(all(item['role'] == User.Role.SALES for item in results))
        self.assertTrue(all(item['is_active'] for item in results))
        self.assertTrue(all(item['department']['slug'] == self.department.slug for item in results))

    def test_query_inventory_filters_status_category_below_min_and_limit(self):
        for index in range(12):
            Product.objects.create(
                name=f'Inventory Item {index}',
                sku=f'SKU-INV-{index}',
                category=Product.Category.ELECTRONICS,
                stock_count=2,
                min_stock=10,
                unit_price_ron='10.00',
            )

        Product.objects.create(
            name='Accessories Item',
            sku='SKU-ACC-1',
            category=Product.Category.ACCESSORIES,
            stock_count=2,
            min_stock=10,
            unit_price_ron='5.00',
        )
        Product.objects.create(
            name='Stock Healthy Item',
            sku='SKU-INV-OK',
            category=Product.Category.ELECTRONICS,
            stock_count=30,
            min_stock=10,
            unit_price_ron='20.00',
        )

        inventory_user = User.objects.create_user(
            username='inventory-manager',
            email='inventory-manager@example.com',
            role=User.Role.INVENTORY,
        )

        results = query_inventory(
            user=inventory_user,
            status='low_stock',
            category='Electronics',
            below_min_stock=True,
            limit=50,
        )

        self.assertEqual(len(results), 10)
        self.assertTrue(all(item['status'] == 'Low Stock' for item in results))
        self.assertTrue(all(item['category'] == Product.Category.ELECTRONICS for item in results))

    def test_create_ticket_returns_ticket_number_and_status(self):
        result = create_ticket(
            user=self.sales_user,
            title='Laptop replacement',
            description='Battery no longer holds charge',
            category='Hardware',
            location='HQ',
        )

        self.assertIn('ticket_number', result)
        self.assertEqual(result['status'], Ticket.Status.OPEN)
        ticket = Ticket.objects.get(ticket_number=result['ticket_number'])
        self.assertEqual(ticket.requested_by, self.sales_user)

    def test_create_ticket_available_to_all_roles(self):
        for user in [self.ceo, self.hr_user, self.sales_user, self.it_user]:
            result = create_ticket(user=user, title=f'Ticket by {user.username}')
            self.assertIn('ticket_number', result)

    def test_create_leave_request_returns_id_and_pending_status(self):
        employee = User.objects.create_user(
            username='employee',
            email='employee@example.com',
            role=User.Role.SALES,
            department=self.department,
        )

        result = create_leave_request(
            user=self.hr_user,
            employee=employee.id,
            from_date=timezone.localdate() + timedelta(days=1),
            to_date=timezone.localdate() + timedelta(days=3),
            reason='Vacation',
        )

        self.assertIn('id', result)
        self.assertEqual(result['status'], LeaveRequest.Status.PENDING)
        self.assertEqual(LeaveRequest.objects.get(id=result['id']).employee_id, employee.id)

    def test_create_leave_request_defaults_employee_to_requesting_user(self):
        result = create_leave_request(
            user=self.sales_user,
            from_date=timezone.localdate() + timedelta(days=1),
            to_date=timezone.localdate() + timedelta(days=3),
        )

        self.assertEqual(result['status'], LeaveRequest.Status.PENDING)
        self.assertEqual(LeaveRequest.objects.get(id=result['id']).employee, self.sales_user)

    def test_create_leave_request_denied_for_ceo(self):
        with self.assertRaises(PermissionError):
            create_leave_request(
                user=self.ceo,
                from_date=timezone.localdate() + timedelta(days=1),
                to_date=timezone.localdate() + timedelta(days=3),
            )

    def test_generate_report_denied_for_non_manager_role(self):
        report = Report.objects.create(
            name='Sales Report',
            slug='sales-report',
            category='Sales',
            period='May 2026',
        )

        with self.assertRaises(PermissionError):
            generate_report(user=self.sales_user, slug=report.slug)

    def test_get_attendance_trend_flags_low_department_attendance_and_repeated_absence(self):
        today = timezone.localdate()
        current_week_start = today - timedelta(days=today.weekday())

        hr_employee = User.objects.create_user(
            username='hr-employee',
            email='hr-employee@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            first_name='Ana',
            last_name='Popa',
        )
        hr_leave_employee = User.objects.create_user(
            username='hr-leave',
            email='hr-leave@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            first_name='Maria',
            last_name='Ionescu',
        )

        # 4 unexcused absences in current week for repeated absence flag.
        for offset in range(4):
            Attendance.objects.create(
                employee=hr_employee,
                date=current_week_start + timedelta(days=offset),
                status=Attendance.Status.ABSENT,
            )

        # Approved leave is tracked separately from unexcused absence.
        Attendance.objects.create(
            employee=hr_leave_employee,
            date=current_week_start,
            status=Attendance.Status.LEAVE,
        )

        # Add one present record so total is non-zero while attendance remains below threshold.
        Attendance.objects.create(
            employee=hr_employee,
            date=current_week_start + timedelta(days=4),
            status=Attendance.Status.PRESENT,
        )

        result = get_attendance_trend(user=self.hr_user, weeks=4)

        self.assertIsInstance(result, list)
        self.assertTrue(result)

        hr_current_week = next(
            row
            for row in result
            if row['department'] == self.hr_department.name and row['week'] == current_week_start.isoformat()
        )

        self.assertLess(hr_current_week['attendance_pct'], 85.0)
        self.assertTrue(hr_current_week['flag_low_attendance'])
        self.assertEqual(hr_current_week['approved_leave_count'], 1)
        self.assertEqual(hr_current_week['unexcused_absence_count'], 4)

        unexcused_entry = next(
            item for item in hr_current_week['employees_absent'] if item['absence_type'] == 'unexcused'
        )
        approved_entry = next(
            item for item in hr_current_week['employees_absent'] if item['absence_type'] == 'approved_leave'
        )

        self.assertEqual(unexcused_entry['name'], 'Ana Popa')
        self.assertEqual(unexcused_entry['count'], 4)
        self.assertTrue(unexcused_entry['flag_repeated_absence'])
        self.assertEqual(approved_entry['name'], 'Maria Ionescu')
        self.assertEqual(approved_entry['count'], 1)
        self.assertFalse(approved_entry['flag_repeated_absence'])

    def test_get_attendance_trend_denied_for_sales_role(self):
        with self.assertRaises(PermissionError):
            get_attendance_trend(user=self.sales_user, weeks=4)

    def test_get_leave_patterns_detects_monday_friday_medical_and_rejection_follow_up(self):
        today = timezone.localdate()
        now = timezone.now()

        hr_employee = User.objects.create_user(
            username='pattern-employee',
            email='pattern-employee@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            first_name='Ana',
            last_name='Popescu',
        )
        medical_employee = User.objects.create_user(
            username='medical-employee',
            email='medical-employee@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            first_name='Maria',
            last_name='Ionescu',
        )
        rejected_employee = User.objects.create_user(
            username='rejected-employee',
            email='rejected-employee@example.com',
            role=User.Role.HR,
            department=self.hr_department,
            first_name='Elena',
            last_name='Marin',
        )

        monday_dates = [today - timedelta(days=today.weekday() + 7 * index) for index in range(3)]
        for index, request_date in enumerate(monday_dates):
            request = LeaveRequest.objects.create(
                employee=hr_employee,
                department=self.hr_department,
                type=LeaveRequest.Type.VACATION,
                from_date=request_date,
                to_date=request_date + timedelta(days=1),
                reason=f'Monday leave {index}',
            )
            LeaveRequest.objects.filter(pk=request.pk).update(
                created_at=now - timedelta(weeks=index, days=today.weekday())
            )

        medical_dates = [today - timedelta(days=1), today - timedelta(days=4), today - timedelta(days=10)]
        for index, request_date in enumerate(medical_dates):
            request = LeaveRequest.objects.create(
                employee=medical_employee,
                department=self.hr_department,
                type=LeaveRequest.Type.SICK,
                from_date=request_date,
                to_date=request_date + timedelta(days=1),
                reason=f'Medical leave {index}',
            )
            LeaveRequest.objects.filter(pk=request.pk).update(created_at=now - timedelta(days=index * 3))

        rejected_request = LeaveRequest.objects.create(
            employee=rejected_employee,
            department=self.hr_department,
            type=LeaveRequest.Type.VACATION,
            from_date=today - timedelta(days=14),
            to_date=today - timedelta(days=12),
            reason='First request',
            status=LeaveRequest.Status.REJECTED,
        )
        follow_up_request = LeaveRequest.objects.create(
            employee=rejected_employee,
            department=self.hr_department,
            type=LeaveRequest.Type.VACATION,
            from_date=today - timedelta(days=7),
            to_date=today - timedelta(days=5),
            reason='Follow up request',
            status=LeaveRequest.Status.PENDING,
        )
        LeaveRequest.objects.filter(pk=rejected_request.pk).update(created_at=now - timedelta(days=10))
        LeaveRequest.objects.filter(pk=follow_up_request.pk).update(created_at=now - timedelta(days=2))

        observations = get_leave_patterns(user=self.hr_user, weeks=8)

        self.assertIsInstance(observations, list)
        self.assertTrue(observations)

        monday_pattern = next(item for item in observations if item['pattern_type'] == 'monday_friday_leave_requests')
        medical_pattern = next(item for item in observations if item['pattern_type'] == 'medical_leave_cluster')
        rejection_pattern = next(item for item in observations if item['pattern_type'] == 'leave_after_rejection')

        self.assertEqual(monday_pattern['employee_name'], 'Ana Popescu')
        self.assertEqual(monday_pattern['occurrences'], 3)
        self.assertIn('Observation:', monday_pattern['description'])

        self.assertEqual(medical_pattern['department'], self.hr_department.name)
        self.assertEqual(medical_pattern['occurrences'], 3)
        self.assertIn('Observation:', medical_pattern['description'])

        self.assertEqual(rejection_pattern['employee_name'], 'Elena Marin')
        self.assertIn('Observation:', rejection_pattern['description'])

    def test_get_leave_patterns_denied_for_sales_role(self):
        with self.assertRaises(PermissionError):
            get_leave_patterns(user=self.sales_user, weeks=8)

    def test_get_headcount_vs_workload_returns_ratios_and_threshold_statuses(self):
        today = timezone.localdate()

        for index in range(1):
            User.objects.create_user(
                username=f'sales-active-{index}',
                email=f'sales-active-{index}@example.com',
                role=User.Role.SALES,
                department=self.department,
                is_active=True,
            )

        for index in range(4):
            User.objects.create_user(
                username=f'inventory-active-{index}',
                email=f'inventory-active-{index}@example.com',
                role=User.Role.INVENTORY,
                is_active=True,
            )

        customer = Customer.objects.create(name='Acme Corp')
        for _ in range(11):
            Order.objects.create(
                customer=customer,
                created_by=self.sales_user,
                value_ron='100.00',
                status=Order.Status.PROCESSING,
            )

        for index in range(12):
            Ticket.objects.create(
                ticket_number=f'TKT-WL-{index:04d}',
                title=f'Open ticket {index}',
                status=Ticket.Status.OPEN,
                requested_by=self.it_user,
            )

        from api.models import Product, StockMovement, Supplier

        product = Product.objects.create(name='Keyboard', sku='KB-001', unit_price_ron='20.00')
        supplier = Supplier.objects.create(name='Default Supplier')
        for index in range(8):
            StockMovement.objects.create(
                movement_type=StockMovement.Type.INBOUND,
                product=product,
                supplier=supplier,
                quantity=1,
                expected_date=today + timedelta(days=index + 1),
                created_by=self.ceo,
            )

        results = get_headcount_vs_workload(user=self.hr_user)

        self.assertEqual([item['department'] for item in results], ['Sales', 'IT', 'Inventory'])

        sales_row = next(item for item in results if item['department'] == 'Sales')
        it_row = next(item for item in results if item['department'] == 'IT')
        inventory_row = next(item for item in results if item['department'] == 'Inventory')

        self.assertEqual(sales_row['active_headcount'], 2)
        self.assertEqual(sales_row['workload_items'], 11)
        self.assertEqual(sales_row['ratio'], 5.5)
        self.assertEqual(sales_row['status'], 'warning')

        self.assertEqual(it_row['active_headcount'], 1)
        self.assertEqual(it_row['workload_items'], 12)
        self.assertEqual(it_row['ratio'], 12.0)
        self.assertEqual(it_row['status'], 'critical')

        self.assertEqual(inventory_row['active_headcount'], 4)
        self.assertEqual(inventory_row['workload_items'], 8)
        self.assertEqual(inventory_row['ratio'], 2.0)
        self.assertEqual(inventory_row['status'], 'ok')

    def test_get_headcount_vs_workload_denied_for_sales_role(self):
        with self.assertRaises(PermissionError):
            get_headcount_vs_workload(user=self.sales_user)
