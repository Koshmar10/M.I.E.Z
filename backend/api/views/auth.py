"""Authentication and the current user's account: login, logout, profile, password.

Logins are Django sessions: `login()` sets the `sessionid` cookie, `logout()` deletes the
session on the server. See core/authentication.py.
"""

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authentication import SessionAuthentication

from ..serializers.auth import LoginSerializer


def _current_user(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': user.phone,
        'address': user.address,
        'department_name': user.department.name if user.department else None,
        'message': 'Authenticated',
    }


class LoginView(APIView):
    """Log in with username and password. Returns the user, like GET /auth/me/."""

    permission_classes = [AllowAny]

    def post(self, request):
        # Logged-out requests skip DRF's CSRF check, so check here: a foreign site must not
        # be able to log the browser into another account.
        SessionAuthentication().enforce_csrf(request)

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            return Response({'detail': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        return Response(_current_user(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({'detail': 'Logout successful'}, status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class UserMeView(APIView):
    """The logged-in user. Also hands out the `csrftoken` cookie, which the frontend
    needs before it can log in or send any change."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_current_user(request.user))

    def patch(self, request):
        user = request.user
        data = request.data
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone' in data:
            user.phone = data['phone']
        if 'address' in data:
            user.address = data['address']

        user.save(update_fields=['first_name', 'last_name', 'phone', 'address'])
        return JsonResponse(
            {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'address': user.address,
                'detail': 'Profile updated successfully.',
            }
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'detail': 'Both current and new passwords are required.'}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return Response({'detail': 'Incorrect current password.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)  # Keeps the user logged in
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
