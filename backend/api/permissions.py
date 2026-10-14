"""Role-based access for API views.

    permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]

When different HTTP methods allow different roles, pass one list per method:

    permission_classes = [IsAuthenticated, role_required(get=[CEO, HR, IT], post=[CEO, HR])]

Methods without a list are denied. Use `User.Role.values` to allow every role.
"""

from collections.abc import Iterable

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


def role_required(*roles: str, **roles_by_method: Iterable[str]) -> type[BasePermission]:
    if roles and roles_by_method:
        raise TypeError('Pass either roles or per-method role lists, not both.')

    allowed_everywhere = frozenset(roles)
    allowed_by_method = {method.upper(): frozenset(method_roles) for method, method_roles in roles_by_method.items()}

    class RoleRequired(BasePermission):
        message = 'You do not have permission to perform this action.'

        def has_permission(self, request: Request, view: APIView) -> bool:
            role = getattr(request.user, 'role', None)
            if not request.user.is_authenticated or role is None:
                return False
            if not allowed_by_method:
                return role in allowed_everywhere
            method = 'GET' if request.method == 'HEAD' else request.method
            return role in allowed_by_method.get(method or '', frozenset())

    return RoleRequired
