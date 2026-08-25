from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.categories.models import Card, CPU, Controller, HardDisk, Memory, NetworkingSpare, RailKit, SFP, Spare
from apps.core.activity import log_activity
from apps.core.models import RolePermission, UserProfile
from apps.core.permissions import PERMISSION_LABELS, ROLE_PERMISSIONS, require_permission
from apps.inventory.models import InventoryTransaction
from apps.servers.models import Server


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
    latest_type = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at').values('transaction_type')[:1]

    category_models = [
        ('Battery', Spare),
        ('Card', Card),
        ('CPU', CPU),
        ('Controller', Controller),
        ('Hard Disk', HardDisk),
        ('Memory', Memory),
        ('Networking Spare', NetworkingSpare),
        ('Rail Kit', RailKit),
        ('SFP', SFP),
    ]

    cards = []
    for label, model in category_models:
        qs = model.objects.annotate(latest_type=Subquery(latest_type))
        live = qs.exclude(latest_type='OUT').count()
        sold = qs.filter(latest_type='OUT').count()
        cards.append({'label': label, 'live': live, 'sold': sold, 'total': live + sold})

    server_qs = Server.objects.annotate(latest_type=Subquery(latest_type))
    server_live = server_qs.exclude(latest_type='OUT').count()
    server_sold = server_qs.filter(latest_type='OUT').count()
    cards.append({'label': 'Server', 'live': server_live, 'sold': server_sold, 'total': server_live + server_sold})

    recent = InventoryTransaction.objects.select_related('product', 'performed_by', 'audited_by').order_by('-created_at')[:12]
    tx_counts = InventoryTransaction.objects.values('transaction_type').annotate(total=Count('id'))

    return render(request, 'dashboard.html', {
        'cards': cards,
        'recent_transactions': recent,
        'tx_counts': list(tx_counts),
    })


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
        'roles': UserProfile.ROLE_CHOICES,
    })


@require_permission('user_management')
def role_permission_settings(request):
    roles = list(UserProfile.ROLE_CHOICES)
    if request.method == 'POST':
        role = request.POST.get('role', '')
        valid_roles = {value for value, _ in roles}
        if role not in valid_roles:
            messages.error(request, 'Invalid role.')
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
        return redirect('role_permission_settings')

    overrides = {row.role: set(row.permissions or []) for row in RolePermission.objects.all()}
    role_rows = [
        {'role': role, 'label': label, 'permissions': overrides.get(role, ROLE_PERMISSIONS.get(role, set())),
         'customized': role in overrides}
        for role, label in roles
    ]
    return render(request, 'auth/role_permission_settings.html', {
        'role_rows': role_rows,
        'permission_options': PERMISSION_LABELS.items(),
    })


@require_permission('user_management')
def user_create(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'STOCK_IN')
        email = request.POST.get('email', '').strip()
        valid_roles = {value for value, _ in UserProfile.ROLE_CHOICES}

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
        'roles': UserProfile.ROLE_CHOICES,
    })


@require_permission('user_management')
def user_edit(request, user_id):
    target = get_object_or_404(User, id=user_id)
    profile = _ensure_profile(target)
    if request.method == 'POST':
        action = request.POST.get('action', 'update')
        valid_roles = {value for value, _ in UserProfile.ROLE_CHOICES}

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
        'roles': UserProfile.ROLE_CHOICES,
    })
