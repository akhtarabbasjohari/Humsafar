from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import SavedItinerary
from .serializers import ItineraryApprovalSerializer, SavedItinerarySerializer

class ItineraryListCreateView(generics.ListCreateAPIView):
    """List or create saved itineraries.
    
    Scoped to user when authenticated.
    Unauthenticated guests can create drafts linked to their session.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SavedItinerarySerializer

    def get_queryset(self):
        user = self.request.user
        return SavedItinerary.objects.filter(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied()
        extra_kwargs = {}
        if not serializer.validated_data.get("source_verified_at"):
            extra_kwargs["source_verified_at"] = timezone.now()
        serializer.save(user=user, **extra_kwargs)

class ItineraryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a saved itinerary."""
    permission_classes = [IsAuthenticated]
    serializer_class = SavedItinerarySerializer
    queryset = SavedItinerary.objects.all()
    lookup_field = "id"

    def get_object(self):
        itinerary = super().get_object()
        user = self.request.user
        if itinerary.user is None:
            raise PermissionDenied("This itinerary is not associated with any account.")
        if itinerary.user != user:
            raise PermissionDenied("You do not have permission to access this itinerary.")
        return itinerary

class ItineraryApproveView(APIView):
    """Human-in-the-loop (HITL) approval endpoint.
    
    Explicit traveler approval transitions a custom draft to 'approved'.
    """
    permission_classes = [AllowAny]

    def post(self, request, id):
        try:
            itinerary = SavedItinerary.objects.get(id=id)
        except SavedItinerary.DoesNotExist:
            return Response({"detail": "Itinerary not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        guest_token = request.headers.get("X-Guest-Token") or request.query_params.get("guest_token")
        if user.is_authenticated:
            if itinerary.user != user:
                raise PermissionDenied("You do not have permission to access this itinerary.")
        else:
            if not itinerary.session or not itinerary.session.guest_token or itinerary.session.guest_token != guest_token:
                raise PermissionDenied("You do not have permission to access this itinerary.")

        serializer = ItineraryApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["approved"]:
            # Data Freshness & Grounding Check: Reject stale or missing source data
            from services.data_integrity import is_timestamp_fresh
            if not itinerary.source_url:
                return Response(
                    {
                        "detail": "Cannot confirm itinerary: missing verifiable source URL.",
                        "error_code": "MISSING_SOURCE_URL",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not itinerary.source_verified_at or not is_timestamp_fresh(itinerary.source_verified_at):
                return Response(
                    {
                        "detail": "Cannot confirm itinerary: data source is stale or missing. Itinerary must be refreshed from live source before confirmation.",
                        "error_code": "STALE_OR_MISSING_SOURCE_DATA",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            itinerary.is_approved_by_user = True
            itinerary.status = SavedItinerary.STATUS_APPROVED
            itinerary.approval_timestamp = timezone.now()
            notes = serializer.validated_data.get("feedback_or_notes", "")
            if notes:
                itinerary.notes = f"{itinerary.notes}\n[Traveler Approval Note]: {notes}".strip()
            itinerary.save()

            from services.inquiry_service import build_inquiry_object

            inquiry = build_inquiry_object(
                itinerary=itinerary,
                user=request.user if request.user.is_authenticated else None,
                session=itinerary.session,
                additional_notes=notes,
            )

            return Response(
                {
                    **SavedItinerarySerializer(itinerary).data,
                    "inquiry": inquiry,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "Itinerary was not approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )


from django.http import HttpResponse
from django.utils.text import slugify
from services.pdf_service import generate_itinerary_pdf


class ItineraryPdfExportView(APIView):
    """
    Generate and stream an itinerary PDF.
    - POST: accepts complete itinerary JSON payload (from chat draft or catalog card).
    - GET: retrieves saved itinerary by <id> with authorization checks.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        itinerary_data = request.data
        if not itinerary_data or not isinstance(itinerary_data, dict):
            return Response(
                {"detail": "Itinerary data payload is required.", "error_code": "MISSING_PAYLOAD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = itinerary_data.get("title", "expedition_plan")
        try:
            pdf_bytes = generate_itinerary_pdf(itinerary_data)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to generate PDF: {str(exc)}", "error_code": "PDF_GENERATION_FAILED"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = f"{slugify(title) or 'itinerary'}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def get(self, request, id=None):
        if not id:
            return Response(
                {"detail": "Itinerary ID required.", "error_code": "MISSING_ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            itinerary = SavedItinerary.objects.get(id=id)
        except SavedItinerary.DoesNotExist:
            return Response({"detail": "Itinerary not found."}, status=status.HTTP_404_NOT_FOUND)

        # Auth check
        user = request.user
        guest_token = request.headers.get("X-Guest-Token") or request.query_params.get("guest_token")
        if itinerary.user:
            if not user.is_authenticated or itinerary.user != user:
                raise PermissionDenied("You do not have permission to access this itinerary.")
        elif itinerary.session and itinerary.session.guest_token:
            if not guest_token or itinerary.session.guest_token != guest_token:
                raise PermissionDenied("You do not have permission to access this itinerary.")

        itinerary_dict = SavedItinerarySerializer(itinerary).data
        if isinstance(itinerary_dict.get("itinerary_data"), dict):
            for k, v in itinerary_dict["itinerary_data"].items():
                if k not in itinerary_dict or not itinerary_dict[k]:
                    itinerary_dict[k] = v

        try:
            pdf_bytes = generate_itinerary_pdf(itinerary_dict)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to generate PDF: {str(exc)}", "error_code": "PDF_GENERATION_FAILED"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = f"{slugify(itinerary.title) or 'itinerary'}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
