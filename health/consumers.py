# health/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class HealthChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour le chat anonyme santé mentale
    """
    
    async def connect(self):
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.room_group_name = f'health_chat_{self.request_id}'
        self.user = self.scope['user']
        
        # Vérifier authentification
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
        
        # Message de bienvenue
        role = "conseiller" if await self.is_user_counselor() else "étudiant"
        await self.send_system_message(f"💬 Chat connecté — vous parlez en tant que {role} anonyme")
        
        logger.info(f"WebSocket connecté: user={self.user.username}, request={self.request_id}")
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        await self.update_chat_session(False)
        
        if close_code != 1000:
            logger.warning(f"WebSocket déconnecté anormalement: code={close_code}")
        
        logger.info(f"WebSocket déconnecté: user={self.user.username}, code={close_code}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '').strip()
        except json.JSONDecodeError:
            await self.send_system_message("❌ Erreur: message invalide")
            return
        
        if not message:
            return
        
        # Vérifier que le chat n'est pas fermé
        is_closed = await self.is_request_closed()
        if is_closed:
            await self.send_system_message("❌ Cette discussion est clôturée, vous ne pouvez plus envoyer de messages.")
            return
        
        # Déterminer rôle et sender
        is_counselor = await self.is_user_counselor()
        
        if is_counselor:
            sender_role = 'counselor'
            sender_name = f"Conseiller"
            # Option: ajouter initiale pour distinguer plusieurs conseillers
            if self.user.first_name:
                sender_name = f"Conseiller {self.user.first_name[0]}."
        else:
            sender_role = 'student'
            sender_name = await self.get_anonymous_id()
        
        # Sauvegarder le message
        saved_message = await self.save_message(sender_name, sender_role, message)
        
        if not saved_message:
            await self.send_system_message("❌ Erreur: impossible d'enregistrer le message")
            return
        
        # Envoyer au groupe
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'sender': sender_name,
                'sender_role': sender_role,
                'message': message,
                'timestamp': timezone.now().strftime('%H:%M'),
            }
        )
        
        # Timeline event
        await self.create_timeline_event(sender_name, f"Message envoyé: {message[:50]}...")
    
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
    
    @database_sync_to_async
    def check_access(self):
        """Vérifier si l'utilisateur a accès à cette demande"""
        from .models import HealthRequest
        
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            
            if self.user.role == 'student':
                return health_request.student == self.user
            elif self.user.role in ['counselor', 'admin']:
                return True
            return False
        except HealthRequest.DoesNotExist:
            return False
    
    @database_sync_to_async
    def is_user_counselor(self):
        return self.user.role in ['counselor', 'admin']
    
    @database_sync_to_async
    def is_request_closed(self):
        from .models import HealthRequest
        try:
            health_request = HealthRequest.objects.get(id=self.request_id)
            return health_request.status == 'closed'
        except HealthRequest.DoesNotExist:
            return True
    
    @database_sync_to_async
    def get_anonymous_id(self):
        if hasattr(self.user, 'student_profile') and self.user.student_profile.anonymous_id:
            return self.user.student_profile.anonymous_id
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
            logger.error(f"Erreur sauvegarde message: {e}")
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
            logger.error(f"Erreur création timeline: {e}")
    
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
                
                is_counselor = self.user.role in ['counselor', 'admin']
                if is_counselor:
                    session.counselor_channel = self.channel_name
                else:
                    session.student_channel = self.channel_name
                
                session.last_activity = timezone.now()
                session.save()
        except Exception as e:
            logger.error(f"Erreur mise à jour session chat: {e}")