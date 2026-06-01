# health/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q

from .models import HealthRequest, Message, HealthTimelineEvent, AuditLog
from .services import HealthService


@login_required
def new_request(request):
    """Formulaire de nouvelle demande santé mentale"""
    if request.method == 'POST':
        category = request.POST.get('category')
        message_text = request.POST.get('message', '').strip()
        
        if not message_text:
            messages.error(request, "Veuillez écrire votre message.")
            return redirect('health:new_request')
        
        if not category:
            category = 'other'
        
        # Déterminer la tranche d'âge
        age_group = "16-18"  # défaut
        if hasattr(request.user, 'student_profile'):
            level = request.user.student_profile.level
            if level == 'primary':
                age_group = '10-12'
            elif level == 'middle':
                age_group = '13-15'
            elif level == 'high':
                age_group = '16-18'
            else:
                age_group = '18+'
        
        service = HealthService()
        health_request = service.create_request(
            student=request.user,
            message=message_text,
            category=category,
            age_group=age_group
        )
        
        messages.success(request, "✓ Votre message a été envoyé. Un conseiller vous répondra bientôt.")
        return redirect('health:chat', request_id=health_request.id)
    
    return render(request, 'health/new_request.html')


@login_required
def chat_view(request, request_id):
    """Interface de chat"""
    health_request = get_object_or_404(HealthRequest, id=request_id)
    
    # Vérifier accès
    if request.user.role == 'student' and health_request.student != request.user:
        messages.error(request, "Accès non autorisé.")
        return redirect('iphone_home')
    
    # Conseiller prend en charge si en attente
    if request.user.role in ['counselor', 'admin'] and health_request.status == 'pending':
        service = HealthService()
        service.assign_counselor(request_id, request.user)
        health_request.refresh_from_db()
    
    # Récupérer les messages (limités aux 100 derniers pour performance)
    messages_list = health_request.messages.all()[:100]
    timeline = health_request.timeline_events.all()[:50]
    
    # === INJECTION DE PANNE: tentative de voir identité réelle ===
    if 'debug_show_identity' in request.GET and request.user.role in ['counselor', 'admin']:
        service = HealthService()
        service.log_security_violation(
            user=request.user,
            request_id=request_id,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        messages.warning(request, "🔒 Information non disponible - l'anonymat de l'étudiant est garanti par la plateforme.")
    
    # Obtenir l'affichage de l'urgence
    urgency_display = dict(HealthRequest.URGENCY_CHOICES).get(health_request.urgency_level, 'Faible')
    
    return render(request, 'health/chat.html', {
        'request_id': health_request.id,
        'anonymous_id': health_request.anonymous_id,
        'messages_list': messages_list,
        'timeline': timeline,
        'request_status': health_request.status,
        'is_counselor': request.user.role in ['counselor', 'admin'],
        'ai_category': health_request.get_effective_category(),
        'ai_confidence': health_request.get_effective_confidence(),
        'ai_explanation': health_request.ai_explanation,
        'urgency_level': urgency_display,
    })


@login_required
def counselor_dashboard(request):
    """Dashboard conseiller"""
    if request.user.role not in ['counselor', 'admin']:
        messages.error(request, "Accès réservé aux conseillers.")
        return redirect('iphone_home')
    
    pending_count = HealthRequest.objects.filter(status='pending').count()
    in_progress_count = HealthRequest.objects.filter(status='in_progress').count()
    closed_count = HealthRequest.objects.filter(status='closed').count()
    
    # Statistiques par catégorie (catégorie effective = override ou IA)
    category_stats = []
    for cat_code, cat_label in HealthRequest.CATEGORY_CHOICES:
        # Compter en utilisant la catégorie effective (override si existant)
        count = HealthRequest.objects.filter(
            Q(overridden_category=cat_code) | 
            Q(overridden_category__isnull=True, ai_category=cat_code)
        ).count()
        if count > 0:
            category_stats.append({
                'ai_category': cat_code,
                'count': count
            })
    
    return render(request, 'health/counselor_dashboard.html', {
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'closed_count': closed_count,
        'category_stats': category_stats,
    })


@login_required
def requests_list(request):
    """Liste des demandes pour conseiller"""
    if request.user.role not in ['counselor', 'admin']:
        messages.error(request, "Accès réservé aux conseillers.")
        return redirect('iphone_home')
    
    status_filter = request.GET.get('status', 'pending')
    
    if status_filter == 'pending':
        requests_qs = HealthRequest.objects.filter(status='pending')
    elif status_filter == 'in_progress':
        requests_qs = HealthRequest.objects.filter(status='in_progress')
    elif status_filter == 'closed':
        requests_qs = HealthRequest.objects.filter(status='closed')
    else:
        requests_qs = HealthRequest.objects.all()
    
    # Optimisation: prefetch messages pour éviter N+1 queries
    requests_qs = requests_qs.prefetch_related('messages').order_by('-created_at')
    
    paginator = Paginator(requests_qs, 20)
    page_number = request.GET.get('page', 1)
    requests_page = paginator.get_page(page_number)
    
    return render(request, 'health/requests.html', {
        'requests': requests_page,
        'current_filter': status_filter,
    })


@login_required
def timeline_view(request, request_id):
    """Timeline détaillée d'une demande"""
    health_request = get_object_or_404(HealthRequest, id=request_id)
    
    # Vérifier accès
    if request.user.role == 'student' and health_request.student != request.user:
        messages.error(request, "Accès non autorisé.")
        return redirect('iphone_home')
    
    if request.user.role not in ['student', 'counselor', 'admin']:
        messages.error(request, "Accès non autorisé.")
        return redirect('iphone_home')
    
    timeline = health_request.timeline_events.all()
    
    return render(request, 'health/timeline.html', {
        'request': health_request,
        'timeline': timeline,
    })


@login_required
@require_http_methods(['POST'])
def override_category(request, request_id):
    """API pour override la catégorie (Human in the loop)"""
    if request.user.role not in ['counselor', 'admin']:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    category = request.POST.get('category')
    if not category or category not in dict(HealthRequest.CATEGORY_CHOICES):
        return JsonResponse({'success': False, 'error': 'Catégorie invalide'}, status=400)
    
    service = HealthService()
    try:
        health_request = service.override_category(request_id, request.user, category)
        return JsonResponse({
            'success': True,
            'new_category': health_request.get_effective_category_display()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def close_request(request, request_id):
    """API pour clôturer une demande"""
    if request.user.role not in ['counselor', 'admin']:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    summary = request.POST.get('summary', '')
    
    service = HealthService()
    try:
        health_request = service.close_request(request_id, request.user, summary)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def security_audit_log(request):
    """Page d'audit de sécurité (admin uniquement)"""
    if request.user.role != 'admin':
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('iphone_home')
    
    logs = AuditLog.objects.all().order_by('-created_at')[:200]
    
    return render(request, 'health/audit_log.html', {'logs': logs})