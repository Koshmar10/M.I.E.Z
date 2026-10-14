"""Serializers for departments and employees."""

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import (
    Department,
    User,
)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'slug', 'icon', 'created_at']
        read_only_fields = ['id', 'created_at']


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
