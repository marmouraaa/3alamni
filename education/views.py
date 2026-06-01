from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q, Avg
import json
from django.core.exceptions import PermissionDenied

from .services_trivia import OpenTriviaService, TriviaQuizManager, QuizScoreService, BadgeService
from .models import Quiz, QuizAttempt, Subject


def role_required(*allowed_roles):
    """Décorateur pour vérifier les rôles"""
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'role') or request.user.role not in allowed_roles:
                raise PermissionDenied("Vous n'avez pas les permissions nécessaires.")
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


# ==================== VUES PROFESSEUR ====================

@login_required
@role_required('teacher')
def create_trivia_quiz(request):
    """Créer un quiz depuis OpenTrivia"""
    config = TriviaQuizManager.get_available_configurations()
    subjects = Subject.objects.filter(is_active=True)
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        amount = int(request.POST.get('amount', 10))
        category = request.POST.get('category')
        difficulty = request.POST.get('difficulty')
        question_type = request.POST.get('question_type')
        title = request.POST.get('title', '')
        
        if amount < 1 or amount > 50:
            messages.error(request, "Le nombre de questions doit être entre 1 et 50")
            return redirect('create_trivia_quiz')
        
        if not subject_id:
            messages.error(request, "Veuillez sélectionner une matière")
            return redirect('create_trivia_quiz')
        
        category_int = int(category) if category and category != '0' else None
        difficulty_val = difficulty if difficulty and difficulty != 'None' else None
        type_val = question_type if question_type and question_type != 'None' else None
        
        quizzes, error = TriviaQuizManager.create_quiz_from_trivia(
            teacher=request.user,
            subject_id=int(subject_id),
            amount=amount,
            category=category_int,
            difficulty=difficulty_val,
            question_type=type_val,
            title=title
        )
        
        if quizzes:
            messages.success(request, f"✅ {len(quizzes)} questions ajoutées avec succès!")
            return redirect('quiz_list')
        else:
            messages.error(request, f"❌ Erreur: {error}")
    
    context = {
        'subjects': subjects,
        'categories': config.get('categories', []),
        'difficulties': config.get('difficulties', []),
        'types': config.get('types', []),
        'max_questions': config.get('max_questions', 50),
        'min_questions': config.get('min_questions', 1),
    }
    return render(request, 'education/create_trivia_quiz.html', context)


@login_required
def quiz_list(request):
    """Liste des quiz"""
    quizzes = Quiz.objects.filter(status='published').select_related('subject', 'teacher')
    subjects = Subject.objects.filter(is_active=True)
    
    return render(request, 'education/quiz_list.html', {
        'quizzes': quizzes,
        'subjects': subjects,
    })


# ==================== API SOUMISSION RÉPONSES ====================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def submit_quiz_answer_api(request, quiz_id):
    """API pour soumettre une réponse"""
    try:
        quiz = Quiz.objects.get(id=quiz_id, status='published')
    except Quiz.DoesNotExist:
        return JsonResponse({'error': 'Quiz non trouvé'}, status=404)
    
    try:
        data = json.loads(request.body)
        answer = data.get('answer')
        time_taken = data.get('time_taken', 0)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    if not answer:
        return JsonResponse({'error': 'Réponse manquante'}, status=400)
    
    # Vérifier si déjà répondu
    existing = QuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    if existing:
        return JsonResponse({
            'success': False,
            'already_answered': True,
            'was_correct': existing.is_correct,
            'correct_answer': quiz.correct_answer,  # ← AJOUTÉ
        })
    
    # Vérifier la réponse (comparaison insensible à la casse)
    is_correct = answer.strip().lower() == quiz.correct_answer.strip().lower()
    
    # Créer la tentative
    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        answer=answer,
        is_correct=is_correct,
        time_taken=time_taken,
        score=100 if is_correct else 0
    )
    
    # Mettre à jour les stats du quiz
    quiz.times_played += 1
    total_correct = QuizAttempt.objects.filter(quiz=quiz, is_correct=True).count()
    quiz.success_rate = (total_correct / quiz.times_played) * 100 if quiz.times_played > 0 else 0
    quiz.save()
    
    # Mettre à jour les stats étudiant
    try:
        profile = request.user.student_profile
    except:
        from accounts.models import StudentProfile
        profile = StudentProfile.objects.create(user=request.user)
    
    profile.total_quizzes_completed += 1
    if is_correct:
        profile.total_correct_answers += 1
    profile.total_quiz_points += (100 if is_correct else 0)
    
    if is_correct:
        profile.current_streak += 1
        if profile.current_streak > profile.best_streak:
            profile.best_streak = profile.current_streak
    else:
        profile.current_streak = 0
    profile.save()
    
    # Retourner la réponse AVEC correct_answer
    return JsonResponse({
        'success': True,
        'is_correct': is_correct,
        'correct_answer': quiz.correct_answer if not is_correct else None,  # ← CORRIGÉ
        'explanation': quiz.explanation if not is_correct else None,
        'points_earned': 100 if is_correct else 0,
        'streak': profile.current_streak,
        'early_warning': False,
        'badges_earned': []
    })
