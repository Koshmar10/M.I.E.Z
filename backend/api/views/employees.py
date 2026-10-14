"""Departments and the employee directory (HR, IT and CEO)."""

from django.db.models import (
    Count,
    Q,
)
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Department,
    User,
)
from ..pagination import StandardPagination
from ..permissions import role_required
from ..serializers.employees import (
    DepartmentSerializer,
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeUpdateSerializer,
)


class DepartmentListCreateView(APIView):
    permission_classes = [
        IsAuthenticated,
        role_required(get=[User.Role.CEO, User.Role.HR], post=[User.Role.CEO]),
    ]

    def get(self, request):
        departments = Department.objects.all()
        serializer = DepartmentSerializer(departments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DepartmentDeleteView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO)]

    def delete(self, request, id):
        department = get_object_or_404(Department, id=id)
        department.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeListView(APIView):
    permission_classes = [
        IsAuthenticated,
        role_required(get=[User.Role.CEO, User.Role.HR, User.Role.IT], post=[User.Role.CEO, User.Role.HR]),
    ]

    def get(self, request):
        queryset = User.objects.select_related('department').all().order_by('id')

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(username__icontains=search)
            )

        department_filter = request.query_params.get('department')
        if department_filter:
            if department_filter.isdigit():
                queryset = queryset.filter(department_id=int(department_filter))
            else:
                queryset = queryset.filter(department__slug=department_filter)

        is_active_filter = request.query_params.get('is_active')
        if is_active_filter is not None:
            normalized = is_active_filter.strip().lower()
            if normalized in ['true', '1', 'yes']:
                queryset = queryset.filter(is_active=True)
            elif normalized in ['false', '0', 'no']:
                queryset = queryset.filter(is_active=False)

        paginator = StandardPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = EmployeeListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        response_serializer = EmployeeListSerializer(employee)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request, id):
        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeListSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeUpdateSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmployeeListSerializer(employee).data, status=status.HTTP_200_OK)


class EmployeeStatsView(APIView):
    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

    def get(self, request):
        base = User.objects.select_related('department').all()

        stats = base.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            full_time=Count('id', filter=Q(full_time=True)),
        )

        department_rows = base.values('department__name').annotate(count=Count('id')).order_by('department__name')

        departments = [
            {'name': row['department__name'] or 'Unassigned', 'count': row['count']} for row in department_rows
        ]

        return Response(
            {
                'total': stats['total'],
                'active': stats['active'],
                'full_time': stats['full_time'],
                'departments': departments,
            },
            status=status.HTTP_200_OK,
        )
