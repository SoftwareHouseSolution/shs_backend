from django.utils import timezone
from django.utils.translation import get_language
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from apps.core.codes import ResponseCode
from apps.core.schema import ERROR_400_VALIDATION, ERROR_409, ERROR_415, api_schema, envelope
from apps.core.views import PublicAPIView
from config.api_responses import ApiResponse

from .models import Enquiry
from .serializers import EnquiryCreateSerializer, EnquiryReceiptSerializer
from .services import EnquiryInput, EnquiryService


class EnquiryCreateView(PublicAPIView):
    throttle_scope = "enquiries"
    service_factory = staticmethod(EnquiryService.from_settings)

    def get_throttles(self):
        # The tight per-hour budget is for submissions only; any other method should get
        # its honest 405, not spend (or be refused by) the submission allowance.
        if self.request.method == "POST":
            return [AnonRateThrottle(), ScopedRateThrottle()]
        return [AnonRateThrottle()]

    @api_schema(
        summary="Send an enquiry from the contact form",
        request=EnquiryCreateSerializer,
        responses={
            201: envelope(EnquiryReceiptSerializer),
            400: ERROR_400_VALIDATION,
            409: ERROR_409,
            415: ERROR_415,
        },
        tags=["enquiries"],
    )
    def post(self, request):
        serializer = EnquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.is_bot:
            # Indistinguishable from success so the bot learns nothing; nothing is stored.
            receipt = EnquiryReceiptSerializer(Enquiry(created_at=timezone.now())).data
            return ApiResponse.created(receipt, code=ResponseCode.ENQUIRY_CREATED)

        data = {k: v for k, v in serializer.validated_data.items() if k != "website"}
        enquiry = self.service_factory().submit(EnquiryInput(**data), language=get_language())
        return ApiResponse.created(EnquiryReceiptSerializer(enquiry).data, code=ResponseCode.ENQUIRY_CREATED)
