from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q, Sum
from early_warning.models import Alert, RiskScore
from accounts.models import StudentProfile
from education.models import QuizAttempt, Badge, UserBadge
from study.models import StudySession  # ← Ajout pour Study With Me


@login_required
def iphone_home(request):
    return render(request, 'iphone/home.html')


@login_required
def dashboard_redirect(request):
    """Redirige vers le dashboard selon le rôle"""
    role = request.user.role
    if role == 'student':
        return redirect('dashboard:student')
    elif role == 'teacher':
        return redirect('dashboard:teacher')
    elif role == 'counselor':
        return redirect('dashboard:counselor')
    elif role == 'parent':
        return redirect('dashboard:parent')
    else:
        return redirect('iphone_home')


@login_required
def dashboard_student(request):
    """Dashboard étudiant avec toutes les statistiques (Quiz + Study)"""
    
    from education.models import QuizAttempt, UserBadge, Badge
    from django.db.models import Sum, Count, Q
    
    # ========== STATISTIQUES QUIZ ==========
    attempts = QuizAttempt.objects.filter(student=request.user)
    
    total_quizzes = attempts.count()
    total_correct = attempts.filter(is_correct=True).count()
    total_points = attempts.aggregate(Sum('score'))['score__sum'] or 0
    success_rate = round((total_correct / total_quizzes * 100), 1) if total_quizzes > 0 else 0
    
    # Badges obtenus
    user_badges = UserBadge.objects.filter(user=request.user).select_related('badge')
    badges_count = user_badges.count()
    all_badges = Badge.objects.all()
    
    # Statistiques par matière
    subject_stats = []
    raw_stats = attempts.values('quiz__subject__name').annotate(
        total=Count('id'),
        correct=Count('id', filter=Q(is_correct=True)),
        points=Sum('score')
    ).order_by('-total')
    
    for stat in raw_stats:
        subject_stats.append({
            'subject': stat['quiz__subject__name'] or "Sans matière",
            'total': stat['total'],
            'correct': stat['correct'],
            'points': stat['points'] or 0,
            'percentage': round((stat['correct'] / stat['total'] * 100), 1) if stat['total'] > 0 else 0
        })
    
    # Pourcentages pour les barres de progression
    total_quizzes_percent = min((total_quizzes / 100 * 100), 100)
    points_percent = min((total_points / 5000 * 100), 100)
    
    # ========== STATISTIQUES STUDY WITH ME ==========
    study_sessions = StudySession.objects.filter(student=request.user, is_complete=True)
    total_study_seconds = sum([s.duration for s in study_sessions])
    total_study_hours = total_study_seconds // 3600
    study_sessions_count = study_sessions.count()
    
    # Badges Study
    from study.models import StudentBadge as StudyStudentBadge
    study_badges = StudyStudentBadge.objects.filter(student=request.user).select_related('badge')
    study_badges_count = study_badges.count()
    
    # ========== PROFIL ÉTUDIANT ==========
    try:
        profile = request.user.student_profile
        # Fusionner les points des quiz et de l'étude
        profile.total_quiz_points = total_points
        profile.total_study_hours = total_study_hours
        profile.total_quizzes_completed = total_quizzes
        profile.total_correct_answers = total_correct
        profile.current_streak = profile.current_streak or 0
        profile.best_streak = profile.best_streak or 0
        profile.save()
        level = profile.get_level_display() if hasattr(profile, 'get_level_display') else "Débutant"
        current_streak = profile.current_streak or 0
        best_streak = profile.best_streak or 0
    except:
        level = "Débutant"
        current_streak = 0
        best_streak = 0
    
    streak_percent = min((current_streak / 30 * 100), 100)
    
    # Dernières activités (quiz)
    recent_attempts = attempts.select_related('quiz__subject').order_by('-created_at')[:10]
    
    # Dernières sessions d'étude
    recent_study_sessions = study_sessions.order_by('-ended_at')[:5]
    
    context = {
        # Cartes stats Quiz
        'total_points': total_points,
        'total_quizzes': total_quizzes,
        'total_correct': total_correct,
        'success_rate': success_rate,
        'current_streak': current_streak,
        'best_streak': best_streak,
        'badges_count': badges_count,
        'level': level,
        # Cartes stats Study
        'total_study_hours': total_study_hours,
        'study_sessions_count': study_sessions_count,
        'study_badges_count': study_badges_count,
        # Badges
        'user_badges': user_badges,
        'all_badges': all_badges,
        'study_badges': study_badges,
        # Progression
        'total_quizzes_percent': total_quizzes_percent,
        'points_percent': points_percent,
        'streak_percent': streak_percent,
        # Performance par matière
        'subject_stats': subject_stats,
        # Activités récentes
        'recent_attempts': recent_attempts,
        'recent_study_sessions': recent_study_sessions,
    }
    
    return render(request, 'dashboard/student.html', context)


