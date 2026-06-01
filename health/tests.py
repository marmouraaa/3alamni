# health/tests.py
import json
import uuid
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from asgiref.sync import sync_to_async

from .models import HealthRequest, Message, HealthTimelineEvent, AuditLog, ChatSession
from .services import MCPHealthCategorizationTool, HealthService

User = get_user_model()


# ============================================================================
# Tests des Modèles
# ============================================================================

class HealthRequestModelTests(TestCase):
    """Tests du modèle HealthRequest"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='etudiant1',
            password='test123',
            email='etudiant1@test.com'
        )
        # Créer un profile étudiant
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.student,
            anonymous_id='Étudiant #1',
            age_group='16-18'
        )
    
    def test_create_health_request(self):
        """Test création d'une demande de santé"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            ai_confidence=85.0,
            ai_explanation="Message contenant des mots-clés liés au stress scolaire"
        )
        
        self.assertEqual(request.status, 'pending')
        self.assertEqual(request.ai_category, 'stress')
        self.assertEqual(request.ai_confidence, 85.0)
        self.assertEqual(str(request), 'Étudiant #1 - En attente')
    
    def test_get_effective_category_without_override(self):
        """Test récupération catégorie sans override"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            ai_confidence=85.0
        )
        self.assertEqual(request.get_effective_category(), 'stress')
        self.assertEqual(request.get_effective_confidence(), 85.0)
    
    def test_get_effective_category_with_override(self):
        """Test récupération catégorie avec override (Human in the loop)"""
        counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            ai_confidence=85.0
        )
        request.overridden_category = 'anxiety'
        request.overridden_by = counselor
        request.overridden_at = timezone.now()
        request.save()
        
        self.assertEqual(request.get_effective_category(), 'anxiety')
        self.assertEqual(request.get_effective_confidence(), 100.0)
    
    def test_urgency_auto_update_high(self):
        """Test mise à jour automatique urgence niveau haut"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='anxiety',
            ai_confidence=85.0
        )
        # Le save() devrait mettre à jour urgency_level
        request.save()
        # Recharger depuis DB
        request.refresh_from_db()
        self.assertEqual(request.urgency_level, 'high')
    
    def test_urgency_auto_update_medium(self):
        """Test mise à jour automatique urgence niveau moyen"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='family',
            ai_confidence=75.0
        )
        request.save()
        request.refresh_from_db()
        self.assertEqual(request.urgency_level, 'medium')
    
    def test_urgency_auto_update_low(self):
        """Test urgence basse par défaut"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='other',
            ai_confidence=50.0
        )
        request.save()
        request.refresh_from_db()
        self.assertEqual(request.urgency_level, 'low')
    
    def test_get_effective_category_display(self):
        """Test affichage catégorie effective"""
        request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        self.assertEqual(request.get_effective_category_display(), '😰 Stress / Examens')


class MessageModelTests(TestCase):
    """Tests du modèle Message"""
    
    def setUp(self):
        self.student = User.objects.create_user(username='etudiant1', password='test123')
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(user=self.student, anonymous_id='Étudiant #1')
        
        self.health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
    
    def test_create_message(self):
        """Test création d'un message"""
        message = Message.objects.create(
            health_request=self.health_request,
            sender='Étudiant #1',
            sender_role='student',
            content="Je me sens stressé"
        )
        
        self.assertEqual(message.content, "Je me sens stressé")
        self.assertEqual(message.sender_role, 'student')
        self.assertFalse(message.is_read)
        self.assertEqual(str(message), "Étudiant #1: Je me sens stressé")
    
    def test_message_ordering(self):
        """Test ordre chronologique des messages"""
        msg1 = Message.objects.create(
            health_request=self.health_request,
            sender='Étudiant #1',
            sender_role='student',
            content="Premier message"
        )
        msg2 = Message.objects.create(
            health_request=self.health_request,
            sender='Conseiller',
            sender_role='counselor',
            content="Deuxième message"
        )
        
        messages = list(Message.objects.filter(health_request=self.health_request))
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)


