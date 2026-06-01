# audit/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class AuditLog(models.Model):
    """
    Journal d'audit pour tracer toutes les actions importantes
    """
    
    # Types d'actions
    ACTION_CHOICES = [
        # Early Warning actions
        ('import_csv', 'Import CSV'),
        ('import_csv_error', 'Import CSV - Erreur'),
        ('import_csv_malformed', 'Import CSV - Malformé'),
        ('update_threshold_config', 'Modification des seuils'),
        ('create_intervention', 'Création intervention'),
        ('update_intervention_status', 'MAJ statut intervention'),
        ('export_csv', 'Export CSV'),
        ('export_pdf', 'Export PDF'),
        ('access_alert_detail', 'Accès détail alerte'),
        ('access_threshold_config', 'Accès configuration seuils'),
        
        # GraphQL actions
        ('graphql_query', 'Requête GraphQL'),
        ('graphql_mutation', 'Mutation GraphQL'),
        ('graphql_generate_suggestion', 'Génération suggestion IA'),
        ('graphql_update_alert', 'MAJ alerte via GraphQL'),
        ('graphql_create_intervention', 'Création intervention via GraphQL'),
        ('graphql_bulk_update_alerts', 'MAJ groupée alertes'),
        
        # Security
        ('unauthorized_access', 'Accès non autorisé'),
        ('login_attempt', 'Tentative de connexion'),
        ('logout', 'Déconnexion'),
        
        # AI / MCP
        ('ai_intervention_suggestion', 'Suggestion IA'),
        ('mcp_fallback', 'Fallback MCP'),
        
        # Health checks
        ('health_check', 'Health check'),
    ]
    
    # Résultats
    RESULT_CHOICES = [
        ('success', '✅ Succès'),
        ('error', '❌ Erreur'),
        ('blocked', '🚫 Bloqué'),
        ('fallback', '⚠️ Fallback'),
        ('warning', '⚠️ Attention'),
    ]
    
    # Informations principales - Correction: utiliser settings.AUTH_USER_MODEL
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, db_index=True)
    reason = models.TextField(blank=True)
    
    # Traçabilité
    case_id = models.CharField(max_length=100, blank=True, db_index=True)
    trace_id = models.CharField(max_length=100, blank=True)
    
    # Informations techniques
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    
    # Données additionnelles (JSON)
    extra_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Log d'audit"
        verbose_name_plural = "Logs d'audit"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['action', 'result']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else 'ANONYMOUS'
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {user_str} - {self.get_action_display()} - {self.get_result_display()}"
    
    @classmethod
    def get_stats(cls, days=7):
        """Obtenir des statistiques d'audit"""
        from django.utils import timezone
        from django.db.models import Count
        
        since = timezone.now() - timezone.timedelta(days=days)
        
        return {
            'total': cls.objects.filter(created_at__gte=since).count(),
            'by_action': dict(cls.objects.filter(created_at__gte=since).values_list('action').annotate(count=Count('id'))),
            'by_result': dict(cls.objects.filter(created_at__gte=since).values_list('result').annotate(count=Count('id'))),
            'errors': cls.objects.filter(result='error', created_at__gte=since).count(),
            'blocked': cls.objects.filter(result='blocked', created_at__gte=since).count(),
        }