@login_required
def dashboard_teacher(request):
    if request.user.role != 'teacher':
        return redirect('iphone_home')
    
    # Filtrer par professeur (via StudentProfile)
    teacher_students = StudentProfile.objects.filter(teacher=request.user)
    student_ids = teacher_students.values_list('user__id', flat=True)
    
    # Filtrer les RiskScore par ces étudiants
    risks = RiskScore.objects.filter(student_id__in=student_ids)
    
    # Alertes
    alerts = Alert.objects.filter(
        risk_score__student_id__in=student_ids,
        status='pending'
    ).select_related('risk_score')[:10]
    
    # Statistiques
    high_risk_count = risks.filter(risk_level='high').count()
    medium_risk = risks.filter(risk_level='medium').count()
    low_risk = risks.filter(risk_level='low').count()
    students_count = risks.count()
    intervention_count = alerts.count()
    
    # === DONNÉES POUR LES GRAPHIQUES ===
    has_data = students_count > 0
    
    risk_distribution_labels = ['Élevé', 'Moyen', 'Faible']
    risk_distribution_data = [high_risk_count, medium_risk, low_risk]
    
    # Score par classe
    class_stats = risks.values('class_name').annotate(avg_risk=Avg('risk_score')).order_by('class_name')
    class_avg_labels = [c['class_name'] for c in class_stats if c['class_name']]
    class_avg_data = [round(c['avg_risk'], 1) for c in class_stats if c['class_name']]
    
    # Histogramme
    risk_scores = list(risks.values_list('risk_score', flat=True))
    bins = [0, 20, 40, 60, 80, 100]
    histogram_data = [0] * (len(bins) - 1)
    for score in risk_scores:
        for i in range(len(bins) - 1):
            if bins[i] <= score < bins[i+1] or (i == len(bins)-2 and score == bins[i+1]):
                histogram_data[i] += 1
                break
    histogram_labels = ['0-20', '20-40', '40-60', '60-80', '80-100']
    
    # Top 10
    top10 = risks.order_by('-risk_score')[:10]
    top10_labels = [s.student_name for s in top10 if s.student_name]
    top10_data = [s.risk_score for s in top10 if s.student_name]
    
    # Scatter
    scatter_absences = [{'x': r.absences, 'y': r.risk_score} for r in risks.filter(absences__isnull=False) if r.absences]
    scatter_grades = [{'x': r.avg_grade, 'y': r.risk_score} for r in risks.filter(avg_grade__isnull=False) if r.avg_grade]
    
    # Par classe
    class_count = risks.values('class_name').annotate(count=Count('id'))
    class_count_labels = [c['class_name'] for c in class_count if c['class_name']]
    class_count_data = [c['count'] for c in class_count if c['class_name']]
    
    class_grades = risks.filter(avg_grade__isnull=False).values('class_name').annotate(avg_grade=Avg('avg_grade'))
    class_grades_labels = [c['class_name'] for c in class_grades if c['class_name']]
    class_grades_data = [round(c['avg_grade'], 1) for c in class_grades if c['class_name']]
    
    context = {
        'alerts': alerts,
        'high_risk_count': high_risk_count,
        'low_risk': low_risk,
        'medium_risk': medium_risk,
        'students_count': students_count,
        'total_students': students_count,
        'intervention_count': intervention_count,
        'has_data': has_data,
        'risk_distribution_labels': risk_distribution_labels,
        'risk_distribution_data': risk_distribution_data,
        'class_avg_labels': class_avg_labels,
        'class_avg_data': class_avg_data,
        'histogram_labels': histogram_labels,
        'histogram_data': histogram_data,
        'top10_labels': top10_labels,
        'top10_data': top10_data,
        'scatter_absences': scatter_absences,
        'scatter_grades': scatter_grades,
        'class_count_labels': class_count_labels,
        'class_count_data': class_count_data,
        'class_grades_labels': class_grades_labels,
        'class_grades_data': class_grades_data,
        'correlation_labels': ['Absences', 'Notes', 'Comportement'],
        'correlation_data': [0.6, -0.7, 0.4],
        'daily_labels': [],
        'daily_data': [],
        'recent_interventions': [],
    }
    return render(request, 'dashboard/teacher.html', context)


