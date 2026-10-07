from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Django session login for the API (the `sessionid` cookie), with CSRF checks on writes.

    The only change from DRF's class: unauthenticated requests get 401 instead of 403,
    so clients can tell "please log in" apart from "you may not do this".
    """

    def authenticate_header(self, request):
        return 'Session'
