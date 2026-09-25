from apps.core.permissions import permissions_for


def permissions(request):
    """Expose the logged-in user's effective permissions to every template as
    ``can`` — e.g. ``{% if can.stock_out %}``. It reads exactly what Role
    Settings saved (or the role defaults), so templates never hard-code roles."""
    user = getattr(request, 'user', None)
    granted = permissions_for(user) if user is not None else set()
    return {'can': {key: True for key in granted}}
