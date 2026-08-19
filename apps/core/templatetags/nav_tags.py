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
