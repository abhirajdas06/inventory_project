from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


LIST_PAGE_SIZE = 50


def paginated_list_context(request, queryset, context_key, *, per_page=LIST_PAGE_SIZE, **extra):
    """Build a bounded, database-paginated context for high-volume list views."""
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
        **extra,
    }
