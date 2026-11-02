from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse

from .models import Membership

SESSION_KEY = "company_id"


class FirstRunMiddleware:
    """Send a brand new install to the setup screen until the first admin exists."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setup_url = reverse("first_run")
        if request.path != setup_url and not request.path.startswith("/static/"):
            if not get_user_model().objects.exists():
                return redirect(setup_url)
        return self.get_response(request)


class ActiveCompanyMiddleware:
    """Set request.company and request.role from the user's own memberships only."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.role = None
        request.memberships = []
        if request.user.is_authenticated:
            memberships = list(Membership.objects.filter(user=request.user).select_related("company"))
            request.memberships = memberships
            chosen = request.session.get(SESSION_KEY)
            active = next((m for m in memberships if m.company_id == chosen), None)
            if active is None and memberships:
                active = memberships[0]
            if active:
                request.company = active.company
                request.role = active.role
        return self.get_response(request)
