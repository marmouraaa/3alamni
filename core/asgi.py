"""
ASGI config for core project — Django Channels activé.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# L'app Django doit être initialisée AVANT d'importer les consumers
django_asgi_app = get_asgi_application()

from health.routing import websocket_urlpatterns   # import après setup Django

application = ProtocolTypeRouter({
    # Requêtes HTTP normales → Django standard
    "http": django_asgi_app,

    # Connexions WebSocket → Channels avec authentification session Django
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})