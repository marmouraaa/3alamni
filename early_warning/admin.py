# early_warning/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import RiskScore, Alert, Intervention, ThresholdConfig, AISuggestion


@admin.register(ThresholdConfig)
class ThresholdConfigAdmin(admin.ModelAdmin):
    """Configuration des seuils"""
    list_display = ['id', 'high_risk_threshold', 'medium_risk_threshold', 'alert_threshold', 
                   'absence_weight', 'grade_weight', 'behavior_weight', 'updated_at']
    list_editable = ['high_risk_threshold', 'medium_risk_threshold', 'alert_threshold',
                    'absence_weight', 'grade_weight', 'behavior_weight']
    fieldsets = (
        ('Seuils d\'alerte', {
            'fields': ('high_risk_threshold', 'medium_risk_threshold', 'alert_threshold')
        }),
        ('Pondérations (doivent totaliser 100%)', {
            'fields': ('absence_weight', 'grade_weight', 'behavior_weight')
        }),
    )


@admin.register(RiskScore)
class RiskScoreAdmin(admin.ModelAdmin):
    """Scores de risque"""
    list_display = ['student_name', 'student_id', 'class_name', 'risk_score_display', 
                   'risk_level_colored', 'absences', 'avg_grade', 'behavior_score', 'created_at']
    list_filter = ['risk_level', 'class_name', 'created_at']
    search_fields = ['student_name', 'student_id', 'class_name']
    readonly_fields = ['risk_score', 'risk_level']
    
    fieldsets = (
        ('Informations étudiant', {
            'fields': ('student_name', 'student_id', 'class_name')
        }),
        ('Données d\'entrée', {
            'fields': ('absences', 'avg_grade', 'behavior_score')
        }),
        ('Résultats calculés (lecture seule)', {
            'fields': ('risk_score', 'risk_level')
        }),
    )
    
    def risk_score_display(self, obj):
        """Affiche le score avec une barre de progression"""
        color = 'red' if obj.risk_score >= 70 else 'orange' if obj.risk_score >= 40 else 'green'
        return format_html(
            '<div style="background: #eee; border-radius: 3px; width: 100px;">'
            '<div style="background: {}; width: {}%; border-radius: 3px; text-align: center; color: white;">'
            '{:.0f}</div></div>',
            color, obj.risk_score, obj.risk_score
        )
    risk_score_display.short_description = 'Score'
    
    def risk_level_colored(self, obj):
        """Affiche le niveau avec couleur"""
        colors = {
            'high': 'red',
            'medium': 'orange',
            'low': 'green'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.risk_level, 'black'),
            obj.get_risk_level_display()
        )
    risk_level_colored.short_description = 'Niveau'


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Alertes générées"""
    list_display = ['id', 'student_name', 'risk_level_display', 'risk_score_value', 
                   'status_colored', 'status', 'has_ai_suggestion', 'created_at']
    list_filter = ['status', 'risk_score__risk_level', 'created_at']
    search_fields = ['risk_score__student_name', 'risk_score__student_id']
    list_editable = ['status']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Étudiant concerné', {
            'fields': ('risk_score',)
        }),
        ('Alerte', {
            'fields': ('message', 'status')
        }),
        ('Suggestion IA', {
            'fields': ('ai_suggestion',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def student_name(self, obj):
        return obj.risk_score.student_name
    student_name.short_description = 'Étudiant'
    student_name.admin_order_field = 'risk_score__student_name'
    
    def risk_level_display(self, obj):
        level = obj.risk_score.risk_level
        colors = {
            'high': '🔴 Élevé',
            'medium': '🟠 Moyen',
            'low': '🟢 Faible'
        }
        return colors.get(level, level)
    risk_level_display.short_description = 'Niveau risque'
    risk_level_display.admin_order_field = 'risk_score__risk_level'
    
    def risk_score_value(self, obj):
        score = obj.risk_score.risk_score
        return f"{score:.1f}/100"
    risk_score_value.short_description = 'Score'
    risk_score_value.admin_order_field = 'risk_score__risk_score'
    
    def status_colored(self, obj):
        colors = {
            'pending': 'red',
            'in_progress': 'orange',
            'resolved': 'green',
            'ignored': 'gray'
        }
        status_display = dict(Alert.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            status_display
        )
    status_colored.short_description = 'Statut (coloré)'
    
    def has_ai_suggestion(self, obj):
        return '✅' if obj.ai_suggestion else '❌'
    has_ai_suggestion.short_description = 'IA'


@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    """Suggestions IA"""
    list_display = ['id', 'action_display', 'student_name', 'confidence_display', 
                   'fallback_badge', 'created_at']
    list_filter = ['suggested_action', 'fallback_used', 'created_at']
    search_fields = ['description', 'explanation_primary_factor']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Action suggérée', {
            'fields': ('suggested_action', 'description', 'confidence')
        }),
        ('Explication IA', {
            'fields': ('explanation_primary_factor', 'explanation_secondary_factor', 'explanation_basis')
        }),
        ('Traçabilité', {
            'fields': ('trace_id', 'fallback_used', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def action_display(self, obj):
        actions = {
            'quiz': '📝 Quiz',
            'meeting': '👥 Réunion',
            'followup': '📋 Suivi',
            'counseling': '🎓 Counseling'
        }
        return actions.get(obj.suggested_action, obj.suggested_action)
    action_display.short_description = 'Action'
    
    def student_name(self, obj):
        alert = obj.alerts.first()
        if alert:
            return alert.risk_score.student_name
        return 'Non assigné'
    student_name.short_description = 'Étudiant'
    
    def confidence_display(self, obj):
        percent = obj.confidence * 100
        color = 'green' if percent >= 80 else 'orange' if percent >= 70 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.0f}%</span>',
            color, percent
        )
    confidence_display.short_description = 'Confiance'
    
    def fallback_badge(self, obj):
        if obj.fallback_used:
            return format_html('<span style="color: orange;">⚠️ Fallback</span>')
        return format_html('<span style="color: green;">✅ IA</span>')
    fallback_badge.short_description = 'Mode'


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    """Interventions"""
    list_display = ['id', 'action_display', 'student_name', 'due_date_colored', 
                   'status_colored', 'status', 'created_at']
    list_filter = ['status', 'action_type', 'due_date']
    search_fields = ['description', 'alert__risk_score__student_name', 'notes']
    list_editable = ['status']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Intervention', {
            'fields': ('alert', 'action_type', 'description', 'due_date', 'status')
        }),
        ('Suggestion IA associée', {
            'fields': ('ai_suggestion',),
            'classes': ('collapse',)
        }),
        ('Suivi', {
            'fields': ('notes',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def action_display(self, obj):
        actions = {
            'quiz': '📝 Quiz',
            'meeting': '👥 Réunion',
            'followup': '📋 Suivi',
            'counseling': '🎓 Counseling',
            'custom': '⚙️ Personnalisé'
        }
        return actions.get(obj.action_type, obj.action_type)
    action_display.short_description = 'Action'
    
    def student_name(self, obj):
        return obj.alert.risk_score.student_name
    student_name.short_description = 'Étudiant'
    student_name.admin_order_field = 'alert__risk_score__student_name'
    
    def due_date_colored(self, obj):
        from django.utils import timezone
        if obj.due_date < timezone.now().date() and obj.status not in ['completed', 'cancelled']:
            return format_html('<span style="color: red; font-weight: bold;">{} ⚠️</span>', obj.due_date)
        return obj.due_date
    due_date_colored.short_description = 'Date limite'
    
    def status_colored(self, obj):
        colors = {
            'planned': 'blue',
            'in_progress': 'orange',
            'completed': 'green',
            'cancelled': 'gray'
        }
        status_display = dict(Intervention.STATUS_CHOICES).get(obj.status, obj.status)
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, 'black'),
            status_display
        )
    status_colored.short_description = 'Statut (coloré)'