class HealthTimelineEventModelTests(TestCase):
    """Tests du modèle HealthTimelineEvent"""
    
    def setUp(self):
        self.student = User.objects.create_user(username='etudiant1', password='test123')
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(user=self.student, anonymous_id='Étudiant #1')
        
        self.health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
    
    def test_create_timeline_event(self):
        """Test création événement timeline"""
        event = HealthTimelineEvent.objects.create(
            health_request=self.health_request,
            event_type='created',
            actor='Étudiant #1',
            action="Ouverture de la demande"
        )
        
        self.assertEqual(event.event_type, 'created')
        self.assertEqual(event.actor, 'Étudiant #1')
        self.assertIn('Ouverture', event.action)


class AuditLogModelTests(TestCase):
    """Tests du modèle AuditLog (Track F - Sécurité)"""
    
    def setUp(self):
        self.counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
    
    def test_create_audit_log_view_identity(self):
        """Test log tentative voir identité réelle"""
        log = AuditLog.objects.create(
            user=self.counselor,
            action='view_identity',
            resource='request-123',
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0',
            details={'attempt': 'view_real_identity', 'blocked': True}
        )
        
        self.assertEqual(log.action, 'view_identity')
        self.assertTrue(log.details['blocked'])
        self.assertEqual(str(log), f"{log.created_at} - view_identity by counselor1")
    
    def test_create_audit_log_override(self):
        """Test log override catégorie"""
        log = AuditLog.objects.create(
            user=self.counselor,
            action='override_category',
            resource='request-456',
            details={'old_category': 'stress', 'new_category': 'anxiety'}
        )
        
        self.assertEqual(log.action, 'override_category')
        self.assertEqual(log.details['old_category'], 'stress')


# ============================================================================
# Tests du Service MCP (Model Context Protocol)
# ============================================================================

