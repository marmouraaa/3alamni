# health/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class HealthChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour le chat anonyme santé mentale
    avec injection de pannes pour démonstration
    """
    
    async def connect(self):
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.room_group_name = f'health_chat_{self.request_id}'
        self.user = self.scope['user']
        
        # Vérifier permissions
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Vérifier accès à la demande
        has_access = await self.check_access()
        if not has_access:
            await self.close()
            return
        
        # Joindre le groupe
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mettre à jour la session de chat
        await self.update_chat_session(True)
        
        # Message de bienvenue système
        await self.send_system_message("💬 Chat connecté — anonymat garanti")
        
        logger.info(f"WebSocket connected: user={self.user.username}, request={self.request_id}")
    
    async def disconnect(self, close_code):
        # Injection de panne simulée: déconnexion inattendue
        if close_code != 1000:
            await self.send_system_message("⚠️ Connexion instable, reconnexion automatique...")
            logger.warning(f"WebSocket disconnected unexpectedly: code={close_code}")
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        await self.update_chat_session(False)
        
        logger.info(f"WebSocket disconnected: user={self.user.username}, code={close_code}")
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '').strip()
        
        if not message:
            return
        
        # Injection de panne: simulation de déconnexion (optionnel)
        # if "inject_disconnect" in message.lower():
        #     await self.close(code=1006)
        #     return
        
        # Déterminer rôle et sender
        is_counselor = await self.is_user_counselor()
        
        if is_counselor:
            sender_role = 'counselor'
            sender = f"Conseiller {self.user.username}"
        else:
            sender_role = 'student'
            anonymous_id = await self.get_anonymous_id()
            sender = anonymous_id
        
        # Sauvegarder le message
        saved_message = await self.save_message(sender, sender_role, message)
        
        # Envoyer au groupe
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'sender': sender,
                'sender_role': sender_role,
                'message': message,
                'timestamp': timezone.now().strftime('%H:%M'),
                'message_id': str(saved_message.id) if saved_message else None
            }
        )
        
        # Timeline event
        await self.create_timeline_event(sender, f"Message envoyé: {message[:50]}...")
    
    async def chat_message(self, event):
        """Envoyer message au WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'sender': event['sender'],
            'sender_role': event['sender_role'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))
    
    async def send_system_message(self, text):
        """Envoyer un message système"""
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': text
        }))
    
    async def send_security_block(self, text):
        """Envoyer un message de blocage sécurité"""
        await self.send(text_data=json.dumps({
            'type': 'security_block',
            'message': text
        }))
    
    @database_sync_to_async
    def check_access(self):
        """Vérifier si l'utilisateur a accès à cette demande"""
        from .models import HealthRequest
        
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            
            # Étudiant: seulement ses propres demandes
            if self.user.role == 'student':
                return health_request.student == self.user
            
            # Conseiller: peut voir toutes les demandes
            elif self.user.role == 'counselor':
                return True
            
            # Admin: tout accès
            elif self.user.role == 'admin':
                return True
            
            return False
        except HealthRequest.DoesNotExist:
            return False
    
    @database_sync_to_async
    def is_user_counselor(self):
        return self.user.role in ['counselor', 'admin']
    
    # health/consumers.py - Dans la classe HealthChatConsumer
    @database_sync_to_async
    def get_anonymous_id(self):
        """Récupère l'ID anonyme de l'étudiant"""
        if hasattr(self.user, 'student_profile'):
            return self.user.student_profile.anonymous_id or f"Étudiant #{self.user.id}"
        return f"Étudiant #{self.user.id}"
    @database_sync_to_async
    def save_message(self, sender, sender_role, content):
        from .models import Message, HealthRequest
        
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            message = Message.objects.create(
                health_request=health_request,
                sender=sender,
                sender_role=sender_role,
                content=content
            )
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return None
    
    @database_sync_to_async
    def create_timeline_event(self, actor, action):
        from .models import HealthTimelineEvent, HealthRequest
        
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            HealthTimelineEvent.objects.create(
                health_request=health_request,
                event_type='message_sent',
                actor=actor[:100],
                action=action[:200]
            )
        except Exception as e:
            logger.error(f"Error creating timeline event: {e}")
    
    @database_sync_to_async
    def update_chat_session(self, is_active):
        from .models import ChatSession, HealthRequest
        
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            session, created = ChatSession.objects.get_or_create(
                health_request=health_request,
                defaults={'is_active': is_active}
            )
            
            if not created:
                session.is_active = is_active
                
                # Mettre à jour le channel approprié
                is_counselor = self.user.role in ['counselor', 'admin']
                if is_counselor:
                    session.counselor_channel = self.channel_name
                else:
                    session.student_channel = self.channel_name
                
                session.save()
        except Exception as e:
            logger.error(f"Error updating chat session: {e}")