# audit/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Count
from .models import AuditLog


@staff_member_required
def audit_logs(request):
    """Vue pour visualiser les logs d'audit"""
    logs = AuditLog.objects.select_related('user').all()
    
    # Filtres
    action_filter = request.GET.get('action', '')
    result_filter = request.GET.get('result', '')
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    if result_filter:
        logs = logs.filter(result=result_filter)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)
    
    # Stats
    stats = {
        'total': AuditLog.objects.count(),
        'by_action': dict(AuditLog.objects.values_list('action').annotate(count=Count('id'))),
        'by_result': dict(AuditLog.objects.values_list('result').annotate(count=Count('id'))),
    }
    
    context = {
        'logs': logs_page,
        'stats': stats,
        'action_filter': action_filter,
        'result_filter': result_filter,
        'actions': AuditLog.ACTION_CHOICES,
        'results': AuditLog.RESULT_CHOICES,
    }
    return render(request, 'audit/logs.html', context)


@staff_member_required
def audit_stats(request):
    """Vue pour les statistiques d'audit"""
    from django.utils import timezone
    from datetime import timedelta
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    logs = AuditLog.objects.filter(created_at__gte=start_date)
    
    stats = {
        'total': logs.count(),
        'errors': logs.filter(result='error').count(),
        'blocked': logs.filter(result='blocked').count(),
        'success': logs.filter(result='success').count(),
        'by_day': [],
        'by_action': dict(logs.values_list('action').annotate(count=Count('id'))),
    }
    
    # Par jour
    for i in range(30):
        day = start_date + timedelta(days=i)
        day_logs = logs.filter(created_at__date=day.date())
        stats['by_day'].append({
            'date': day.strftime('%d/%m'),
            'count': day_logs.count(),
            'errors': day_logs.filter(result='error').count(),
        })
    
    return render(request, 'audit/stats.html', {'stats': stats})