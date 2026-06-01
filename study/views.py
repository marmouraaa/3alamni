# study/views.py - Version corrigée

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import StudySession, Badge, StudentBadge
from accounts.models import StudentProfile
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
            
            student = StudentProfile.objects.get(user=request.user)
            session = StudySession.objects.create(
                student=student,
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
                session = StudySession.objects.get(id=session_id)
                session.ended_at = timezone.now()
                session.is_complete = True
                
                # Calculer la durée réelle en secondes
                duration_seconds = (session.ended_at - session.started_at).total_seconds()
                session.duration = int(duration_seconds)
                session.save()
                
                # Vérifier et attribuer les badges
                badges_earned = check_and_award_badges(session.student)
                
                # Nettoyer la session
                del request.session['study_session_id']
                
                return JsonResponse({
                    'success': True,
                    'badge': badges_earned[0] if badges_earned else None,
                    'duration': session.duration
                })
            except StudySession.DoesNotExist:
                pass
        
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

def check_and_award_badges(student):
    # Compter les sessions complétées
    completed_sessions = StudySession.objects.filter(
        student=student,
        is_complete=True
    ).count()
    
    # Calculer le temps total d'étude (en minutes)
    total_study_time = sum([
        session.duration for session in StudySession.objects.filter(
            student=student, 
            is_complete=True
        )
    ]) // 60  # Convertir en minutes
    
    earned_badges = []
    
    # Badge "Premier Pas" - 1ère session
    if completed_sessions == 1:
        badge, _ = Badge.objects.get_or_create(
            name='Premier Pas',
            defaults={
                'description': 'Première session d\'étude complétée',
                'icon': '🌟',
                'condition_type': 'study_count',
                'condition_value': 1
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=student,
            badge=badge
        )
        if created:
            earned_badges.append({'name': badge.name, 'icon': badge.icon, 'description': badge.description})
    
    # Badge "Apprenti Assidu" - 5 sessions
    if completed_sessions >= 5:
        badge, _ = Badge.objects.get_or_create(
            name='Apprenti Assidu',
            defaults={
                'description': '5 sessions d\'étude complétées',
                'icon': '📚',
                'condition_type': 'study_count',
                'condition_value': 5
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=student,
            badge=badge
        )
        if created:
            earned_badges.append({'name': badge.name, 'icon': badge.icon, 'description': badge.description})
    
    # Badge "1 Heure d'Étude"
    if total_study_time >= 60:
        badge, _ = Badge.objects.get_or_create(
            name='Maître du Temps',
            defaults={
                'description': '1 heure d\'étude accumulée',
                'icon': '⏰',
                'condition_type': 'study_time',
                'condition_value': 60
            }
        )
        student_badge, created = StudentBadge.objects.get_or_create(
            student=student,
            badge=badge
        )
        if created:
            earned_badges.append({'name': badge.name, 'icon': badge.icon, 'description': badge.description})
    
    return earned_badges