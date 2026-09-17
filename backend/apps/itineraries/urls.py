from django.urls import path
from .views import (
    ItineraryApproveView,
    ItineraryDetailView,
    ItineraryListCreateView,
    ItineraryPdfExportView,
)

urlpatterns = [
    path("", ItineraryListCreateView.as_view(), name="itinerary-list-create"),
    path("export-pdf/", ItineraryPdfExportView.as_view(), name="itinerary-export-pdf"),
    path("<uuid:id>/", ItineraryDetailView.as_view(), name="itinerary-detail"),
    path("<uuid:id>/pdf/", ItineraryPdfExportView.as_view(), name="itinerary-detail-pdf"),
    path("<uuid:id>/approve/", ItineraryApproveView.as_view(), name="itinerary-approve"),
]

