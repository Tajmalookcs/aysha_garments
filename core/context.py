from .models import Membership


def active_company(request):
    role = getattr(request, "role", None)
    return {
        "company": getattr(request, "company", None),
        "memberships": getattr(request, "memberships", []),
        "is_admin": role == Membership.Role.ADMIN,
    }
