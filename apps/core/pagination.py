"""Page-number pagination that reports through the standard envelope.

DRF's stock pagination returns `{"count", "next", "previous", "results"}` — a different
outer shape. Here the page data goes in `data` and the counters in `meta.pagination`, so a
paginated list is indistinguishable from any other response at the envelope level.
"""

import math

from rest_framework.pagination import PageNumberPagination

from apps.core.codes import ResponseCode
from config.api_responses import ApiResponse


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_meta(self) -> dict:
        page = self.page
        count = page.paginator.count
        size = page.paginator.per_page
        return {
            "count": count,
            "page": page.number,
            "page_size": size,
            "total_pages": max(1, math.ceil(count / size)) if size else 1,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
        }

    def get_paginated_response(self, data):
        return ApiResponse.paginated(data, pagination=self.get_meta())

    def get_paginated_response_schema(self, schema):
        """OpenAPI shape of the paginated envelope, used by drf-spectacular."""
        return {
            "type": "object",
            "required": ["success", "message", "code", "data", "errors", "meta"],
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string", "example": "Content retrieved successfully."},
                "code": {"type": "string", "example": ResponseCode.CONTENT_LIST_RETRIEVED.value},
                "data": schema,
                "errors": {"type": "object", "nullable": True, "example": None},
                "meta": {
                    "type": "object",
                    "properties": {
                        "pagination": {
                            "type": "object",
                            "required": ["count", "page", "page_size", "total_pages", "next", "previous"],
                            "properties": {
                                "count": {"type": "integer", "example": 367},
                                "page": {"type": "integer", "example": 1},
                                "page_size": {"type": "integer", "example": 20},
                                "total_pages": {"type": "integer", "example": 19},
                                "next": {"type": "string", "format": "uri", "nullable": True},
                                "previous": {"type": "string", "format": "uri", "nullable": True},
                            },
                        }
                    },
                },
            },
        }


class LargeResultsPagination(StandardPagination):
    """For collections a page legitimately renders in full (the 367-client directory)."""

    page_size = 100
    max_page_size = 500
