from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.analytics.views import CollectView
from apps.clients.views import ClientListView, ClientTaxonomyView
from apps.content.views import PartnerListView, TestimonialListView
from apps.core.views import ApiNotFoundView, HealthView
from apps.enquiries.views import EnquiryCreateView
from apps.events.views import EventDetailView, EventListView
from apps.home.views import HomeView
from apps.pages.views import PageDetailView, PageListView
from apps.site_config.views import SiteView

api_v1 = [
    path("health/", HealthView.as_view(), name="health"),
    path("site/", SiteView.as_view(), name="site"),
    path("home/", HomeView.as_view(), name="home"),
    path("pages/", PageListView.as_view(), name="page-list"),
    path("pages/<slug:slug>/", PageDetailView.as_view(), name="page-detail"),
    path("clients/", ClientListView.as_view(), name="client-list"),
    path("clients/taxonomy/", ClientTaxonomyView.as_view(), name="client-taxonomy"),
    path("events/", EventListView.as_view(), name="event-list"),
    path("events/<slug:slug>/", EventDetailView.as_view(), name="event-detail"),
    path("testimonials/", TestimonialListView.as_view(), name="testimonial-list"),
    path("partners/", PartnerListView.as_view(), name="partner-list"),
    path("enquiries/", EnquiryCreateView.as_view(), name="enquiry-create"),
    path("analytics/collect/", CollectView.as_view(), name="analytics-collect"),
    # Documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-v1:schema"), name="docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api-v1:schema"), name="redoc"),
]

admin.site.site_header = "Software House Solutions"
admin.site.site_title = "SWH CMS"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include((api_v1, "api-v1"))),
    # Anything else under /api/ is a 404 in the envelope, never Django's HTML page.
    re_path(r"^api/", ApiNotFoundView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "apps.core.error_views.not_found"
handler500 = "apps.core.error_views.server_error"
