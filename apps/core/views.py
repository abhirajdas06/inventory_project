from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.activity import log_activity
from apps.core.models import RolePermission, UserProfile
from apps.core.permissions import PERMISSION_LABELS, ROLE_PERMISSIONS, all_roles, require_permission
from apps.inventory.models import InventoryTransaction


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'auth/login.html')


@require_POST
def login_view(request):
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)
    if user is None:
        messages.error(request, 'Invalid username or password.')
        return redirect('home')
    login(request, user)
    return redirect('dashboard')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def dashboard(request):
    from apps.core.dashboard_stats import dashboard_registry, kind_overview

    cards = []
    for kind, cfg in dashboard_registry().items():
        data = kind_overview(cfg['model'], cfg.get('category_q'), with_empty=cfg.get('is_server', False))
        data.update({'kind': kind, 'label': cfg['label'], 'icon': cfg['icon']})
        # Compact card face: total store-wise breakdown, top few only — the
        # rest (full store list, faulty/damaged, faulty/damaged/scrap-out) is
        # one click away in the detail modal so the card never grows huge.
        data['top_stores'] = data['by_store'][:4]
        data['more_stores'] = max(0, len(data['by_store']) - 4)
        cards.append(data)

    recent = InventoryTransaction.objects.select_related('product', 'performed_by', 'audited_by').order_by('-created_at')[:12]
    tx_counts = InventoryTransaction.objects.values('transaction_type').annotate(total=Count('id'))

    return render(request, 'dashboard.html', {
        'cards': cards,
        'recent_transactions': recent,
        'tx_counts': list(tx_counts),
    })


@login_required
def dashboard_card_detail(request, kind):
    from apps.core.dashboard_stats import card_data

    data = card_data(kind, with_urls=True)
    if data is None:
        return JsonResponse({'error': 'Unknown card'}, status=404)
    return JsonResponse(data)


# ════════════════════════════════════════════════════════════
#  USER MANAGEMENT (Admin only)
# ════════════════════════════════════════════════════════════

def _ensure_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'ADMIN' if user.is_superuser else 'STOCK_IN'},
    )
    return profile


@require_permission('user_management')
def user_list(request):
    users = User.objects.select_related('profile').order_by('username')
    rows = []
    for user in users:
        rows.append({'user': user, 'profile': _ensure_profile(user)})
    return render(request, 'auth/user_list.html', {
        'rows': rows,
        'roles': all_roles(),
    })


def _custom_role_key(label):
    """Role key for a new user type, e.g. Store Viewer -> STORE_VIEWER."""
    import re
    base = re.sub(r'[^A-Z0-9]+', '_', label.upper()).strip('_')[:32] or 'USER_TYPE'
    taken = {value for value, _ in all_roles()}
    key, n = base, 2
    while key in taken:
        key = f'{base[:32 - len(str(n)) - 1]}_{n}'
        n += 1
    return key


def _add_user_type(request):
    label = ' '.join((request.POST.get('label') or '').split())[:60]
    if not label:
        messages.error(request, 'Give the new user type a name.')
        return redirect('role_permission_settings')
    if any(label.lower() == existing.lower() for _, existing in all_roles()):
        messages.error(request, f'A user type called "{label}" already exists.')
        return redirect('role_permission_settings')
    copy_from = request.POST.get('copy_from', '')
    permissions = []
    if copy_from:
        override = RolePermission.objects.filter(role=copy_from).first()
        permissions = sorted(override.permissions if override else ROLE_PERMISSIONS.get(copy_from, set()))
    role = _custom_role_key(label)
    RolePermission.objects.create(role=role, label=label, is_custom=True, permissions=permissions)
    log_activity(action='USER_TYPE_CREATED', module='USER', entity=role, user=request.user,
                 new_values={'label': label, 'permissions': permissions, 'copied_from': copy_from},
                 remarks='User type added')
    messages.success(request, f'User type "{label}" added. Tick its permissions below and save.')
    return redirect(f"{reverse('role_permission_settings')}?open={role}")


def _delete_user_type(request, role):
    row = RolePermission.objects.filter(role=role, is_custom=True).first()
    if row is None:
        messages.error(request, 'Only user types you added can be deleted.')
        return redirect('role_permission_settings')
    in_use = UserProfile.objects.filter(role=role).count()
    if in_use:
        messages.error(request, f'"{row.label}" is still given to {in_use} user(s). Change their role first.')
        return redirect('role_permission_settings')
    row.delete()
    log_activity(action='USER_TYPE_DELETED', module='USER', entity=role, user=request.user,
                 old_values={'label': row.label, 'permissions': row.permissions},
                 remarks='User type deleted')
    messages.success(request, f'User type "{row.label}" deleted.')
    return redirect('role_permission_settings')


