from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from apps.core.models import RolePermission


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

PERMISSION_LABELS = {
    'user_management': 'Manage users and role settings',
    'stock_in': 'Add stock and components',
    'stock_out': 'Stock out products',
    'stock_out_import': 'Import stock-out Excel files',
    'transfer_request': 'Create transfer requests',
    'transfer_receive': 'Receive and approve transfers',
    'audit': 'Perform single-product audits',
    'audit_view': 'View audit reports and findings',
    'audit_findings': 'Create audit and general findings',
    'attend_audit_finding': 'Attend audit findings',
    'product_history': 'View product history and ledgers',
    'sales_return': 'Process sales returns',
    'stock_return': 'Return non-sale stocked-out products',
    'rent_return': 'Process rental returns',
    'sold_view': 'View sold, faulty, and stock-status lists',
    'reconciliation': 'Reconcile audit differences',
    'mapping': 'Map products and update list remarks',
    'freeze': 'Freeze and unfreeze stock',
    'reports': 'View and export reports',
}


def user_role(user):
    if not getattr(user, 'is_authenticated', False):
        return ''
    if getattr(user, 'is_superuser', False):
        return 'ADMIN'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else ''


def permissions_for(user):
    """Return the set of permission keys the user currently holds."""
    if not getattr(user, 'is_authenticated', False):
        return set()
    if getattr(user, 'is_superuser', False):
        return set(PERMISSION_LABELS.keys())
    role = user_role(user)
    override = RolePermission.objects.filter(role=role).only('permissions').first()
    if override is not None:
        return set(override.permissions or [])
    return set(ROLE_PERMISSIONS.get(role, set()))


def has_permission(user, permission):
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    role = user_role(user)
    override = RolePermission.objects.filter(role=role).only('permissions').first()
    if override is not None:
        return permission in (override.permissions or [])
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
