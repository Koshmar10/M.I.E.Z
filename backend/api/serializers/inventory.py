"""Serializers for products, suppliers and stock movements."""

from rest_framework import serializers

from ..models import (
    Product,
    StockMovement,
    Supplier,
)


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'category', 'stock_count', 'min_stock', 'unit_price_ron', 'created_at']
        read_only_fields = ['id', 'created_at']


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

        if movement_type in [StockMovement.Type.ADJUSTMENT, StockMovement.Type.WRITE_OFF] and not notes:
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
