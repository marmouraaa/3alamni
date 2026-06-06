from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import date

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', '🎓 Étudiant'),
        ('parent', '👨‍👩‍👧 Parent'),
        ('teacher', '📚 Professeur'),
        ('counselor', '🧠 Conseiller scolaire'),
        ('admin', '👑 Administrateur'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date de naissance")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Téléphone")
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(max_length=500, null=True, blank=True, verbose_name="Bio")
    
    # Pour les parents : lier à un étudiant existant
    linked_student = models.ForeignKey(
        'StudentProfile', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='linked_parents',
        verbose_name="Étudiant lié"
    )
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    @property
    def is_student(self): return self.role == 'student'
    @property
    def is_teacher(self): return self.role == 'teacher'
    @property
    def is_counselor(self): return self.role == 'counselor'
    @property
    def is_parent(self): return self.role == 'parent'
    @property
    def is_admin(self): return self.role == 'admin'


class StudentProfile(models.Model):
    LEVEL_CHOICES = [
        ('primary', '🏫 Primaire (6-11 ans)'),
        ('middle', '📚 Collège (12-14 ans)'),
        ('high', '🎓 Lycée (15-17 ans)'),
        ('university', '🏛️ Université (18-25 ans)'),
    ]
    
    HIGH_SCHOOL_SPECIALITIES = [
        ('math', 'Mathématiques'),
        ('sciences', 'Sciences Expérimentales'),
        ('tech', 'Sciences Techniques'),
        ('economics', 'Économie & Gestion'),
        ('letters', 'Lettres'),
        ('sports', 'Sport'),
    ]
    
    UNIVERSITY_MAJORS = [
        ('cs', '💻 Informatique / Génie Logiciel'),
        ('med', '🩺 Médecine / Pharmacie'),
        ('eng', '🔧 Ingénierie'),
        ('business', '📈 Commerce / Finance'),
        ('law', '⚖️ Droit'),
        ('economics', '📊 Sciences Économiques'),
        ('letters', '📖 Lettres / Langues'),
        ('arts', '🎨 Arts / Design'),
        ('science', '🔬 Sciences Fondamentales'),
        ('agri', '🌾 Agriculture'),
    ]
    parent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, verbose_name="Niveau scolaire")
    high_school_speciality = models.CharField(max_length=20, choices=HIGH_SCHOOL_SPECIALITIES, null=True, blank=True)
    high_school_year = models.IntegerField(null=True, blank=True, help_text="1,2,3,4")
    university_major = models.CharField(max_length=30, choices=UNIVERSITY_MAJORS, null=True, blank=True)
    university_year = models.IntegerField(null=True, blank=True, help_text="1-5")
    school_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="Établissement")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    anonymous_id = models.CharField(max_length=20, unique=True, verbose_name="ID anonyme", blank=True, null=True)    
    # Suivi académique
    total_study_hours = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)              # ← nouveau
    total_quizzes_completed = models.IntegerField(default=0)
    total_correct_answers = models.IntegerField(default=0)    # ← nouveau
    total_quiz_points = models.IntegerField(default=0)        # ← nouveau
    class Meta:
        verbose_name = "Profil étudiant"
        verbose_name_plural = "Profils étudiants"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_level_display()}"


class TeacherProfile(models.Model):
    SUBJECT_CHOICES = [
        ('math', 'Mathématiques'),
        ('physics', 'Physique-Chimie'),
        ('french', 'Français'),
        ('arabic', 'Arabe'),
        ('english', 'Anglais'),
        ('history', 'Histoire-Géographie'),
        ('science', 'Sciences'),
        ('informatics', 'Informatique'),
        ('philosophy', 'Philosophie'),
        ('sports', 'Sport'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES, verbose_name="Matière enseignée")
    school = models.CharField(max_length=200, verbose_name="Établissement")
    years_of_experience = models.IntegerField(default=0, verbose_name="Années d'expérience")
    
    class Meta:
        verbose_name = "Professeur"
        verbose_name_plural = "Professeurs"

    def __str__(self):
        return f"Prof. {self.user.get_full_name()} - {self.get_subject_display()}"


class CounselorProfile(models.Model):
    SPECIALITY_CHOICES = [
        ('psychologist', 'Psychologue scolaire'),
        ('orientation', 'Conseiller d\'orientation'),
        ('social', 'Assistant social'),
        ('educator', 'Éducateur spécialisé'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='counselor_profile')
    speciality = models.CharField(max_length=20, choices=SPECIALITY_CHOICES, verbose_name="Spécialité")
    license_number = models.CharField(max_length=50, verbose_name="Numéro de licence")
    available_for_chat = models.BooleanField(default=True, verbose_name="Disponible pour chat")
    
    class Meta:
        verbose_name = "Conseiller"
        verbose_name_plural = "Conseillers"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_speciality_display()}"


class ParentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    children = models.ManyToManyField(StudentProfile, blank=True, related_name='parents', verbose_name="Enfants")
    
    class Meta:
        verbose_name = "Parent"
        verbose_name_plural = "Parents"

    def __str__(self):
        return f"Parent: {self.user.get_full_name()}"