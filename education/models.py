from django.db import models
from accounts.models import User, StudentProfile

class Course(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    pdf_file = models.FileField(upload_to='courses/')
    extracted_text = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.subject}"

class QuizRequest(models.Model):
    GAME_TYPES = [
        ('dragdrop','Drag & Drop'),
        ('flashcard','Flashcard'),
        ('fillblank','Remplir les blancs'),
        ('wordsearch','Mots cachés')
    ]
    NETWORKS = [
        ('tiktok','TikTok'),
        ('instagram','Instagram'),
        ('snapchat','Snapchat'),
        ('facebook','Facebook')
    ]
    STATUS = [
        ('pending','En attente'),
        ('generated','Généré'),
        ('validated','Validé'),
        ('published','Publié')
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    num_questions = models.IntegerField()
    specific_part = models.CharField(max_length=200, null=True, blank=True)
    game_type = models.CharField(max_length=20, choices=GAME_TYPES)
    target_network = models.CharField(max_length=20, choices=NETWORKS)
    ai_explanation = models.TextField(null=True)       # Track E
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz Request - {self.course} - {self.game_type}"

class Quiz(models.Model):
    quiz_request = models.OneToOneField(QuizRequest, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    game_type = models.CharField(max_length=20)
    target_network = models.CharField(max_length=20)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.target_network})"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.IntegerField()
    ai_generated = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}"

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.text[:50]}"

class StudentScore(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField()
    completed_at = models.DateTimeField(auto_now_add=True)
    time_spent = models.IntegerField()     # secondes

    def __str__(self):
        return f"{self.student} - {self.quiz} - {self.score}"