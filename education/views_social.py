# education/views_social.py
# Vues pour les actions des réseaux sociaux (like, submit, share, comment)

import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Quiz, QuizAttempt
from accounts.models import StudentProfile


def _submit_answer(request, quiz_id):
    """Logique commune de soumission de réponse pour tous les réseaux sociaux."""
    try:
        quiz = Quiz.objects.get(id=quiz_id, status='published')
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz non trouvé'}, status=404)

    try:
        data = json.loads(request.body)
        answer = data.get('answer', '').strip()
        time_taken = data.get('time_taken', 0)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    if not answer:
        return JsonResponse({'error': 'Réponse manquante'}, status=400)

    # Déjà répondu ?
    existing = QuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    if existing:
        return JsonResponse({
            'success': False,
            'already_answered': True,
            'was_correct': existing.is_correct,
            'correct_answer': quiz.correct_answer,
        })

    is_correct = answer.lower() == quiz.correct_answer.strip().lower()

    QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        answer=answer,
        is_correct=is_correct,
        time_taken=time_taken,
        score=100 if is_correct else 0
    )

    # Mettre à jour stats quiz
    quiz.times_played += 1
    total_correct = QuizAttempt.objects.filter(quiz=quiz, is_correct=True).count()
    quiz.success_rate = (total_correct / quiz.times_played) * 100
    quiz.save()

    # Mettre à jour profil étudiant
    try:
        profile = request.user.student_profile
    except Exception:
        profile = StudentProfile.objects.create(user=request.user)

    profile.total_quizzes_completed += 1
    if is_correct:
        profile.total_correct_answers = (profile.total_correct_answers or 0) + 1
        profile.current_streak = (profile.current_streak or 0) + 1
        if profile.current_streak > (profile.best_streak or 0):
            profile.best_streak = profile.current_streak
    else:
        profile.current_streak = 0
    profile.total_quiz_points = (profile.total_quiz_points or 0) + (100 if is_correct else 0)
    profile.save()

    # Vérifier si alerte Early Warning à déclencher
    early_warning = False
    total = profile.total_quizzes_completed
    if total >= 5:
        correct = profile.total_correct_answers or 0
        rate = (correct / total) * 100
        if rate < 40:
            early_warning = True

    return JsonResponse({
        'success': True,
        'is_correct': is_correct,
        'correct_answer': quiz.correct_answer if not is_correct else None,
        'explanation': quiz.explanation if not is_correct else None,
        'points_earned': 100 if is_correct else 0,
        'streak': profile.current_streak,
        'early_warning': early_warning,
    })


def _like_quiz(request, quiz_id):
    """Logique commune de like pour tous les réseaux sociaux."""
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        quiz.likes += 1
        quiz.save(update_fields=['likes'])
        return JsonResponse({'success': True, 'likes': quiz.likes})
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz non trouvé'}, status=404)


def _share_quiz(request, quiz_id):
    """Logique commune de partage."""
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        quiz.shares += 1
        quiz.save(update_fields=['shares'])
        return JsonResponse({'success': True, 'shares': quiz.shares})
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz non trouvé'}, status=404)


def _comment_quiz(request, quiz_id):
    """Compteur de commentaires (sans modèle dédié pour l'instant)."""
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        quiz.comments_count += 1
        quiz.save(update_fields=['comments_count'])
        return JsonResponse({'success': True})
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz non trouvé'}, status=404)


# ─── TikTok ───────────────────────────────────────────────────────────────────

@login_required
@csrf_exempt
@require_http_methods(['POST'])
def tiktok_submit_answer(request, quiz_id):
    return _submit_answer(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def tiktok_like(request, quiz_id):
    return _like_quiz(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def tiktok_share(request, quiz_id):
    return _share_quiz(request, quiz_id)


# ─── Instagram ────────────────────────────────────────────────────────────────

@login_required
@csrf_exempt
@require_http_methods(['POST'])
def instagram_submit_answer(request, quiz_id):
    return _submit_answer(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def instagram_like(request, quiz_id):
    return _like_quiz(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def instagram_share(request, quiz_id):
    return _share_quiz(request, quiz_id)


# ─── Snapchat ─────────────────────────────────────────────────────────────────

@login_required
@csrf_exempt
@require_http_methods(['POST'])
def snapchat_submit_answer(request, quiz_id):
    return _submit_answer(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def snapchat_like(request, quiz_id):
    return _like_quiz(request, quiz_id)


# ─── Facebook ─────────────────────────────────────────────────────────────────

@login_required
@csrf_exempt
@require_http_methods(['POST'])
def facebook_submit_answer(request, quiz_id):
    return _submit_answer(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def facebook_like(request, quiz_id):
    return _like_quiz(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def facebook_share(request, quiz_id):
    return _share_quiz(request, quiz_id)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def facebook_comment(request, quiz_id):
    return _comment_quiz(request, quiz_id)
