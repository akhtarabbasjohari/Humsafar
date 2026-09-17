from django.urls import path
from .views import (
    ChatAudioTranscribeView,
    ChatDocumentUploadView,
    ChatItineraryRedraftView,
    ChatMessageListCreateView,
    ChatMessageSendView,
    ChatSessionClaimView,
    ChatSessionDetailView,
    ChatSessionListCreateView,
    ModelComparisonAPIView,
    ModelComparisonDashboardView,
    ObservabilityDashboardView,
    ObservabilityLogsAPIView,
)

urlpatterns = [
    path("transcribe/", ChatAudioTranscribeView.as_view(), name="chat-transcribe"),
    path("upload/", ChatDocumentUploadView.as_view(), name="chat-document-upload"),
    path("sessions/<uuid:session_id>/upload/", ChatDocumentUploadView.as_view(), name="chat-session-document-upload"),
    path("comparison/", ModelComparisonAPIView.as_view(), name="model-comparison-api"),
    path("comparison/view/", ModelComparisonDashboardView.as_view(), name="model-comparison-dashboard"),
    path("observability/logs/", ObservabilityLogsAPIView.as_view(), name="observability-logs"),
    path("observability/view/", ObservabilityDashboardView.as_view(), name="observability-dashboard"),
    path("sessions/", ChatSessionListCreateView.as_view(), name="chat-session-list-create"),
    path("sessions/claim/", ChatSessionClaimView.as_view(), name="chat-session-claim"),
    path("sessions/<uuid:id>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("sessions/<uuid:session_id>/messages/", ChatMessageListCreateView.as_view(), name="chat-message-list-create"),
    path("sessions/<uuid:session_id>/send/", ChatMessageSendView.as_view(), name="chat-message-send"),
    path("sessions/<uuid:session_id>/redraft/", ChatItineraryRedraftView.as_view(), name="chat-itinerary-redraft"),
    path("sessions/<uuid:session_id>/observability/", ObservabilityLogsAPIView.as_view(), name="session-observability"),
]

