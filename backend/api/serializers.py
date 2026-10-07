from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import (
    Asset,
    ConversationMessage,
    ConversationSession,
    Customer,
    Department,
    Invoice,
    Notification,
    Order,
    OrderItem,
    Product,
    Report,
    StockMovement,
    Supplier,
    SystemStatus,
    Ticket,
    User,
    Workflow,
    WorkflowLog,
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'slug', 'icon', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True, required=False)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
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
        ]
        read_only_fields = ['id', 'created_at', 'assigned_to_username', 'assigned_to_name']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to is None:
            return None

        full_name = obj.assigned_to.get_full_name().strip()
        return full_name or obj.assigned_to.username


class EmployeeListSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'position',
            'employment_type',
            'start_date',
            'salary_ron',
            'address',
            'role',
            'is_active',
            'full_time',
            'department',
        ]

    def get_department(self, obj):
        if obj.department is None:
            return None
        return {
            'id': obj.department.id,
            'name': obj.department.name,
            'slug': obj.department.slug,
        }


class EmployeeDepartmentRoleMixin:
    @staticmethod
    def get_role_for_department(department, default_role):
        if department is None:
            return default_role

        department_slug = (getattr(department, 'slug', '') or '').strip().lower()
        department_name = (getattr(department, 'name', '') or '').strip().lower()

        if 'it' in department_slug or 'it' in department_name:
            return User.Role.IT
        if 'sales' in department_slug or 'sales' in department_name:
            return User.Role.SALES
        if 'hr' in department_slug or 'hr' in department_name:
            return User.Role.HR
        if 'inventory' in department_slug or 'inventory' in department_name:
            return User.Role.INVENTORY
        return default_role


class EmployeeCreateSerializer(EmployeeDepartmentRoleMixin, serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message='An employee with this email already exists.',
            )
        ]
    )

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'phone',
            'role',
            'department',
            'position',
            'employment_type',
            'start_date',
            'salary_ron',
            'address',
            'is_active',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone': {'required': True},
            'role': {'required': False},
            'department': {'required': True},
            'position': {'required': True},
            'employment_type': {'required': True},
            'start_date': {'required': True},
            'salary_ron': {'required': True},
            'address': {'required': True},
            'is_active': {'required': True},
        }

    def validate_phone(self, value):
        if not value.startswith('+40'):
            raise serializers.ValidationError('Phone number must start with +40.')
        return value

    def create(self, validated_data):
        email = validated_data.pop('email').lower().strip()
        base_username = email.split('@')[0] or 'employee'
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

        explicit_role = validated_data.pop('role', None)
        employment_type = validated_data.pop('employment_type', User.EmploymentType.FULL_TIME)
        validated_data['full_time'] = employment_type == User.EmploymentType.FULL_TIME

        department = validated_data.get('department')
        role = self.get_role_for_department(department, User.Role.SALES)

        if explicit_role:
            role = explicit_role

        user = User.objects.create(
            username=username,
            email=email,
            role=role,
            employment_type=employment_type,
            **validated_data,
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        return user


class EmployeeUpdateSerializer(EmployeeDepartmentRoleMixin, serializers.ModelSerializer):
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'position',
            'department',
            'phone',
            'is_active',
        ]

    def validate_phone(self, value):
        if value and not value.startswith('+40'):
            raise serializers.ValidationError('Phone number must start with +40.')
        return value

    def update(self, instance, validated_data):
        department = validated_data.get('department', instance.department)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.role = self.get_role_for_department(department, instance.role)
        instance.save()
        return instance


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'category', 'stock_count', 'min_stock', 'unit_price_ron', 'created_at']
        read_only_fields = ['id', 'created_at']


class SalesProductSerializer(serializers.ModelSerializer):
    availability = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'category', 'unit_price_ron', 'stock_count', 'availability']

    def get_availability(self, obj):
        return obj.availability


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact_email', 'contact_phone', 'address', 'created_at']
        read_only_fields = ['id', 'created_at']


