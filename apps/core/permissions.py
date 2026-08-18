from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


ROLE_PERMISSIONS = {
    'ADMIN': {
        'user_management', 'stock_in', 'stock_out', 'stock_out_import',
        'transfer_request', 'transfer_receive', 'audit', 'audit_view',
        'product_history', 'sales_return', 'sold_view', 'rent_return',
        'reconciliation', 'mapping', 'freeze', 'reports', 'audit_findings',
        'attend_audit_finding', 'stock_return',
    },
    'STOCK_IN': {
        'stock_in', 'sales_return', 'rent_return', 'transfer_receive',
        'audit_view', 'product_history', 'sold_view', 'mapping',
        'audit_findings', 'attend_audit_finding', 'stock_return', 'reports',
    },
    'STOCK_OUT': {
        'stock_out', 'stock_out_import', 'transfer_request', 'freeze', 'mapping',
        'sold_view', 'reports',
    },
    'AUDIT': {
        'audit', 'audit_findings',
    },
}


def user_role(user):
    if not getattr(user, 'is_authenticated', False):
        return ''
    if getattr(user, 'is_superuser', False):
        return 'ADMIN'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else ''


def has_permission(user, permission):
    role = user_role(user)
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_permission(request.user, permission):
                return HttpResponseForbidden('Permission denied')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def require_any_permission(*permissions):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not any(has_permission(request.user, permission) for permission in permissions):
                return HttpResponseForbidden('Permission denied')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
