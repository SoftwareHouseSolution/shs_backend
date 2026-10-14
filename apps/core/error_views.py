"""URL-level error handlers (active when DEBUG is off). API paths get the JSON envelope;
everything else — the admin included — keeps Django's normal HTML pages."""

from django.views.defaults import page_not_found
from django.views.defaults import server_error as html_server_error
from rest_framework import status as http

from config.api_exceptions import internal_error_meta
from config.api_responses import json_error

from .codes import ResponseCode
from .middleware import is_api_request


def not_found(request, exception=None):
    if is_api_request(request):
        return json_error(code=ResponseCode.RESOURCE_NOT_FOUND, status=http.HTTP_404_NOT_FOUND)
    return page_not_found(request, exception)


def server_error(request):
    if is_api_request(request):
        return json_error(
            code=ResponseCode.INTERNAL_SERVER_ERROR,
            status=http.HTTP_500_INTERNAL_SERVER_ERROR,
            meta=internal_error_meta(),
        )
    return html_server_error(request)
