# health/services.py
import logging
import uuid
from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings
import re

from health.models import HealthRequest

logger = logging.getLogger(__name__)

# Tentative d'import Groq, avec fallback
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq non installé, utilisation du fallback uniquement")


class MCPHealthCategorizationTool:
    """
    MCP (Model Context Protocol) pour la catégorisation des messages de santé mentale
    """
    
    def __init__(self):
        self.client = None
        if GROQ_AVAILABLE and hasattr(settings, 'GROQ_API_KEY') and settings.GROQ_API_KEY:
            try:
                self.client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq client initialisé avec succès")
            except Exception as e:
                logger.error(f"Erreur initialisation Groq: {e}")
    
    def get_schema(self) -> Dict:
        """Retourne le schéma MCP pour l'outil de catégorisation"""
        return {
            'name': 'health_categorization',
            'description': 'Analyse et catégorise un message de santé mentale d\'un étudiant',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'description': 'Message de l\'étudiant'},
                    'age_group': {'type': 'string', 'description': 'Tranche d\'âge (13-15, 16-18, 18+)'}
                },
                'required': ['message']
            },
            'output_schema': {
                'type': 'object',
                'properties': {
                    'category': {'type': 'string', 'enum': ['stress', 'family', 'school', 'anxiety', 'other']},
                    'confidence': {'type': 'number', 'minimum': 0, 'maximum': 100},
                    'explanation': {'type': 'string'},
                    'keywords': {'type': 'array', 'items': {'type': 'string'}}
                }
            }
        }
    
    def _build_prompt(self, message: str, age_group: str = "") -> str:
        """Construit le prompt pour l'IA"""
        age_context = f" (tranche d'âge: {age_group})" if age_group else ""
        return f"""Analyse le message suivant d'un étudiant{age_context} et catégorise-le en fonction des problèmes de santé mentale.

Message: "{message}"

Catégories possibles:
- stress: stress scolaire, examens, pression académique, surcharge de travail
- family: problèmes familiaux, disputes parents, divorce, conflits à la maison
- school: harcèlement scolaire, relations avec les professeurs, problèmes avec les camarades
- anxiety: angoisses, crises d'angoisse, peurs, insomnie liée à l'anxiété
- other: autre sujet ne correspondant pas aux catégories ci-dessus

Réponds UNIQUEMENT avec un JSON valide au format suivant:
{{"category": "nom_categorie", "confidence": 85, "explanation": "Explication courte de pourquoi cette catégorie a été choisie", "keywords": ["mot1", "mot2"]}}

La confiance doit être un nombre entre 0 et 100.
L'explication doit être en français, lisible par un humain (2-3 phrases maximum).
Les keywords sont les mots-clés importants du message."""

    def _fallback_categorization(self, message: str) -> Dict:
        """Catégorisation par règles (fallback si IA indisponible)"""
        message_lower = message.lower()
        
        # Mots-clés par catégorie
        keywords = {
            'stress': ['stress', 'examen', 'révision', 'pression', 'note', 'bac', 'réussir', 'travail', 'charge'],
            'anxiety': ['angoisse', 'anxiété', 'peur', 'crise', 'panique', 'dormir', 'insomnie', 'vertige', 'cœur'],
            'family': ['parent', 'maman', 'papa', 'famille', 'dispute', 'divorce', 'frère', 'sœur', 'maison'],
            'school': ['harcèlement', 'prof', 'camarade', 'classe', 'école', 'lycée', 'collège', 'moquerie', 'exclu']
        }
        
        scores = {cat: 0 for cat in keywords}
        found_keywords = []
        
        for cat, words in keywords.items():
            for word in words:
                if word in message_lower:
                    scores[cat] += 20
                    found_keywords.append(word)
        
        # Catégorie avec le score le plus élevé
        if max(scores.values()) > 0:
            category = max(scores, key=scores.get)
            confidence = min(40 + scores[category], 85)
        else:
            category = 'other'
            confidence = 50
        
        # Générer explication
        explanations = {
            'stress': "Le message contient des mots-clés liés au stress scolaire ou à la pression académique.",
            'anxiety': "Le message évoque des signes d'anxiété ou d'angoisse.",
            'family': "Le message fait référence à des problèmes ou conflits familiaux.",
            'school': "Le message mentionne des difficultés liées à l'environnement scolaire.",
            'other': "Le message ne correspond pas clairement aux catégories prédéfinies."
        }
        
        return {
            'category': category,
            'confidence': confidence,
            'explanation': explanations.get(category, "Message analysé automatiquement."),
            'keywords': list(set(found_keywords[:5]))
        }
    
    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse la réponse JSON de l'IA"""
        import json
        
        # Nettoyer la réponse (enlever les backticks et balises code)
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        elif response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        try:
            result = json.loads(response_text)
            # Validation des champs requis
            if 'category' in result and 'confidence' in result and 'explanation' in result:
                # Normaliser la catégorie
                if result['category'] not in ['stress', 'family', 'school', 'anxiety', 'other']:
                    result['category'] = 'other'
                # Limiter la confiance
                result['confidence'] = max(0, min(100, result['confidence']))
                return result
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON: {e}")
        
        return None
    
    def categorize(self, message: str, age_group: str = "", trace_id: str = "") -> Dict:
        """
        Catégorise un message en utilisant l'IA (Groq) ou fallback
        
        Args:
            message: Le message de l'étudiant
            age_group: Tranche d'âge (optionnel)
            trace_id: ID de traçabilité
        
        Returns:
            Dict avec category, confidence, explanation, keywords, used_fallback
        """
        result = {
            'category': 'other',
            'confidence': 50,
            'explanation': "Analyse automatique du message.",
            'keywords': [],
            'trace_id': trace_id or str(uuid.uuid4()),
            'used_fallback': True
        }
        
        # Tentative d'appel API si client disponible
        if self.client:
            try:
                prompt = self._build_prompt(message, age_group)
                
                response = self.client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[
                        {"role": "system", "content": "Tu es un assistant spécialisé dans l'analyse de messages de santé mentale. Tu réponds UNIQUEMENT en JSON valide."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                response_text = response.choices[0].message.content
                parsed = self._parse_response(response_text)
                
                if parsed:
                    result.update(parsed)
                    result['used_fallback'] = False
                    logger.info(f"Catégorisation IA réussie: {result['category']} ({result['confidence']}%)")
                    
                    # Enregistrement d'un audit pour traçabilité MCP
                    self._log_mcp_call(trace_id, message, result)
                    return result
                    
            except Exception as e:
                logger.error(f"Erreur appel Groq: {e}")
        
        # Fallback par règles
        logger.info(f"Utilisation du fallback pour catégorisation")
        fallback = self._fallback_categorization(message)
        result.update(fallback)
        result['used_fallback'] = True
        
        return result
    
    def _log_mcp_call(self, trace_id: str, message: str, result: Dict):
        """Log l'appel MCP pour traçabilité"""
        try:
            from .models import AuditLog
            import json
            AuditLog.objects.create(
                user=None,  # Appel système
                action='security_violation',  # Réutilisons pour la traçabilité
                resource='mcp_call',
                details={
                    'trace_id': trace_id,
                    'message_preview': message[:100],
                    'result': result
                }
            )
        except Exception as e:
            logger.error(f"Erreur log MCP: {e}")


class HealthService:
    """Service pour la gestion des demandes santé mentale"""
    
    def __init__(self):
        self.mcp = MCPHealthCategorizationTool()
    
    def create_request(self, student, message: str, category: str = None, age_group: str = "") -> 'HealthRequest':
        """
        Crée une demande de santé avec catégorisation IA automatique
        """
        from .models import HealthRequest, HealthTimelineEvent, Message as ChatMessage
        from django.utils import timezone
        import uuid
        
        # 1. Catégorisation IA du message
        trace_id = str(uuid.uuid4())
        ai_result = self.mcp.categorize(message, age_group, trace_id)
        
        # Si l'utilisateur a forcé une catégorie (formulaire), on l'utilise comme override implicite
        if category and category != 'other' and ai_result.get('used_fallback', False):
            # Si fallback, on donne plus de poids à la catégorie choisie par l'étudiant
            ai_result['category'] = category
            ai_result['confidence'] = 70
            ai_result['explanation'] = f"L'étudiant a choisi la catégorie '{category}' comme sujet principal."
        
        # Récupérer l'ID anonyme
        anonymous_id = f"Étudiant #{student.id}"
        if hasattr(student, 'student_profile') and student.student_profile.anonymous_id:
            anonymous_id = student.student_profile.anonymous_id
        
        now = timezone.now()
        
        # 2. Créer la demande
        health_request = HealthRequest.objects.create(
            id=uuid.uuid4(),
            student=student,
            anonymous_id=anonymous_id,
            ai_category=ai_result['category'],
            ai_confidence=ai_result['confidence'],
            ai_explanation=ai_result['explanation'],
            ai_trace_id=trace_id,
            status='pending',
            urgency_level='low',
            student_age_group=age_group,
            created_at=now,
            updated_at=now,
            closure_summary=''
        )
        
        # 3. Créer le message initial
        ChatMessage.objects.create(
            health_request=health_request,
            sender=anonymous_id,
            sender_role='student',
            content=message,
            created_at=now
        )
        
        # 4. Timeline: création
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='created',
            actor=anonymous_id,
            action=f"Ouverture de la demande par {anonymous_id}",
            created_at=now
        )
        
        # 5. Timeline: catégorisation IA
        confidence_display = f"{ai_result['confidence']:.0f}%" if ai_result['confidence'] else "?"
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='ia_categorized',
            actor="IA (Groq via MCP)",
            action=f"Catégorisation: {health_request.get_effective_category_display()} (confiance {confidence_display})",
            detail=ai_result['explanation'],
            created_at=now
        )
        
        # 6. Ajuster urgence si nécessaire
        if ai_result['category'] in ['anxiety', 'stress'] and ai_result['confidence'] > 80:
            health_request.urgency_level = 'high'
            health_request.save()
        
        logger.info(f"Demande santé créée: {health_request.id} - catégorie {ai_result['category']}")
        
        return health_request
    
    def assign_counselor(self, request_id, counselor):
        """Assigne un conseiller à une demande"""
        from .models import HealthRequest, HealthTimelineEvent
        from django.utils import timezone
        
        health_request = HealthRequest.objects.get(id=request_id)
        
        if health_request.status == 'pending':
            old_status = health_request.status
            health_request.counselor = counselor
            health_request.status = 'in_progress'
            health_request.save()
            
            # Récupérer le nom anonyme pour l'affichage
            anonymous_display = health_request.anonymous_id
            
            HealthTimelineEvent.objects.create(
                health_request=health_request,
                event_type='assigned',
                actor=f"Conseiller {counselor.first_name or counselor.username}",
                action=f"Prise en charge de {anonymous_display}",
                detail=f"Statut: {old_status} → en cours",
                created_at=timezone.now()
            )
            
            logger.info(f"Demande {request_id} assignée à {counselor.username}")
        
        return health_request
    
    def close_request(self, request_id, counselor, summary: str = ""):
        """Clôture une demande"""
        from .models import HealthRequest, HealthTimelineEvent
        from django.utils import timezone
        
        health_request = HealthRequest.objects.get(id=request_id)
        
        if health_request.status != 'closed':
            health_request.status = 'closed'
            health_request.closed_at = timezone.now()
            health_request.closure_summary = summary
            health_request.save()
            
            HealthTimelineEvent.objects.create(
                health_request=health_request,
                event_type='closed',
                actor=f"Conseiller {counselor.first_name or counselor.username}",
                action="Demande clôturée",
                detail=summary or "Accompagnement terminé",
                created_at=timezone.now()
            )
            
            logger.info(f"Demande {request_id} clôturée par {counselor.username}")
        
        return health_request
    
    def override_category(self, request_id, counselor, new_category: str):
        """
        Override de catégorie par un conseiller (Human in the loop)
        Track E - IA explicable avec correction humaine
        """
        from .models import HealthRequest, HealthTimelineEvent, AuditLog
        from django.utils import timezone
        
        health_request = HealthRequest.objects.get(id=request_id)
        old_category = health_request.get_effective_category()
        old_display = health_request.get_effective_category_display()
        
        health_request.overridden_category = new_category
        health_request.overridden_by = counselor
        health_request.overridden_at = timezone.now()
        health_request.save()
        
        # Timeline
        new_display = dict(HealthRequest.CATEGORY_CHOICES).get(new_category, new_category)
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='ia_override',
            actor=f"Conseiller {counselor.first_name or counselor.username}",
            action=f"Override catégorie IA: {old_display} → {new_display}",
            detail=f"L'IA avait proposé {old_display} avec une confiance de {health_request.ai_confidence:.0f}%. Le conseiller a corrigé manuellement.",
            created_at=timezone.now()
        )
        
        # Audit log pour traçabilité
        AuditLog.objects.create(
            user=counselor,
            action='override_category',
            resource=str(health_request.id),
            ip_address=None,
            details={
                'old_category': old_category,
                'new_category': new_category,
                'ai_confidence': health_request.ai_confidence,
                'ai_explanation': health_request.ai_explanation
            },
            created_at=timezone.now()
        )
        
        logger.info(f"Override catégorie demande {request_id}: {old_category} → {new_category} par {counselor.username}")
        
        return health_request
    
    def log_security_violation(self, user, request_id, ip_address, user_agent):
        """Log une tentative de violation de sécurité"""
        from .models import AuditLog
        from django.utils import timezone
        
        return AuditLog.objects.create(
            user=user,
            action='view_identity',
            resource=str(request_id),
            ip_address=ip_address,
            user_agent=user_agent,
            details={'attempt': 'view_real_identity', 'blocked': True},
            created_at=timezone.now()
        )