# ==================== STATISTIQUES ÉTUDIANT ====================

@login_required
def get_my_stats_api(request):
    """API pour les stats étudiant"""
    try:
        profile = request.user.student_profile
    except:
        return JsonResponse({'success': False, 'error': 'Profil non trouvé'}, status=404)
    
    recent_attempts = QuizAttempt.objects.filter(
        student=request.user
    ).select_related('quiz', 'quiz__subject').order_by('-created_at')[:10]
    
    subject_stats = QuizAttempt.objects.filter(
        student=request.user
    ).values('quiz__subject__name').annotate(
        total=Count('id'),
        correct=Count('id', filter=Q(is_correct=True)),
    )
    
    return JsonResponse({
        'success': True,
        'stats': {
            'total_points': profile.total_quiz_points,
            'total_quizzes': profile.total_quizzes_completed,
            'total_correct': profile.total_correct_answers,
            'success_rate': round((profile.total_correct_answers / profile.total_quizzes_completed * 100), 1) if profile.total_quizzes_completed > 0 else 0,
            'current_streak': profile.current_streak,
            'best_streak': profile.best_streak,
        },
        'subject_stats': [
            {'subject': s['quiz__subject__name'], 'total': s['total'], 'correct': s['correct']}
            for s in subject_stats
        ],
        'recent_attempts': [
            {
                'quiz_title': a.quiz.title,
                'is_correct': a.is_correct,
                'score': a.score,
                'date': a.created_at.strftime('%d/%m/%Y'),
            }
            for a in recent_attempts
        ]
    })

@login_required
def quiz_detail(request, quiz_id):
    """Détail d'un quiz et soumission de réponse"""
    from .models import Quiz, QuizAttempt
    
    quiz = get_object_or_404(Quiz, id=quiz_id, status='published')
    
    # Vérifier si l'utilisateur a déjà tenté ce quiz
    existing_attempt = QuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    
    if request.method == 'POST':
        answer = request.POST.get('answer')
        time_taken = int(request.POST.get('time_taken', 0))
        
        is_correct = (answer == quiz.correct_answer)
        
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            answer=answer,
            is_correct=is_correct,
            time_taken=time_taken,
            score=100 if is_correct else 0
        )
        
        # Mettre à jour les stats du quiz
        quiz.times_played += 1
        total_correct = QuizAttempt.objects.filter(quiz=quiz, is_correct=True).count()
        quiz.success_rate = (total_correct / quiz.times_played) * 100 if quiz.times_played > 0 else 0
        quiz.save()
        
        messages.success(request, "Réponse enregistrée!")
        return redirect('quiz_detail', quiz_id=quiz_id)
    
    # Récupérer la dernière tentative
    last_attempt = QuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    
    return render(request, 'education/quiz_detail.html', {
        'quiz': quiz,
        'last_attempt': last_attempt,
        'existing_attempt': existing_attempt,
    })
# ==================== VUES RÉSEAUX SOCIAUX ====================

@login_required
def tiktok_feed(request):
    quizzes = Quiz.objects.filter(status='published').order_by('-created_at')
    return render(request, 'tiktok/feed.html', {'quizzes': quizzes})

@login_required
def instagram_feed(request):
    quizzes = Quiz.objects.filter(status='published').order_by('-created_at')
    return render(request, 'instagram/feed.html', {'quizzes': quizzes})

@login_required
def snapchat_feed(request):
    quizzes = Quiz.objects.filter(status='published').order_by('-created_at')
    return render(request, 'snapchat/feed.html', {'quizzes': quizzes})
@login_required
def facebook_feed(request):
    quizzes = Quiz.objects.filter(status='published').order_by('-created_at')
    return render(request, 'facebook/feed.html', {'quizzes': quizzes})