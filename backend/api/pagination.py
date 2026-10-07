"""Pagination for list endpoints (`?page=N&page_size=M`).

Responses look like:
    {"total_count": 42, <extra totals>, "count": 42, "next": url, "previous": url, "results": [...]}
`total_count` repeats `count` because the frontend reads it.
"""

from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data: Any, **extra: Any) -> Response:
        """`extra` adds summary fields to the response, e.g. totals over all pages."""
        assert self.page is not None
        count = self.page.paginator.count
        return Response(
            {
                'total_count': count,
                **extra,
                'count': count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data,
            }
        )


class TenPerPagePagination(StandardPagination):
    """Pages of 10; `?page_size=` can only make them smaller."""

    max_page_size = 10


class TwentyPerPagePagination(StandardPagination):
    page_size = 20
