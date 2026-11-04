def active_company(request):
    return {
        "company": getattr(request, "company", None),
        "licence": getattr(request, "licence", None),
    }