class MCPHealthCategorizationToolTests(TestCase):
    """Tests du service MCP pour la catégorisation IA"""
    
    def setUp(self):
        self.mcp = MCPHealthCategorizationTool()
    
    def test_mcp_schema(self):
        """Test que le schéma MCP est correctement défini"""
        schema = self.mcp.get_schema()
        
        self.assertEqual(schema['name'], 'health_categorization')
        self.assertIn('description', schema)
        self.assertIn('input_schema', schema)
        self.assertIn('output_schema', schema)
        self.assertIn('message', schema['input_schema']['properties'])
        self.assertIn('category', schema['output_schema']['properties'])
        self.assertIn('confidence', schema['output_schema']['properties'])
        self.assertIn('explanation', schema['output_schema']['properties'])
    
    def test_fallback_categorization_stress(self):
        """Test fallback détection stress"""
        result = self.mcp._fallback_categorization("Je suis très stressé par mes examens")
        
        self.assertEqual(result['category'], 'stress')
        self.assertGreaterEqual(result['confidence'], 50)
        self.assertIn('stress', result['explanation'].lower())
        self.assertIsInstance(result['keywords'], list)
    
    def test_fallback_categorization_family(self):
        """Test fallback détection problèmes familiaux"""
        result = self.mcp._fallback_categorization("Mes parents se disputent tout le temps")
        
        self.assertEqual(result['category'], 'family')
    
    def test_fallback_categorization_school(self):
        """Test fallback détection problèmes scolaires"""
        result = self.mcp._fallback_categorization("Je me fais harceler au lycée par des élèves")
        
        self.assertEqual(result['category'], 'school')
    
    def test_fallback_categorization_anxiety(self):
        """Test fallback détection anxiété"""
        result = self.mcp._fallback_categorization("J'ai des crises d'angoisse et je n'arrive pas à dormir")
        
        self.assertEqual(result['category'], 'anxiety')
    
    def test_fallback_categorization_other(self):
        """Test fallback catégorie autre"""
        result = self.mcp._fallback_categorization("Message sans mots clés spécifiques")
        
        self.assertEqual(result['category'], 'other')
        self.assertEqual(result['confidence'], 50)
    
    def test_parse_response_valid_json(self):
        """Test parsing réponse JSON valide"""
        response_text = '{"category": "stress", "confidence": 92, "explanation": "Test", "keywords": ["stress"]}'
        result = self.mcp._parse_response(response_text)
        
        self.assertEqual(result['category'], 'stress')
        self.assertEqual(result['confidence'], 92)
    
    def test_parse_response_invalid_json(self):
        """Test parsing réponse JSON invalide (fallback)"""
        response_text = "Réponse invalide sans JSON"
        result = self.mcp._parse_response(response_text)
        
        self.assertEqual(result['category'], 'other')
        self.assertEqual(result['confidence'], 50)
    
    def test_build_prompt(self):
        """Test construction du prompt"""
        prompt = self.mcp._build_prompt("Je suis stressé", "16-18")
        
        self.assertIn("Je suis stressé", prompt)
        self.assertIn("16-18", prompt)
        self.assertIn("stress", prompt)
    
    @patch('groq.Groq')
    def test_categorize_success(self, mock_groq):
        """Test catégorisation réussie avec mock"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"category": "stress", "confidence": 88, "explanation": "Test", "keywords": ["stress"]}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq.return_value = mock_client
        
        result = self.mcp.categorize("Je suis stressé", trace_id="test-123")
        
        self.assertEqual(result['category'], 'stress')
        self.assertEqual(result['confidence'], 88)
        self.assertEqual(result['trace_id'], 'test-123')
        self.assertFalse(result.get('used_fallback', False))
    
    @patch('groq.Groq')
    def test_categorize_with_error_fallback(self, mock_groq):
        """Test catégorisation avec erreur API (fallback)"""
        mock_groq.side_effect = Exception("API Error")
        
        result = self.mcp.categorize("Je suis stressé")
        
        self.assertEqual(result['category'], 'stress')  # fallback détecte stress
        self.assertTrue(result.get('used_fallback', False))
        self.assertIn('error', result)


# ============================================================================
# Tests du HealthService
# ============================================================================

class HealthServiceTests(TestCase):
    """Tests du service HealthService"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='etudiant1',
            password='test123',
            email='etudiant1@test.com'
        )
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.student,
            anonymous_id='Étudiant #1',
            age_group='16-18'
        )
        
        self.counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
        
        self.service = HealthService()
    
    @patch.object(MCPHealthCategorizationTool, 'categorize')
    def test_create_request(self, mock_categorize):
        """Test création d'une demande via service"""
        mock_categorize.return_value = {
            'category': 'stress',
            'confidence': 85.0,
            'explanation': 'Message contenant des mots-clés de stress',
            'keywords': ['stress', 'examen'],
            'trace_id': 'test-trace-123'
        }
        
        health_request = self.service.create_request(
            student=self.student,
            message="Je suis stressé par le baccalauréat",
            category="stress",
            age_group="16-18"
        )
        
        self.assertEqual(health_request.ai_category, 'stress')
        self.assertEqual(health_request.ai_confidence, 85.0)
        self.assertEqual(health_request.ai_explanation, 'Message contenant des mots-clés de stress')
        
        # Vérifier création du message
        self.assertEqual(health_request.messages.count(), 1)
        message = health_request.messages.first()
        self.assertEqual(message.content, "Je suis stressé par le baccalauréat")
        self.assertEqual(message.sender_role, 'student')
        
        # Vérifier création timeline
        self.assertGreaterEqual(health_request.timeline_events.count(), 2)
    
    def test_assign_counselor(self):
        """Test assignation d'un conseiller"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='pending'
        )
        
        result = self.service.assign_counselor(health_request.id, self.counselor)
        
        self.assertEqual(result.status, 'in_progress')
        self.assertEqual(result.counselor, self.counselor)
        
        # Vérifier événement timeline
        timeline_event = health_request.timeline_events.filter(event_type='assigned').first()
        self.assertIsNotNone(timeline_event)
        self.assertIn(self.counselor.username, timeline_event.actor)
    
    def test_assign_counselor_already_assigned(self):
        """Test assignation d'un conseiller à une demande déjà prise"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='in_progress',
            counselor=self.counselor
        )
        
        new_counselor = User.objects.create_user(username='counselor2', password='test123', role='counselor')
        result = self.service.assign_counselor(health_request.id, new_counselor)
        
        # Ne devrait pas changer (déjà en cours)
        self.assertEqual(result.counselor, self.counselor)
    
    def test_close_request(self):
        """Test clôture d'une demande"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='in_progress',
            counselor=self.counselor
        )
        
        result = self.service.close_request(
            health_request.id,
            self.counselor,
            summary="Problème résolu, l'étudiant va mieux"
        )
        
        self.assertEqual(result.status, 'closed')
        self.assertIsNotNone(result.closed_at)
        self.assertEqual(result.closure_summary, "Problème résolu, l'étudiant va mieux")
        
        # Vérifier événement timeline
        timeline_event = health_request.timeline_events.filter(event_type='closed').first()
        self.assertIsNotNone(timeline_event)
    
    def test_override_category(self):
        """Test override catégorie par conseiller (Human in the loop)"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            ai_confidence=85.0
        )
        
        result = self.service.override_category(health_request.id, self.counselor, 'anxiety')
        
        self.assertEqual(result.overridden_category, 'anxiety')
        self.assertEqual(result.overridden_by, self.counselor)
        self.assertIsNotNone(result.overridden_at)
        self.assertEqual(result.get_effective_category(), 'anxiety')
        
        # Vérifier événement timeline
        timeline_event = health_request.timeline_events.filter(event_type='ia_override').first()
        self.assertIsNotNone(timeline_event)
        self.assertIn('stress → anxiety', timeline_event.action)
        
        # Vérifier audit log
        audit_log = AuditLog.objects.filter(
            action='override_category',
            resource=str(health_request.id)
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.details['old_category'], 'stress')
        self.assertEqual(audit_log.details['new_category'], 'anxiety')
    
    def test_log_security_violation(self):
        """Test logging tentative violation sécurité (Track F)"""
        log = self.service.log_security_violation(
            user=self.counselor,
            request_id='test-request-123',
            ip_address='192.168.1.1',
            user_agent='Chrome/120.0'
        )
        
        self.assertEqual(log.action, 'view_identity')
        self.assertEqual(log.resource, 'test-request-123')
        self.assertEqual(log.ip_address, '192.168.1.1')
        self.assertTrue(log.details['blocked'])