class StockMovementSerializer(serializers.ModelSerializer):
    # Accept product and supplier as PKs on write, but include nested objects on read
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), allow_null=True, required=False)
    product_obj = ProductSerializer(source='product', read_only=True)
    supplier_obj = SupplierSerializer(source='supplier', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'movement_type',
            'product',
            'product_obj',
            'product_name',
            'product_sku',
            'supplier',
            'supplier_obj',
            'supplier_name',
            'quantity',
            'expected_date',
            'notes',
            'created_by',
            'created_by_username',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_by',
            'created_at',
            'product_obj',
            'supplier_obj',
            'product_name',
            'product_sku',
            'supplier_name',
            'created_by_username',
        ]

    def validate(self, data):
        movement_type = data.get('movement_type')
        quantity = data.get('quantity', 0)
        notes = data.get('notes', '').strip()

        if movement_type in [StockMovement.Type.ADJUSTMENT, StockMovement.Type.WRITE_OFF]:
            if not notes:
                raise serializers.ValidationError({'notes': 'Notes are required for adjustments and write-offs.'})

        if movement_type == StockMovement.Type.ADJUSTMENT:
            if quantity < 0:
                raise serializers.ValidationError({'quantity': 'Quantity cannot be negative.'})
        else:
            if quantity <= 0:
                raise serializers.ValidationError({'quantity': 'Quantity must be greater than zero.'})

        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and not validated_data.get('created_by'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'customer_name',
            'value_ron',
            'date',
            'status',
            'channel',
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'value_ron',
            'date',
            'status',
            'channel',
            'notes',
        ]
        read_only_fields = ['id', 'order_number']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class OrderItemDetailSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    line_total_ron = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'quantity',
            'unit_price_ron',
            'line_total_ron',
        ]

    def get_line_total_ron(self, obj):
        return obj.quantity * obj.unit_price_ron


class OrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    items = OrderItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer',
            'customer_name',
            'created_by',
            'created_by_username',
            'value_ron',
            'date',
            'status',
            'channel',
            'notes',
            'created_at',
            'updated_at',
            'items',
        ]


class CustomerSalesSummarySerializer(serializers.ModelSerializer):
    total_value_ron = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    orders_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'contact_name',
            'location',
            'tier',
            'orders_count',
            'total_value_ron',
        ]


class CustomerOrderHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'value_ron',
            'date',
            'status',
            'channel',
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    orders = CustomerOrderHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'contact_name',
            'contact_email',
            'contact_phone',
            'address',
            'location',
            'tier',
            'notes',
            'created_at',
            'updated_at',
            'orders',
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.name', read_only=True)
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'order',
            'order_number',
            'customer_name',
            'amount_ron',
            'status',
            'effective_status',
            'issued_date',
            'due_date',
        ]

    def get_effective_status(self, obj):
        today = timezone.localdate()
        if obj.due_date and obj.due_date < today and obj.status != Invoice.Status.PAID:
            return 'OVERDUE'
        return obj.status


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal_ron = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price_ron', 'subtotal_ron']

    def get_subtotal_ron(self, obj):
        return obj.quantity * obj.unit_price_ron


class InvoiceDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.name', read_only=True)
    line_items = InvoiceLineItemSerializer(source='order.items', many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'order',
            'order_number',
            'customer_name',
            'issued_date',
            'due_date',
            'status',
            'amount_ron',
            'line_items',
        ]


class TicketSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    requested_for_username = serializers.CharField(source='requested_for.username', read_only=True, allow_null=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_number',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'department',
            'department_name',
            'requested_by',
            'requested_by_username',
            'requested_for',
            'requested_for_username',
            'assigned_to',
            'assigned_to_username',
            'location',
            'created_at',
            'updated_at',
            'resolved_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at', 'resolved_at']


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_number',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'department',
            'requested_for',
            'assigned_to',
            'location',
            'requested_by',
            'created_at',
            'updated_at',
            'resolved_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'status', 'requested_by', 'created_at', 'updated_at', 'resolved_at']
        extra_kwargs = {
            'title': {'required': True, 'allow_blank': False},
            'description': {'required': True, 'allow_blank': False},
            'category': {'required': False},
            'priority': {'required': False},
            'department': {'required': False},
            'requested_for': {'required': False, 'allow_null': True},
            'assigned_to': {'required': False, 'allow_null': True},
            'location': {'required': False},
        }

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['requested_by'] = request.user
        validated_data['status'] = Ticket.Status.OPEN
        return super().create(validated_data)


class TicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'status', 'assigned_to', 'resolved_at']
        read_only_fields = ['id', 'resolved_at']

    def validate_status(self, value):
        if self.instance is None:
            return value

        current = self.instance.status
        allowed_transitions = {
            Ticket.Status.OPEN: [Ticket.Status.IN_PROGRESS],
            Ticket.Status.IN_PROGRESS: [Ticket.Status.RESOLVED],
            Ticket.Status.RESOLVED: [],
            Ticket.Status.CLOSED: [],
        }

        if value == current:
            return value

        if value not in allowed_transitions.get(current, []):
            raise serializers.ValidationError(f'Invalid transition from {current} to {value}.')

        return value

    def update(self, instance, validated_data):
        new_status = validated_data.get('status')
        if new_status == Ticket.Status.IN_PROGRESS and not validated_data.get('assigned_to'):
            request = self.context.get('request')
            if request and request.user and request.user.is_authenticated:
                validated_data['assigned_to'] = request.user

        return super().update(instance, validated_data)


class ReportSerializer(serializers.ModelSerializer):
    file_available = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'period',
            'file_size_kb',
            'generated_at',
            'file_available',
            'digest_data',
        ]

    def get_file_available(self, obj):
        return bool(obj.file_path)


class SystemStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemStatus
        fields = ['id', 'name', 'uptime_pct', 'status', 'last_incident_date', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageHistorySerializer(serializers.Serializer):
    """Serializer for a single message in conversation history."""

    role = serializers.ChoiceField(choices=['user', 'assistant'])
    content = serializers.CharField()


class AssistantChatRequestSerializer(serializers.Serializer):
    """Serializer for the assistant chat endpoint request."""

    message = serializers.CharField(required=True)
    history = ChatMessageHistorySerializer(many=True, required=False, allow_empty=True)
    current_page = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError('Message cannot be empty.')
        if len(value) > 4000:
            raise serializers.ValidationError('Message cannot exceed 4000 characters.')
        return value


class ToolCallSerializer(serializers.Serializer):
    """Serializer for tool calls made by the agent."""

    tool_name = serializers.CharField()
    arguments = serializers.JSONField()


class AssistantChatResponseSerializer(serializers.Serializer):
    """Serializer for the assistant chat endpoint response."""

    response = serializers.CharField()
    tool_calls_made = ToolCallSerializer(many=True, allow_empty=True)


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSessionSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ConversationSession
        fields = ['id', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ConversationSessionListSerializer(serializers.ModelSerializer):
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    preview = serializers.SerializerMethodField()

    def get_preview(self, obj):
        first = obj.messages.filter(role='user').first()
        return first.content[:80] if first else ''

    class Meta:
        model = ConversationSession
        fields = ['id', 'created_at', 'updated_at', 'message_count', 'preview']
        read_only_fields = fields


class WorkflowSerializer(serializers.ModelSerializer):
    trigger_label = serializers.SerializerMethodField()
    action_labels = serializers.SerializerMethodField()

    class Meta:
        model = Workflow
        fields = [
            'id',
            'name',
            'trigger_type',
            'trigger_label',
            'trigger_config',
            'actions',
            'action_labels',
            'is_active',
            'last_triggered_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'last_triggered_at', 'created_at', 'updated_at']

    def get_trigger_label(self, obj):
        return dict(Workflow.TriggerType.choices).get(obj.trigger_type, obj.trigger_type)

    def get_action_labels(self, obj):
        label_map = dict(Workflow.ActionType.choices)
        result = []
        for a in obj.actions or []:
            if isinstance(a, str):
                result.append(label_map.get(a, a))
            elif isinstance(a, dict):
                key = a.get('type') or a.get('action') or ''
                result.append(label_map.get(key, key))
        return result


class WorkflowWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = ['name', 'trigger_type', 'trigger_config', 'actions', 'is_active']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_trigger_type(self, value):
        valid = [c[0] for c in Workflow.TriggerType.choices]
        if value not in valid:
            raise serializers.ValidationError(f'Must be one of: {", ".join(valid)}')
        return value

    def validate_actions(self, value):
        if not value:
            raise serializers.ValidationError('Must have at least one action.')
        valid = [c[0] for c in Workflow.ActionType.choices]
        for a in value:
            if a not in valid:
                raise serializers.ValidationError(f'"{a}" is not a valid action type.')
        return value


class WorkflowLogSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)

    class Meta:
        model = WorkflowLog
        fields = ['id', 'workflow', 'workflow_name', 'triggered_at', 'trigger_type', 'actions_log', 'success']
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'body', 'is_read', 'link', 'created_at']
        read_only_fields = ['id', 'type', 'title', 'body', 'link', 'created_at']
