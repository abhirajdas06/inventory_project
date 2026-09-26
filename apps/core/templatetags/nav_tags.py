from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def nav_active(context, *names):
    request = context.get('request')
    if not request:
        return ''
    current = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    kwargs = getattr(getattr(request, 'resolver_match', None), 'kwargs', {}) or {}
    for name in names:
        route, _, kind = str(name).partition(':')
        if current != route:
            continue
        if kind and kwargs.get('kind') != kind:
            continue
        return 'active'
    return ''


@register.simple_tag(takes_context=True)
def nav_open(context, *names):
    request = context.get('request')
    if not request:
        return ''
    current = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    kwargs = getattr(getattr(request, 'resolver_match', None), 'kwargs', {}) or {}
    for name in names:
        route, _, kind = str(name).partition(':')
        if current != route:
            continue
        if kind and kwargs.get('kind') != kind:
            continue
        return 'show'
    return ''


@register.simple_tag(takes_context=True)
def page_query(context, page_number):
    """Current query string with ``page`` replaced, so pagination keeps the
    active search and filters without piling up duplicate page= parameters."""
    params = context['request'].GET.copy()
    params['page'] = page_number
    return params.urlencode()


@register.simple_tag(takes_context=True)
def legend_chip(context, status):
    """Attributes for a topbar colour-legend chip that filters the current list.

    Returns a dict: ``url`` (empty when the current page can't filter by this
    colour), ``active`` and ``title``. Clicking an active chip clears the
    filter. On the server pages the gray "Empty" chip switches between the
    Live and Empty server tabs, since that is how empty servers are separated.
    """
    request = context.get('request')
    if not request:
        return {'url': '', 'active': False}
    from django.urls import reverse

    params = request.GET.copy()
    params.pop('page', None)
    url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''

    if status == 'EMPTY' and url_name in ('server_list', 'server_empty_list'):
        active = url_name == 'server_empty_list'
        target = reverse('server_list' if active else 'server_empty_list')
        params.pop('status', None)
        return {'url': target + ('?' + params.urlencode() if params else ''), 'active': active}

    f = context.get('list_filter')
    if not f or not f.get('show_status') or status not in dict(f.get('status_options', [])):
        return {'url': '', 'active': False}
    active = f['values'].get('status') == status
    if active:
        params['status'] = ''   # explicit empty keeps sold lists from re-defaulting to SALE
    else:
        params['status'] = status
    return {'url': request.path + '?' + params.urlencode(), 'active': active}
