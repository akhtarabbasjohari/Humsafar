from django.urls import path
from .views import (
    ItineraryApproveView,
    ItineraryDetailView,
    ItineraryListCreateView,
)

urlpatterns = [
    path("", ItineraryListCreateView.as_view(), name="itinerary-list-create"),
    path("<uuid:id>/", ItineraryDetailView.as_view(), name="itinerary-detail"),
    path("<uuid:id>/approve/", ItineraryApproveView.as_view(), name="itinerary-approve"),
]
