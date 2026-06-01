# health/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/health/chat/(?P<request_id>[^/]+)/$', consumers.HealthChatConsumer.as_asgi()),
]