from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CEO = 'CEO', 'CEO'
        HR = 'HR', 'HR'
        SALES = 'SALES', 'Sales Rep'
        IT = 'IT', 'IT Technician'
        INVENTORY = 'INVENTORY', 'Inventory Manager'

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full-time'
        PART_TIME = 'PART_TIME', 'Part-time'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CEO,
    )
    department = models.ForeignKey(
        'Department',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    phone = models.CharField(max_length=20, default='')
    position = models.CharField(max_length=120, default='')
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    start_date = models.DateField(default=date.today)
    salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(default='')
    full_time = models.BooleanField(default=True)

    class Meta:
        db_table = 'users'


class Asset(models.Model):
    class Category(models.TextChoices):
        LAPTOP = 'LAPTOP', 'Laptop'
        MONITOR = 'MONITOR', 'Monitor'
        PHONE = 'PHONE', 'Phone'
        PERIPHERAL = 'PERIPHERAL', 'Peripheral'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        RETIRED = 'RETIRED', 'Retired'

    name = models.CharField(max_length=160)
    serial_number = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.name} ({self.serial_number})'


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    icon = models.CharField(max_length=40, default='Building2')
    created_at = models.DateTimeField(auto_now_add=True)

    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Customer(models.Model):
    class Tier(models.TextChoices):
        GOLD = 'Gold', 'Gold'
        SILVER = 'Silver', 'Silver'
        BRONZE = 'Bronze', 'Bronze'
        INDIVIDUAL = 'Individual', 'Individual'

    name = models.CharField(max_length=160)
    contact_name = models.CharField(max_length=160, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    location = models.CharField(max_length=160, blank=True, default='')
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.INDIVIDUAL)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    class Category(models.TextChoices):
        ELECTRONICS = 'Electronics', 'Electronics'
        FURNITURE = 'Furniture', 'Furniture'
        LIGHTING = 'Lighting', 'Lighting'
        ACCESSORIES = 'Accessories', 'Accessories'

    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.ELECTRONICS)
    unit_price_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_count = models.PositiveIntegerField(default=0)
    min_stock = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def availability(self):
        stock = int(self.stock_count or 0)
        if stock <= 0:
            return 'Out of Stock'
        if stock < int(self.min_stock or 0):
            return 'Low Stock'
        return 'In Stock'

    def __str__(self) -> str:
        return f'{self.name} ({self.sku})'


