# health/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import HealthRequest, Message, ChatSession, HealthTimelineEvent, AuditLog


@admin.register(HealthRequest)
class HealthRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'anonymous_id', 'get_effective_category_display', 'status', 'urgency_level', 'created_at')
    list_filter = ('status', 'urgency_level', 'ai_category', 'overridden_category', 'created_at')
    search_fields = ('anonymous_id', 'ai_explanation', 'closure_summary')
    readonly_fields = ('id', 'created_at', 'updated_at', 'closed_at', 'ai_trace_id')
    
    fieldsets = (
        ('Information générale', {
            'fields': ('id', 'student', 'anonymous_id', 'status', 'urgency_level')
        }),
        ('Catégorisation IA (Track E)', {
            'fields': ('ai_category', 'ai_confidence', 'ai_explanation', 'ai_trace_id'),
            'classes': ('collapse',)
        }),
        ('Override Humain (Human in the Loop)', {
            'fields': ('overridden_category', 'overridden_by', 'overridden_at'),
            'classes': ('collapse',)
        }),
        ('Gestion', {
            'fields': ('counselor', 'closed_at', 'closure_summary')
        }),
        ('Métadonnées', {
            'fields': ('student_age_group', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_effective_category_display(self, obj):
        category = obj.get_effective_category()
        colors = {
            'stress': '#FF9800',
            'anxiety': '#F44336',
            'family': '#9C27B0',
            'school': '#2196F3',
            'other': '#757575'
        }
        color = colors.get(category, '#757575')
        display = obj.get_effective_category_display()
        
        if obj.overridden_category:
            return format_html('<span style="background:{}; color:white; padding:2px 8px; border-radius:12px;">✏️ {}</span>', color, display)
        return format_html('<span style="background:{}; color:white; padding:2px 8px; border-radius:12px;">🤖 {}</span>', color, display)
    
    get_effective_category_display.short_description = 'Catégorie effective'
    
    actions = ['mark_as_in_progress', 'mark_as_closed']
    
    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} demande(s) marquée(s) "En cours".')
    mark_as_in_progress.short_description = 'Marquer comme "En cours"'
    
    def mark_as_closed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='closed', closed_at=timezone.now())
        self.message_user(request, f'{updated} demande(s) clôturée(s).')
    mark_as_closed.short_description = 'Marquer comme "Clôturée"'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'health_request', 'sender', 'sender_role', 'short_content', 'created_at')
    list_filter = ('sender_role', 'created_at', 'is_read')
    search_fields = ('sender', 'content')
    readonly_fields = ('id', 'created_at')
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Contenu'


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('health_request', 'is_active', 'last_activity')
    list_filter = ('is_active', 'last_activity')
    readonly_fields = ('counselor_channel', 'student_channel')


@admin.register(HealthTimelineEvent)
class HealthTimelineEventAdmin(admin.ModelAdmin):
    list_display = ('health_request', 'event_type', 'actor', 'short_action', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('actor', 'action', 'detail')
    readonly_fields = ('created_at',)
    
    def short_action(self, obj):
        return obj.action[:60] + '...' if len(obj.action) > 60 else obj.action
    short_action.short_description = 'Action'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'resource', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'resource', 'ip_address')
    readonly_fields = ('created_at', 'details')
    
    def has_add_permission(self, request):
        return False  # Les logs sont en lecture seule
    
    def has_change_permission(self, request, obj=None):
        return False  # Les logs sont en lecture seule