# audit/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user_display', 'action_display', 'result_colored', 'case_id', 'ip_address']
    list_filter = ['action', 'result', 'created_at']
    search_fields = ['user__username', 'reason', 'case_id', 'trace_id', 'ip_address']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Action', {
            'fields': ('user', 'action', 'result', 'reason')
        }),
        ('Traçabilité', {
            'fields': ('case_id', 'trace_id')
        }),
        ('Technique', {
            'fields': ('ip_address', 'user_agent', 'request_path', 'request_method'),
            'classes': ('collapse',)
        }),
        ('Données supplémentaires', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Date', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.user:
            return format_html('<strong>{}</strong> ({})', obj.user.username, obj.user.role if hasattr(obj.user, 'role') else 'no role')
        return 'ANONYMOUS'
    user_display.short_description = 'Utilisateur'
    
    def action_display(self, obj):
        return obj.get_action_display()
    action_display.short_description = 'Action'
    
    def result_colored(self, obj):
        colors = {
            'success': 'green',
            'error': 'red',
            'blocked': 'orange',
            'fallback': 'orange',
            'warning': 'orange',
        }
        color = colors.get(obj.result, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_result_display())
    result_colored.short_description = 'Résultat'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False