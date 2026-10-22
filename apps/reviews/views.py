from django.utils import timezone
from django.utils.translation import get_language
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from apps.core.codes import ResponseCode
from apps.core.schema import ERROR_400_VALIDATION, ERROR_409, ERROR_415, api_schema, envelope
from apps.core.views import PublicAPIView
from config.api_exceptions import ServiceUnavailableException
from config.api_responses import ApiResponse

from . import drafting
from .models import Review
from .serializers import (
    ReviewCreateSerializer,
    ReviewDraftResultSerializer,
    ReviewDraftSerializer,
    ReviewReceiptSerializer,
)
from .services import ReviewInput, ReviewService


class ReviewCreateView(PublicAPIView):
    """POST a client review from the website's review page."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "reviews"
    service_factory = staticmethod(ReviewService.from_settings)

    def get_throttles(self):
        if self.request.method == "POST":
            return [AnonRateThrottle(), ScopedRateThrottle()]
        return [AnonRateThrottle()]

    @api_schema(
        summary="Send a client review",
        request={"multipart/form-data": ReviewCreateSerializer},
        responses={
            201: envelope(ReviewReceiptSerializer),
            400: ERROR_400_VALIDATION,
            409: ERROR_409,
            415: ERROR_415,
        },
        tags=["reviews"],
    )
    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.is_bot:
            # Indistinguishable from success so the bot learns nothing; nothing is stored.
            receipt = ReviewReceiptSerializer(Review(created_at=timezone.now())).data
            return ApiResponse.created(receipt, code=ResponseCode.REVIEW_CREATED)

        data = dict(serializer.validated_data)
        data.pop("website", None)
        photo = data.pop("photo", None)
        review = self.service_factory().submit(ReviewInput(**data), photo=photo, language=get_language())
        return ApiResponse.created(ReviewReceiptSerializer(review).data, code=ResponseCode.REVIEW_CREATED)


class ReviewDraftView(PublicAPIView):
    """POST a client's answers; get back a review written in their voice (apps.reviews.drafting).

    503 when AI drafting is off or fails — the review page then drafts from its own
    templates, so a client never sees this endpoint fail."""

    throttle_scope = "review_drafts"

    def get_throttles(self):
        return [AnonRateThrottle(), ScopedRateThrottle()]

    @api_schema(
        summary="Draft a client review from their answers",
        request=ReviewDraftSerializer,
        responses={200: envelope(ReviewDraftResultSerializer), 400: ERROR_400_VALIDATION},
        tags=["reviews"],
    )
    def post(self, request):
        serializer = ReviewDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            text = drafting.draft(drafting.DraftRequest(**serializer.validated_data), language=get_language())
        except drafting.DraftUnavailable as exc:
            raise ServiceUnavailableException() from exc
        return ApiResponse.success({"text": text}, code=ResponseCode.REVIEW_DRAFTED)
