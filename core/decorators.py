from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Membership


def company_required(view):
    """The user must be logged in and belong to a company."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.company is None:
            raise PermissionDenied("This account is not linked to a company. Ask an admin to add it.")
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    """The user must be an admin of the active company."""

    @wraps(view)
    @company_required
    def wrapper(request, *args, **kwargs):
        if request.role != Membership.Role.ADMIN:
            raise PermissionDenied("Only an admin can open this page.")
        return view(request, *args, **kwargs)

    return wrapper
