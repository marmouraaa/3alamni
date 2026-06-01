from django.db import models
from django.contrib.auth import get_user_model
import json

User = get_user_model()


class Subject(models.Model):
    """Matière scolaire"""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, default='fas fa-book')
    color = models.CharField(max_length=20, default='#667eea')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Quiz(models.Model):
    """Quiz provenant d'OpenTrivia"""
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Facile'),
        ('medium', 'Moyen'),
        ('hard', 'Difficile'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
    ]
    
    SOURCE_CHOICES = [
        ('teacher', 'Professeur'),
        ('trivia', 'OpenTrivia Database'),
    ]
    
    # Métadonnées
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_quizzes')
    
    # Contenu du quiz
    question = models.TextField()
    options = models.JSONField(default=list)
    correct_answer = models.CharField(max_length=500)
    explanation = models.TextField(blank=True)
    
    # Configuration
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS, default='medium')
    
    # Source
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='trivia')
    trivia_category_id = models.IntegerField(null=True, blank=True)
    trivia_category_name = models.CharField(max_length=100, blank=True)
    
    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_quizzes')
    validated_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    # Métriques sociales
    likes = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    
    # Statistiques
    times_played = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    def get_options_list(self):
        if isinstance(self.options, str):
            return json.loads(self.options)
        return self.options or []

    class Meta:
        ordering = ['-created_at']


class QuizAttempt(models.Model):
    """Tentative de quiz par un étudiant"""
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    
    answer = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    time_taken = models.IntegerField(default=0)
    
    score = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} - {'Correct' if self.is_correct else 'Incorrect'}"


class Badge(models.Model):
    """Badge de réussite"""
    
    BADGE_TYPES = [
        ('first_quiz', 'Premier quiz'),
        ('perfect_score', 'Score parfait'),
        ('quiz_master', 'Maître des quiz'),
        ('streak_5', 'Série de 5'),
        ('streak_10', 'Série de 10'),
    ]
    
    name = models.CharField(max_length=100)
    badge_type = models.CharField(max_length=50, choices=BADGE_TYPES, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='fas fa-medal')
    required_correct_answers = models.IntegerField(default=0)
    
    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """Badges obtenus par un utilisateur"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'badge']
    
    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"