class Order(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'PROCESSING', 'Processing'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Channel(models.TextChoices):
        EMAG = 'EMAG', 'eMAG'
        WEBSITE = 'WEBSITE', 'Website'
        DIRECT = 'DIRECT', 'Direct'

    order_number = models.CharField(max_length=32, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders_created')
    value_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.WEBSITE)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            last_order_number = (
                Order.objects.filter(order_number__startswith='#')
                .order_by('-id')
                .values_list('order_number', flat=True)
                .first()
            )

            next_number = 1
            if last_order_number:
                raw = last_order_number[1:]
                if raw.isdigit():
                    next_number = int(raw) + 1

            self.order_number = f'#{next_number:04d}'

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [('order', 'product')]


class Supplier(models.Model):
    name = models.CharField(max_length=160)
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class StockMovement(models.Model):
    class Type(models.TextChoices):
        INBOUND = 'INBOUND', 'Inbound'
        OUTBOUND = 'OUTBOUND', 'Outbound'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        WRITE_OFF = 'WRITE_OFF', 'Write-off'

    movement_type = models.CharField(max_length=12, choices=Type.choices)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_movements')
    # supplier is optional for adjustments or write-offs where supplier may not apply
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements'
    )
    quantity = models.PositiveIntegerField(default=0)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='stock_movements_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # on create, apply the stock change to the product
        is_create = self.pk is None
        super().save(*args, **kwargs)
        if is_create:
            try:
                if self.movement_type == StockMovement.Type.INBOUND:
                    # increment product stock
                    self.product.stock_count = (getattr(self.product, 'stock_count', 0) or 0) + int(self.quantity)
                    self.product.save(update_fields=['stock_count'])
                elif self.movement_type in (StockMovement.Type.OUTBOUND, StockMovement.Type.WRITE_OFF):
                    # decrement product stock (not below zero)
                    new_count = max(0, (getattr(self.product, 'stock_count', 0) or 0) - int(self.quantity))
                    self.product.stock_count = new_count
                    self.product.save(update_fields=['stock_count'])
                    self._evaluate_stock_workflows()
                elif self.movement_type == StockMovement.Type.ADJUSTMENT:
                    old_count = getattr(self.product, 'stock_count', 0) or 0
                    self.product.stock_count = int(self.quantity)
                    self.product.save(update_fields=['stock_count'])
                    if self.product.stock_count < old_count:
                        self._evaluate_stock_workflows()
            except Exception:
                # Don't let product save failures block the movement creation; log later if needed
                pass

    def _evaluate_stock_workflows(self):
        from django.utils import timezone

        workflows = Workflow.objects.filter(trigger_type=Workflow.TriggerType.STOCK_BELOW_MINIMUM, is_active=True)
        for wf in workflows:
            config = wf.trigger_config or {}
            target_product_id = config.get('product_id')
            if target_product_id and str(target_product_id) != str(self.product.id):
                continue

            threshold = config.get('threshold', getattr(self.product, 'min_stock', 10))
            if self.product.stock_count < int(threshold):
                actions_log = []
                for action in wf.actions:
                    act_type = action.get('type', str(action)) if isinstance(action, dict) else str(action)
                    actions_log.append(
                        {
                            'action': act_type,
                            'status': 'success',
                            'message': f'Executed {act_type} for product {self.product.name} (stock {self.product.stock_count} < threshold {threshold})',
                        }
                    )

                WorkflowLog.objects.create(
                    workflow=wf, trigger_type=wf.trigger_type, actions_log=actions_log, success=True
                )
                wf.last_triggered_at = timezone.now()
                wf.save(update_fields=['last_triggered_at'])


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ISSUED = 'ISSUED', 'Issued'
        PAID = 'PAID', 'Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'

    invoice_number = models.CharField(max_length=32, unique=True)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='invoices')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoices_issued')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    amount_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        REMOTE = 'REMOTE', 'Remote'
        LEAVE = 'LEAVE', 'Leave'

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField(default=date.today)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PRESENT)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'date')]
        ordering = ['-date']