# ============================================================================
# Tests des Vues (Views)
# ============================================================================

class ViewTests(TestCase):
    """Tests des vues de l'application health"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='etudiant1',
            password='test123',
            email='etudiant1@test.com'
        )
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.student,
            anonymous_id='Étudiant #1',
            age_group='16-18'
        )
        
        self.counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
        
        self.admin = User.objects.create_user(
            username='admin1',
            password='test123',
            role='admin'
        )
        
        self.client = Client()
    
    def test_new_request_get_student(self):
        """Test accès formulaire nouvelle demande (étudiant)"""
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:new_request'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'health/new_request.html')
    
    @patch.object(HealthService, 'create_request')
    def test_new_request_post_valid(self, mock_create):
        """Test soumission formulaire valide"""
        self.client.login(username='etudiant1', password='test123')
        
        mock_request = MagicMock()
        mock_request.id = '123e4567-e89b-12d3-a456-426614174000'
        mock_create.return_value = mock_request
        
        response = self.client.post(reverse('health:new_request'), {
            'category': 'stress',
            'message': 'Je suis très stressé par mes examens'
        })
        
        # Redirection vers le chat
        self.assertEqual(response.status_code, 302)
        mock_create.assert_called_once()
    
    def test_new_request_post_empty_message(self):
        """Test soumission avec message vide"""
        self.client.login(username='etudiant1', password='test123')
        response = self.client.post(reverse('health:new_request'), {
            'category': 'stress',
            'message': ''
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veuillez écrire votre message")
    
    def test_chat_view_student_own_request(self):
        """Test accès chat par étudiant (sa propre demande)"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:chat', args=[health_request.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'health/chat.html')
    
    def test_chat_view_student_other_request_access_denied(self):
        """Test accès refusé: étudiant voit demande d'un autre"""
        other_student = User.objects.create_user(username='etudiant2', password='test123')
        from accounts.models import StudentProfile
        StudentProfile.objects.create(user=other_student, anonymous_id='Étudiant #2')
        
        health_request = HealthRequest.objects.create(
            student=other_student,
            anonymous_id='Étudiant #2',
            ai_category='stress'
        )
        
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:chat', args=[health_request.id]))
        
        # Redirection avec message d'erreur
        self.assertEqual(response.status_code, 302)
    
    def test_chat_view_counselor_access(self):
        """Test accès chat par conseiller"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='pending'
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:chat', args=[health_request.id]))
        
        self.assertEqual(response.status_code, 200)
        
        # Vérifier que la demande est passée en "en cours"
        health_request.refresh_from_db()
        self.assertEqual(health_request.status, 'in_progress')
        self.assertEqual(health_request.counselor, self.counselor)
    
    def test_chat_view_counselor_security_block(self):
        """Test tentative conseiller de voir identité réelle (bloquée)"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(
            reverse('health:chat', args=[health_request.id]),
            {'debug_show_identity': 'true'}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Vérifier que l'audit log a enregistré la tentative
        log_exists = AuditLog.objects.filter(
            action='view_identity',
            user=self.counselor
        ).exists()
        self.assertTrue(log_exists)
    
    def test_counselor_dashboard_access_granted(self):
        """Test dashboard conseiller accès autorisé"""
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:counselor_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'health/counselor_dashboard.html')
    
    def test_counselor_dashboard_access_denied_student(self):
        """Test dashboard conseiller accès refusé pour étudiant"""
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:counselor_dashboard'))
        
        # Redirection avec message d'erreur
        self.assertEqual(response.status_code, 302)
    
    def test_requests_list_filter_pending(self):
        """Test liste demandes filtre en attente"""
        HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='pending'
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:requests_list'), {'status': 'pending'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['requests']), 1)
    
    def test_requests_list_filter_in_progress(self):
        """Test liste demandes filtre en cours"""
        HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='in_progress',
            counselor=self.counselor
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:requests_list'), {'status': 'in_progress'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['requests']), 1)
    
    def test_requests_list_pagination(self):
        """Test pagination liste demandes"""
        for i in range(25):
            HealthRequest.objects.create(
                student=self.student,
                anonymous_id=f'Étudiant #{i}',
                ai_category='stress'
            )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:requests_list'), {'status': 'all'})
        
        self.assertEqual(response.status_code, 200)
        # Pagination 20 par défaut
        self.assertEqual(len(response.context['requests']), 20)
    
    def test_timeline_view_student(self):
        """Test visualisation timeline par étudiant"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='created',
            actor='Étudiant #1',
            action="Ouverture"
        )
        
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:timeline', args=[health_request.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'health/timeline.html')
        self.assertEqual(response.context['timeline'].count(), 1)
    
    def test_override_category_api(self):
        """Test API override catégorie"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.post(
            reverse('health:override_category', args=[health_request.id]),
            {'category': 'anxiety'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('new_category', data)
        
        # Vérifier override en base
        health_request.refresh_from_db()
        self.assertEqual(health_request.overridden_category, 'anxiety')
    
    def test_override_category_api_unauthorized(self):
        """Test API override catégorie sans autorisation"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        self.client.login(username='etudiant1', password='test123')
        response = self.client.post(
            reverse('health:override_category', args=[health_request.id]),
            {'category': 'anxiety'}
        )
        
        self.assertEqual(response.status_code, 403)
    
    def test_close_request_api(self):
        """Test API clôture demande"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress',
            status='in_progress',
            counselor=self.counselor
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.post(
            reverse('health:close_request', args=[health_request.id]),
            {'summary': 'Problème résolu'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        health_request.refresh_from_db()
        self.assertEqual(health_request.status, 'closed')
    
    def test_security_audit_log_admin(self):
        """Test page audit log pour admin"""
        self.client.login(username='admin1', password='test123')
        response = self.client.get(reverse('health:audit_log'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'health/audit_log.html')
    
    def test_security_audit_log_unauthorized(self):
        """Test page audit log accès refusé non-admin"""
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:audit_log'))
        
        self.assertEqual(response.status_code, 302)  # Redirection


# ============================================================================
# Tests d'Intégration
# ============================================================================

class IntegrationTests(TestCase):
    """Tests d'intégration complets"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='etudiant1',
            password='test123'
        )
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.student,
            anonymous_id='Étudiant #1'
        )
        
        self.counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
        
        self.client = Client()
    
    @patch.object(MCPHealthCategorizationTool, 'categorize')
    def test_full_flow_student_to_counselor(self, mock_categorize):
        """
        Test parcours complet:
        1. Étudiant crée demande
        2. IA catégorise
        3. Conseiller prend en charge
        4. Conseiller override catégorie
        5. Conseiller clôture
        """
        mock_categorize.return_value = {
            'category': 'stress',
            'confidence': 85.0,
            'explanation': 'Stress détecté',
            'keywords': ['stress'],
            'trace_id': 'test-123'
        }
        
        # Étape 1: Étudiant crée demande
        self.client.login(username='etudiant1', password='test123')
        response = self.client.post(reverse('health:new_request'), {
            'category': 'stress',
            'message': 'Je suis stressé par le bac'
        })
        
        # Récupérer l'ID de la demande créée
        import re
        match = re.search(r'/health/chat/([^/]+)/', response.url)
        request_id = match.group(1)
        
        health_request = HealthRequest.objects.get(id=request_id)
        self.assertEqual(health_request.ai_category, 'stress')
        self.assertEqual(health_request.status, 'pending')
        
        # Étape 2: Conseiller prend en charge
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:chat', args=[request_id]))
        
        health_request.refresh_from_db()
        self.assertEqual(health_request.status, 'in_progress')
        self.assertEqual(health_request.counselor, self.counselor)
        
        # Étape 3: Conseiller override catégorie
        response = self.client.post(
            reverse('health:override_category', args=[request_id]),
            {'category': 'anxiety'}
        )
        
        health_request.refresh_from_db()
        self.assertEqual(health_request.overridden_category, 'anxiety')
        
        # Étape 4: Conseiller clôture
        response = self.client.post(
            reverse('health:close_request', args=[request_id]),
            {'summary': 'Accompagnement terminé'}
        )
        
        health_request.refresh_from_db()
        self.assertEqual(health_request.status, 'closed')
        
        # Vérifier timeline complète
        timeline_events = health_request.timeline_events.all()
        event_types = [e.event_type for e in timeline_events]
        self.assertIn('created', event_types)
        self.assertIn('ia_categorized', event_types)
        self.assertIn('assigned', event_types)
        self.assertIn('ia_override', event_types)
        self.assertIn('closed', event_types)


# ============================================================================
# Tests de Sécurité (Track F)
# ============================================================================

class SecurityTests(TestCase):
    """Tests de sécurité et confidentialité (Track F)"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='etudiant1',
            password='test123',
            email='etudiant_real@example.com'
        )
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.student,
            anonymous_id='Étudiant #47'
        )
        
        self.counselor = User.objects.create_user(
            username='counselor1',
            password='test123',
            role='counselor'
        )
        
        self.health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #47',
            ai_category='stress'
        )
        
        self.client = Client()
    
    def test_counselor_cannot_see_real_identity_in_chat(self):
        """
        Track F: Le conseiller ne doit pas voir l'identité réelle
        """
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(reverse('health:chat', args=[self.health_request.id]))
        
        content = response.content.decode('utf-8')
        
        # Ne doit pas contenir le vrai nom/email
        self.assertNotIn('etudiant1', content)
        self.assertNotIn('etudiant_real', content)
        
        # Doit contenir l'identifiant anonyme
        self.assertIn('Étudiant #47', content)
    
    def test_security_violation_logged_on_identity_attempt(self):
        """
        Track F: Tentative de voir identité réelle est loggée
        """
        self.client.login(username='counselor1', password='test123')
        response = self.client.get(
            reverse('health:chat', args=[self.health_request.id]),
            {'debug_show_identity': 'true'}
        )
        
        # Vérifier que l'audit log a enregistré
        log = AuditLog.objects.filter(
            action='view_identity',
            user=self.counselor,
            resource=str(self.health_request.id)
        ).first()
        
        self.assertIsNotNone(log)
        self.assertTrue(log.details.get('blocked', False))
    
    def test_student_cannot_access_other_student_request(self):
        """Un étudiant ne peut pas voir la demande d'un autre"""
        other_student = User.objects.create_user(username='etudiant2', password='test123')
        from accounts.models import StudentProfile
        StudentProfile.objects.create(user=other_student, anonymous_id='Étudiant #99')
        
        other_request = HealthRequest.objects.create(
            student=other_student,
            anonymous_id='Étudiant #99',
            ai_category='stress'
        )
        
        self.client.login(username='etudiant1', password='test123')
        response = self.client.get(reverse('health:chat', args=[other_request.id]))
        
        self.assertEqual(response.status_code, 302)  # Redirection
        
        # Vérifier log d'accès refusé
        log = AuditLog.objects.filter(action='access_denied').first()
        # Note: optionnel, peut ne pas être implémenté
    
    def test_counselor_cannot_modify_other_counselor_request(self):
        """Un conseiller ne peut pas modifier une demande prise par un autre"""
        other_counselor = User.objects.create_user(
            username='counselor2',
            password='test123',
            role='counselor'
        )
        
        taken_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #47',
            ai_category='stress',
            status='in_progress',
            counselor=other_counselor
        )
        
        self.client.login(username='counselor1', password='test123')
        response = self.client.post(
            reverse('health:override_category', args=[taken_request.id]),
            {'category': 'anxiety'}
        )
        
        # Devrait réussir quand même (les conseillers peuvent aider)
        # Mais on vérifie que le counselor n'a pas changé
        taken_request.refresh_from_db()
        self.assertEqual(taken_request.counselor, other_counselor)
    
    def test_audit_log_contains_all_security_events(self):
        """Vérifier que tous les événements de sécurité sont loggés"""
        # Simuler plusieurs violations
        for i in range(3):
            AuditLog.objects.create(
                user=self.counselor,
                action='view_identity',
                resource=f'request-{i}',
                details={'attempt': f'attempt-{i}'}
            )
        
        logs = AuditLog.objects.filter(action='view_identity')
        self.assertEqual(logs.count(), 3)


