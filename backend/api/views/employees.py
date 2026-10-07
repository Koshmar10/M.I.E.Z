"""Departments and the employee directory (HR, IT and CEO)."""

from django.db.models import (
    Count,
    Q,
)
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Department,
    User,
)
from ..serializers.employees import (
    DepartmentSerializer,
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeUpdateSerializer,
)


class DepartmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view departments.'}, status=status.HTTP_403_FORBIDDEN)

        departments = Department.objects.all()
        serializer = DepartmentSerializer(departments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEOs can create departments.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DepartmentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        if request.user.role != User.Role.CEO:
            return Response({'detail': 'Only CEOs can remove departments.'}, status=status.HTTP_403_FORBIDDEN)

        department = get_object_or_404(Department, id=id)
        department.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmployeeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR, User.Role.IT]:
            return Response({'detail': 'Only CEO, HR, and IT can view employees.'}, status=status.HTTP_403_FORBIDDEN)

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

        paginator = EmployeePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = EmployeeListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can create employees.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        response_serializer = EmployeeListSerializer(employee)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view employee details.'}, status=status.HTTP_403_FORBIDDEN)

        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeListSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response(
                {'detail': 'Only CEO and HR can update employee details.'}, status=status.HTTP_403_FORBIDDEN
            )

        employee = get_object_or_404(User.objects.select_related('department'), id=id)
        serializer = EmployeeUpdateSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EmployeeListSerializer(employee).data, status=status.HTTP_200_OK)


class EmployeeStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in [User.Role.CEO, User.Role.HR]:
            return Response({'detail': 'Only CEO and HR can view employee stats.'}, status=status.HTTP_403_FORBIDDEN)

        base = User.objects.select_related('department').all()

        stats = base.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            full_time=Count('id', filter=Q(full_time=True)),
        )

        department_rows = base.values('department__name').annotate(count=Count('id')).order_by('department__name')

        departments = []
        for row in department_rows:
            departments.append(
                {
                    'name': row['department__name'] or 'Unassigned',
                    'count': row['count'],
                }
            )

        return Response(
            {
                'total': stats['total'],
                'active': stats['active'],
                'full_time': stats['full_time'],
                'departments': departments,
            },
            status=status.HTTP_200_OK,
        )
