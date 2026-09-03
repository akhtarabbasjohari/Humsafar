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
    permission_classes = [AllowAny]
    serializer_class = SavedItinerarySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return SavedItinerary.objects.filter(user=user)
        session_id = self.request.query_params.get("session_id")
        if session_id:
            return SavedItinerary.objects.filter(session_id=session_id)
        return SavedItinerary.objects.none()

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)

class ItineraryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a saved itinerary."""
    permission_classes = [AllowAny]
    serializer_class = SavedItinerarySerializer
    queryset = SavedItinerary.objects.all()
    lookup_field = "id"

    def get_object(self):
        itinerary = super().get_object()
        user = self.request.user
        if itinerary.user and itinerary.user != user:
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

        serializer = ItineraryApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["approved"]:
            itinerary.is_approved_by_user = True
            itinerary.status = SavedItinerary.STATUS_APPROVED
            itinerary.approval_timestamp = timezone.now()
            notes = serializer.validated_data.get("feedback_or_notes", "")
            if notes:
                itinerary.notes = f"{itinerary.notes}\n[Traveler Approval Note]: {notes}".strip()
            itinerary.save()

            return Response(
                SavedItinerarySerializer(itinerary).data,
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "Itinerary was not approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