@login_required
def dashboard_counselor(request):
    return render(request, 'dashboard/counselor.html')
@login_required
def dashboard_parent(request):
    """Dashboard parent - affiche les données de l'enfant lié"""
    
    from education.models import QuizAttempt, UserBadge
    from study.models import StudySession
    from django.db.models import Sum, Count, Q
    from early_warning.models import Alert, RiskScore
    from accounts.models import StudentProfile
    from django.utils import timezone
    from datetime import timedelta
    
    # Récupérer l'enfant lié à ce parent (via le champ parent dans StudentProfile)
    child = None
    
    try:
        # Chercher un profil étudiant dont le parent = request.user
        student_profile = StudentProfile.objects.filter(parent=request.user).first()
        if student_profile:
            child = student_profile.user
            print(f"✅ Enfant trouvé: {child.username}")
    except Exception as e:
        print(f"Erreur: {e}")
    
    if child:
        # Statistiques Quiz
        attempts = QuizAttempt.objects.filter(student=child)
        total_quizzes = attempts.count()
        total_correct = attempts.filter(is_correct=True).count()
        total_points = attempts.aggregate(Sum('score'))['score__sum'] or 0
        success_rate = round((total_correct / total_quizzes * 100), 1) if total_quizzes > 0 else 0
        
        # Badges
        user_badges = UserBadge.objects.filter(user=child).select_related('badge')
        badges_count = user_badges.count()
        child_badges = [{'name': ub.badge.name, 'icon': ub.badge.icon} for ub in user_badges]
        
        # Statistiques Study
        study_sessions = StudySession.objects.filter(student=child, is_complete=True)
        total_study_seconds = sum([s.duration for s in study_sessions])
        total_study_hours = total_study_seconds // 3600
        
        # Série actuelle
        try:
            profile = child.student_profile
            current_streak = profile.current_streak or 0
        except:
            current_streak = 0
        
        # Heures d'étude cette semaine
        week_ago = timezone.now() - timedelta(days=7)
        week_sessions = study_sessions.filter(ended_at__gte=week_ago)
        study_hours_week = sum([s.duration for s in week_sessions]) // 3600
        week_percent = min((study_hours_week / 5 * 100), 100)
        
        # Performance par matière
        subject_stats = []
        raw_stats = attempts.values('quiz__subject__name').annotate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True)),
        ).order_by('-total')
        
        for stat in raw_stats:
            if stat['quiz__subject__name']:
                percentage = round((stat['correct'] / stat['total'] * 100), 1) if stat['total'] > 0 else 0
                subject_stats.append({
                    'subject': stat['quiz__subject__name'],
                    'total': stat['total'],
                    'correct': stat['correct'],
                    'percentage': percentage
                })
        
        # Récupérer le RiskScore de l'enfant
        try:
            risk_score = RiskScore.objects.filter(student_id=str(child.id)).first()
        except:
            risk_score = None
        
        # Alertes récentes (CORRIGÉ: utiliser risk_score au lieu de student)
        alerts = []
        if risk_score:
            alerts = Alert.objects.filter(
                risk_score=risk_score,
                status='pending'
            ).order_by('-created_at')[:5]
        
        # Activités récentes
        recent_attempts = attempts.select_related('quiz__subject').order_by('-created_at')[:10]
        
        context = {
            'child': child,
            'total_points': total_points,
            'total_quizzes': total_quizzes,
            'success_rate': success_rate,
            'current_streak': current_streak,
            'total_study_hours': total_study_hours,
            'badges_count': badges_count,
            'child_badges': child_badges,
            'study_hours_week': study_hours_week,
            'week_percent': week_percent,
            'subject_stats': subject_stats,
            'alerts': alerts,
            'recent_attempts': recent_attempts,
        }
    else:
        context = {'child': None}
    
    return render(request, 'dashboard/parent.html', context)