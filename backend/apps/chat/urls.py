from django.urls import path
from .views import (
    ChatMessageListCreateView,
    ChatMessageSendView,
    ChatSessionDetailView,
    ChatSessionListCreateView,
)

urlpatterns = [
    path("sessions/", ChatSessionListCreateView.as_view(), name="chat-session-list-create"),
    path("sessions/<uuid:id>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("sessions/<uuid:session_id>/messages/", ChatMessageListCreateView.as_view(), name="chat-message-list-create"),
    path("sessions/<uuid:session_id>/send/", ChatMessageSendView.as_view(), name="chat-message-send"),
]
