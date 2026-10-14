"""Test-only views that raise each kind of failure, mounted under /api/ so the full
middleware stack (request id, language) runs exactly as in production."""

from django.db import IntegrityError, OperationalError
from django.http import Http404, HttpResponse
from django.urls import include, path
from rest_framework import exceptions as drf
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from config import urls as project_urls
from config.api_exceptions import BusinessRuleException, ExternalServiceException


def _raiser(exc_factory, **attrs):
    class View(APIView):
        permission_classes: list = []

        def get(self, request):
            raise exc_factory()

    for k, v in attrs.items():
        setattr(View, k, v)
    return View.as_view()


class Protected(APIView):
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # pragma: no cover - never reached anonymously
        return HttpResponse()


def plain_django_view(request):
    raise RuntimeError("secret detail: password=hunter2")


urlpatterns = [
    path("api/test/boom/", _raiser(lambda: RuntimeError("secret detail: password=hunter2"))),
    path("api/test/integrity/", _raiser(lambda: IntegrityError('duplicate key value violates "x_pkey"'))),
    path("api/test/db-down/", _raiser(lambda: OperationalError("could not connect to server"))),
    path("api/test/http404/", _raiser(lambda: Http404("nope"))),
    path("api/test/forbidden/", _raiser(drf.PermissionDenied)),
    path("api/test/business/", _raiser(lambda: BusinessRuleException("Slot already taken."))),
    path("api/test/upstream/", _raiser(ExternalServiceException)),
    path("api/test/non-field/", _raiser(lambda: drf.ValidationError(["Dates overlap."]))),
    path("api/test/throttled/", _raiser(lambda: drf.Throttled(wait=17))),
    path("api/test/protected/", Protected.as_view()),
    path("api/test/plain/", plain_django_view),
    path("", include(project_urls)),
]