class LeaveRequest(models.Model):
    class Type(models.TextChoices):
        VACATION = 'VACATION', 'Vacation'
        SICK = 'SICK', 'Sick'
        UNPAID = 'UNPAID', 'Unpaid'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests'
    )
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.VACATION)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_requests_approved'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Contract(models.Model):
    class Type(models.TextChoices):
        EMPLOYMENT = 'EMPLOYMENT', 'Employment'
        CONTRACTOR = 'CONTRACTOR', 'Contractor'

    contract_number = models.CharField(max_length=40, unique=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contracts')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts'
    )
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.EMPLOYMENT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PayrollEntry(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_entries')
    month = models.DateField(help_text='Any date within the payroll month')
    gross_salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary_ron = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('employee', 'month')]


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = 'INFO', 'Info'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=16, choices=Type.choices, default=Type.INFO)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default='')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    ticket_number = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=80, blank=True, default='')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tickets_requested')
    requested_for = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_requested_for'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_assigned'
    )
    location = models.CharField(max_length=160, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def _generate_ticket_number(cls):
        max_number = 0
        for ticket_number in cls.objects.values_list('ticket_number', flat=True):
            if not ticket_number or not ticket_number.startswith('TKT-'):
                continue

            numeric_part = ticket_number.split('TKT-', 1)[1]
            if numeric_part.isdigit():
                max_number = max(max_number, int(numeric_part))

        return f'TKT-{(max_number + 1):05d}'

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()

        if self.status == self.Status.RESOLVED and self.resolved_at is None:
            from django.utils import timezone

            self.resolved_at = timezone.now()

        super().save(*args, **kwargs)


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ticket_comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Workflow(models.Model):
    class TriggerType(models.TextChoices):
        STOCK_BELOW_MINIMUM = 'STOCK_BELOW_MINIMUM', 'Stock Below Minimum'
        NEW_ORDER_RECEIVED = 'NEW_ORDER_RECEIVED', 'New Order Received'
        DAILY_AT_TIME = 'DAILY_AT_TIME', 'Daily At Time'
        WEEKLY_AT_TIME = 'WEEKLY_AT_TIME', 'Weekly At Time'
        NEW_IT_TICKET = 'NEW_IT_TICKET', 'New IT Ticket'
        CONTRACT_EXPIRES = 'CONTRACT_EXPIRES', 'Contract Expires'
        ORDER_EXCEEDS_THRESHOLD = 'ORDER_EXCEEDS_THRESHOLD', 'Order Exceeds Threshold'

    class ActionType(models.TextChoices):
        EMAIL_SUPPLIER = 'EMAIL_SUPPLIER', 'Email Supplier'
        NOTIFY_MANAGER = 'NOTIFY_MANAGER', 'Notify Manager'
        SEND_CONFIRMATION_EMAIL = 'SEND_CONFIRMATION_EMAIL', 'Send Confirmation Email'
        UPDATE_DASHBOARD = 'UPDATE_DASHBOARD', 'Update Dashboard'
        GENERATE_REPORT = 'GENERATE_REPORT', 'Generate Report'
        EMAIL_CEO = 'EMAIL_CEO', 'Email CEO'
        ASSIGN_TO_TEAM_LEAD = 'ASSIGN_TO_TEAM_LEAD', 'Assign to Team Lead'
        POST_TO_CHANNEL = 'POST_TO_CHANNEL', 'Post to Channel'
        LOG_TO_AUDIT_TRAIL = 'LOG_TO_AUDIT_TRAIL', 'Log to Audit Trail'

    name = models.CharField(max_length=160)
    trigger_type = models.CharField(max_length=64, choices=TriggerType.choices, blank=True, default='')
    trigger_config = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WorkflowLog(models.Model):
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='logs')
    triggered_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(max_length=64, blank=True, default='')
    actions_log = models.JSONField(default=list, blank=True)
    success = models.BooleanField(default=True)


class SystemStatistic(models.Model):
    name = models.CharField(max_length=160, unique=True)
    value = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SystemStatus(models.Model):
    class StatusChoices(models.TextChoices):
        ONLINE = 'ONLINE', 'Online'
        DEGRADED = 'DEGRADED', 'Degraded'
        OFFLINE = 'OFFLINE', 'Offline'

    name = models.CharField(max_length=160, unique=True)
    uptime_pct = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    status = models.CharField(max_length=12, choices=StatusChoices.choices, default=StatusChoices.ONLINE)
    last_incident_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.status}'


class Report(models.Model):
    class Category(models.TextChoices):
        SALES = 'Sales', 'Sales'
        FINANCE = 'Finance', 'Finance'
        INVENTORY = 'Inventory', 'Inventory'
        HR = 'HR', 'HR'
        IT = 'IT', 'IT'

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=100, unique=True, default='')
    category = models.CharField(max_length=20, choices=Category.choices, blank=True, default='')
    period = models.CharField(max_length=80, blank=True, default='')
    file_path = models.CharField(max_length=255, blank=True, default='')
    file_size_kb = models.IntegerField(default=0)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_generated'
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    # Store digest data as JSON (for HR digest or similar structured reports)
    digest_data = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return self.name


class ConversationSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Session {self.id} — {self.user.username}'


class ConversationMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    session = models.ForeignKey(ConversationSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:60]}'
