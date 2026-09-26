from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

from apps.core.list_filters import apply_list_filters


LIST_PAGE_SIZE = 50


def paginated_list_context(request, queryset, context_key, *, per_page=LIST_PAGE_SIZE,
                           filter_hide=(), status_options=None, sold=None, **extra):
    """Build a bounded, database-paginated context for high-volume list views.

    The shared list filters (status / store / brand / date range — see
    apps.core.list_filters) are applied here, before pagination, so every list
    that goes through this helper filters identically and its counts and pages
    always reflect the active filters.
    """
    queryset, list_filter = apply_list_filters(
        request, queryset, hide=filter_hide, status_options=status_options, sold=sold,
    )
    paginator = Paginator(queryset, per_page)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    return {
        context_key: page_obj,
        'page_obj': page_obj,
        'total_count': paginator.count,
        'q': (request.GET.get('q') or '').strip(),
        'list_filter': list_filter,
        **extra,
    }