@require_permission('user_management')
def role_permission_export(request):
    """Excel of every user type, its permissions and its users, with
    columns for management to approve."""
    from io import BytesIO
    from django.http import HttpResponse
    from django.utils import timezone
    from apps.core.role_export import build_role_approval_workbook
    stream = BytesIO()
    build_role_approval_workbook(generated_by=request.user.get_username()).save(stream)
    log_activity(action='ROLE_PERMISSIONS_EXPORTED', module='USER', entity='Role permissions',
                 user=request.user, remarks='Role permissions exported for approval')
    response = HttpResponse(stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="user-types-permissions-{timezone.localdate()}.xlsx"'
    return response


@require_permission('user_management')
def role_permission_settings(request):
    roles = all_roles()
    if request.method == 'POST':
        if request.POST.get('action') == 'add_role':
            return _add_user_type(request)
        role = request.POST.get('role', '')
        valid_roles = {value for value, _ in roles}
        if role not in valid_roles:
            messages.error(request, 'Invalid role.')
            return redirect('role_permission_settings')
        if request.POST.get('action') == 'delete_role':
            return _delete_user_type(request, role)
        if request.POST.get('action') == 'reset':
            if role not in ROLE_PERMISSIONS:
                messages.error(request, 'User types you added have no defaults to reset to.')
                return redirect('role_permission_settings')
            deleted, _ = RolePermission.objects.filter(role=role).delete()
            log_activity(action='ROLE_PERMISSIONS_RESET', module='USER', entity=role,
                         user=request.user,
                         new_values={'permissions': sorted(ROLE_PERMISSIONS.get(role, set()))},
                         remarks='Role permissions reset to default')
            if deleted:
                messages.success(request, f'{dict(roles)[role]} permissions reset to default.')
            else:
                messages.info(request, f'{dict(roles)[role]} already uses the default permissions.')
            return redirect('role_permission_settings')
        selected = [key for key in PERMISSION_LABELS if request.POST.get(key) == 'on']
        # Do not let an administrator remove the only way back into these settings.
        if role == 'ADMIN' and 'user_management' not in selected:
            selected.append('user_management')
        RolePermission.objects.update_or_create(role=role, defaults={'permissions': selected})
        log_activity(action='ROLE_PERMISSIONS_UPDATED', module='USER', entity=role,
                     user=request.user, new_values={'permissions': selected},
                     remarks='Role permissions updated')
        messages.success(request, f'{dict(roles)[role]} permissions updated.')
        return redirect(f"{reverse('role_permission_settings')}?open={role}")

    rows = {row.role: row for row in RolePermission.objects.all()}
    user_counts = dict(UserProfile.objects.values('role').annotate(n=Count('id')).values_list('role', 'n'))
    open_role = request.GET.get('open') or (roles[0][0] if roles else '')
    role_rows = [
        {'role': role, 'label': label,
         'permissions': set(rows[role].permissions or []) if role in rows else ROLE_PERMISSIONS.get(role, set()),
         'customized': role in rows and not rows[role].is_custom,
         'is_custom': role in rows and rows[role].is_custom,
         'user_count': user_counts.get(role, 0),
         'open': role == open_role}
        for role, label in roles
    ]
    return render(request, 'auth/role_permission_settings.html', {
        'role_rows': role_rows,
        'permission_options': PERMISSION_LABELS.items(),
        'roles': roles,
    })


@require_permission('user_management')
def user_create(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'STOCK_IN')
        email = request.POST.get('email', '').strip()
        valid_roles = {value for value, _ in all_roles()}

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return redirect('user_create')
        if role not in valid_roles:
            messages.error(request, 'Invalid role.')
            return redirect('user_create')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('user_create')

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            is_staff=(role == 'ADMIN'),
            is_superuser=(role == 'ADMIN'),
        )
        UserProfile.objects.update_or_create(user=user, defaults={'role': role})
        log_activity(
            action='USER_CREATE',
            module='USER',
            entity=username,
            entity_id=user.id,
            user=request.user,
            new_values={'role': role, 'email': email},
            remarks='User created',
        )
        messages.success(request, f'User "{username}" created.')
        return redirect('user_list')
    return render(request, 'auth/user_form.html', {
        'roles': all_roles(),
    })


@require_permission('user_management')
def user_edit(request, user_id):
    target = get_object_or_404(User, id=user_id)
    profile = _ensure_profile(target)
    if request.method == 'POST':
        action = request.POST.get('action', 'update')
        valid_roles = {value for value, _ in all_roles()}

        if action == 'reset_password':
            new_password = request.POST.get('password', '')
            if not new_password:
                messages.error(request, 'Password cannot be empty.')
                return redirect('user_edit', user_id=user_id)
            target.set_password(new_password)
            target.save(update_fields=['password'])
            log_activity(action='USER_PASSWORD_RESET', module='USER', entity=target.username,
                         entity_id=target.id, user=request.user, remarks='Password reset')
            messages.success(request, 'Password reset.')
            return redirect('user_edit', user_id=user_id)

        old_role = profile.role
        role = request.POST.get('role', profile.role)
        if role not in valid_roles:
            messages.error(request, 'Invalid role.')
            return redirect('user_edit', user_id=user_id)
        is_active = request.POST.get('is_active') == 'on'

        profile.role = role
        profile.save(update_fields=['role'])
        target.is_active = is_active
        target.is_staff = (role == 'ADMIN')
        target.is_superuser = (role == 'ADMIN')
        target.email = request.POST.get('email', target.email).strip()
        target.save(update_fields=['is_active', 'is_staff', 'is_superuser', 'email'])
        log_activity(action='USER_UPDATE', module='USER', entity=target.username,
                     entity_id=target.id, user=request.user,
                     old_values={'role': old_role}, new_values={'role': role, 'is_active': is_active},
                     remarks='User updated')
        messages.success(request, 'User updated.')
        return redirect('user_list')
    return render(request, 'auth/user_form.html', {
        'target': target,
        'profile': profile,
        'roles': all_roles(),
    })


@require_permission('user_management')
@require_POST
def user_toggle_active(request, user_id):
    """Activate / deactivate a user. Inactive users cannot log in
    (Django's auth backend rejects is_active=False)."""
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('user_list')

    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    log_activity(
        action='USER_ACTIVATE' if target.is_active else 'USER_DEACTIVATE',
        module='USER', entity=target.username, entity_id=target.id, user=request.user,
        new_values={'is_active': target.is_active},
        remarks=('Marked active' if target.is_active else 'Marked inactive — login blocked'),
    )
    messages.success(
        request,
        f'"{target.username}" is now {"active" if target.is_active else "inactive (cannot log in)"}.'
    )
    return redirect('user_list')
