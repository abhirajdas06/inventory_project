from apps.core.permissions import permissions_for


def permissions(request):
    """Expose the logged-in user's effective permissions to every template as
    ``can`` — e.g. ``{% if can.stock_out %}``. It reads exactly what Role
    Settings saved (or the role defaults), so templates never hard-code roles."""
    user = getattr(request, 'user', None)
    granted = permissions_for(user) if user is not None else set()
    return {'can': {key: True for key in granted}}


def spare_subcategory_nav(request):
    """Sidebar entries for the 19 split-out spare sub-categories (Cable,
    Battery, Motherboard, ...), with URLs and "is this the current page"
    flags precomputed — the base.html nav just loops and checks booleans,
    no per-item template-tag string building needed. See
    apps.categories.spare_subcategories for the category list itself."""
    from django.urls import reverse
    from apps.categories.spare_subcategories import SPARE_SUBCATEGORIES, spare_kind_key

    resolver = getattr(request, 'resolver_match', None)
    url_name = getattr(resolver, 'url_name', '') if resolver else ''
    kwargs = getattr(resolver, 'kwargs', {}) if resolver else {}
    current_kind = kwargs.get('kind', '')

    items = []
    any_active = False
    for slug, cfg in SPARE_SUBCATEGORIES.items():
        kind = spare_kind_key(slug)
        is_current = current_kind == kind and url_name in ('spare_subcategory_list', 'inventory_sold', 'inventory_faulty')
        any_active = any_active or is_current
        items.append({
            'kind': kind,
            'label': cfg['label'],
            'icon': cfg['icon'],
            'list_url': reverse('spare_subcategory_list', args=[kind]),
            'sold_url': reverse('inventory_sold', args=[kind]),
            'faulty_url': reverse('inventory_faulty', args=[kind]),
            'add_url': f"{reverse('add_spare')}?type={cfg['canonical']}",
            'list_active': url_name == 'spare_subcategory_list' and current_kind == kind,
            'sold_active': url_name == 'inventory_sold' and current_kind == kind,
            'faulty_active': url_name == 'inventory_faulty' and current_kind == kind,
        })
    return {
        'spare_subcategory_nav': items,
        'spare_subcategory_nav_open': any_active,
        'server_group_nav': _server_group_nav(url_name, kwargs),
    }


def _server_group_nav(url_name, kwargs):
    """Sidebar entries for the server groups (Blade Server, Storage, ...) —
    same precomputed-flags approach as the spare sub-categories."""
    from django.urls import reverse
    from apps.servers.groups import SERVER_GROUPS

    current = kwargs.get('group', '')
    items = []
    for slug, cfg in SERVER_GROUPS.items():
        here = current == slug
        items.append({
            'group': slug,
            'label': cfg['label'],
            'icon': cfg['icon'],
            'list_url': reverse('server_group_list', args=[slug]),
            'empty_url': reverse('server_group_empty_list', args=[slug]),
            'sold_url': reverse('server_group_out_list', args=[slug]),
            'faulty_url': reverse('server_group_faulty_list', args=[slug]),
            'add_url': f"{reverse('add_server')}?group={slug}",
            'open': here,
            'list_active': here and url_name == 'server_group_list',
            'empty_active': here and url_name == 'server_group_empty_list',
            'sold_active': here and url_name == 'server_group_out_list',
            'faulty_active': here and url_name == 'server_group_faulty_list',
        })
    return items
