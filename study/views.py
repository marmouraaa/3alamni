# study/views.py - Version complète et corrigée

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import StudySession, Badge, StudentBadge
import json


@login_required
def study_start(request):
    return render(request, 'study/start.html')


@login_required
def api_start_session(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            duration = data.get('duration', 1800)
            
            session = StudySession.objects.create(
                student=request.user,
                started_at=timezone.now(),
                duration=duration,
                is_complete=False
            )
            
            request.session['study_session_id'] = session.id
            return JsonResponse({'success': True, 'session_id': session.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def api_complete_session(request):
    if request.method == 'POST':
        session_id = request.session.get('study_session_id')
        if session_id:
            try:
                session = StudySession.objects.get(id=session_id, student=request.user)
                session.ended_at = timezone.now()
                session.is_complete = True
                
                # Calculer la durée réelle en secondes
                duration_seconds = int((session.ended_at - session.started_at).total_seconds())
                session.duration = duration_seconds
                session.save()
                
                # Vérifier et attribuer les badges
                badges_earned = check_and_award_badges(request.user)
                
                # Calculer les points gagnés (1 point par minute)
                points_earned = max(1, duration_seconds // 60)
                
                # Mettre à jour le profil étudiant
                try:
                    profile = request.user.student_profile
                    profile.total_study_hours = (profile.total_study_hours or 0) + (points_earned // 60)
                    profile.total_quiz_points = (profile.total_quiz_points or 0) + points_earned
                    profile.save()
                except:
                    pass
                
                # Nettoyer la session
                del request.session['study_session_id']
                
                return JsonResponse({
                    'success': True,
                    'badge': badges_earned[0] if badges_earned else None,
                    'badges_earned': badges_earned,
                    'duration': session.duration,
                    'points_earned': points_earned,
                    'total_minutes': get_total_study_minutes(request.user)
                })
            except StudySession.DoesNotExist:
                pass
        
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def get_total_study_minutes(user):
    sessions = StudySession.objects.filter(student=user, is_complete=True)
    total_seconds = sum([s.duration for s in sessions])
    return total_seconds // 60


def check_and_award_badges(user):
    """Vérifie et attribue les badges à l'utilisateur"""
    
    # Compter les sessions complétées
    completed_sessions = StudySession.objects.filter(student=user, is_complete=True).count()
    
    # Calculer le temps total d'étude (en minutes)
    total_study_seconds = sum([
        session.duration for session in StudySession.objects.filter(student=user, is_complete=True)
    ])
    total_study_minutes = total_study_seconds // 60
    
    earned_badges = []
    
    # Badge "Premier Pas" - 1ère session
    if completed_sessions >= 1:
        badge, _ = Badge.objects.get_or_create(
            name='🌟 Premier Pas',
            defaults={
                'description': 'Première session d\'étude complétée',
                'icon': '🌟',
                'condition_type': 'study_count',
                'condition_value': 1
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=user,
            badge=badge
        )
        if created:
            earned_badges.append({
                'name': badge.name, 
                'icon': badge.icon, 
                'description': badge.description
            })
    
    # Badge "Apprenti Assidu" - 5 sessions
    if completed_sessions >= 5:
        badge, _ = Badge.objects.get_or_create(
            name='📚 Apprenti Assidu',
            defaults={
                'description': '5 sessions d\'étude complétées',
                'icon': '📚',
                'condition_type': 'study_count',
                'condition_value': 5
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=user,
            badge=badge
        )
        if created:
            earned_badges.append({
                'name': badge.name, 
                'icon': badge.icon, 
                'description': badge.description
            })
    
    # Badge "Maître du Temps" - 1 heure d'étude
    if total_study_minutes >= 60:
        badge, _ = Badge.objects.get_or_create(
            name='⏰ Maître du Temps',
            defaults={
                'description': '1 heure d\'étude accumulée',
                'icon': '⏰',
                'condition_type': 'study_time',
                'condition_value': 60
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=user,
            badge=badge
        )
        if created:
            earned_badges.append({
                'name': badge.name, 
                'icon': badge.icon, 
                'description': badge.description
            })
    
    return earned_badges


@login_required
def check_user_badges(request):
    """Vue pour vérifier les badges d'un utilisateur (debug)"""
    from .models import StudentBadge
    
    badges = StudentBadge.objects.filter(student=request.user).select_related('badge')
    
    result = {
        'username': request.user.username,
        'badges_count': badges.count(),
        'badges': [{'name': sb.badge.name, 'icon': sb.badge.icon, 'earned_at': sb.earned_at.strftime('%Y-%m-%d %H:%M')} for sb in badges]
    }
    
    return JsonResponse(result)