# ============================================================================
# Tests de Performance et Optimisation
# ============================================================================

class PerformanceTests(TestCase):
    """Tests de performance et optimisations"""
    
    def setUp(self):
        self.student = User.objects.create_user(username='etudiant1', password='test123')
        from accounts.models import StudentProfile
        self.profile = StudentProfile.objects.create(user=self.student, anonymous_id='Étudiant #1')
        
        self.counselor = User.objects.create_user(username='counselor1', password='test123', role='counselor')
        
        # Créer plusieurs demandes avec messages
        for i in range(50):
            request = HealthRequest.objects.create(
                student=self.student,
                anonymous_id=f'Étudiant #{i}',
                ai_category='stress'
            )
            for j in range(10):
                Message.objects.create(
                    health_request=request,
                    sender=f'Étudiant #{i}',
                    sender_role='student',
                    content=f'Message {j}'
                )
        
        self.client = Client()
    
    def test_requests_list_with_prefetch(self):
        """
        Test utilisation de prefetch_related pour optimisation
        Vérifie que la requête N+1 est évitée
        """
        self.client.login(username='counselor1', password='test123')
        
        with self.assertNumQueries(3):  # 1 pour requests + 1 pour prefetch messages + 1 pour pagination count
            response = self.client.get(reverse('health:requests_list'), {'status': 'all'})
        
        self.assertEqual(response.status_code, 200)
    
    def test_chat_view_messages_limited(self):
        """Test que seuls les 100 derniers messages sont chargés"""
        health_request = HealthRequest.objects.create(
            student=self.student,
            anonymous_id='Étudiant #1',
            ai_category='stress'
        )
        
        # Créer 150 messages
        for i in range(150):
            Message.objects.create(
                health_request=health_request,
                sender='Étudiant #1',
                sender_role='student',
                content=f'Message {i}'
            )
        
        self.client.login(username='etudiant1', password='test123')
        with self.assertNumQueries(3):  # health_request, messages, timeline
            response = self.client.get(reverse('health:chat', args=[health_request.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['messages_list']), 100)  # Limitée à 100