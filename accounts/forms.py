from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import StudentProfile, TeacherProfile, CounselorProfile
from datetime import date

User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Nom d\'utilisateur',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Mot de passe',
            'class': 'form-control'
        })
    )


class StudentRegisterForm(UserCreationForm):
    """Formulaire d'inscription pour les étudiants"""
    
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Email")
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date de naissance"
    )
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    level = forms.ChoiceField(choices=StudentProfile.LEVEL_CHOICES, required=True, label="Niveau scolaire")
    school_name = forms.CharField(max_length=200, required=True, label="Nom de l'établissement")
    
    # Lycée
    high_school_speciality = forms.ChoiceField(
        choices=StudentProfile.HIGH_SCHOOL_SPECIALITIES,
        required=False,
        label="Spécialité"
    )
    high_school_year = forms.ChoiceField(
        choices=[(1, '1ère année'), (2, '2ème année'), (3, '3ème année'), (4, '4ème année')],
        required=False,
        label="Année"
    )
    
    # Université
    university_major = forms.ChoiceField(
        choices=StudentProfile.UNIVERSITY_MAJORS,
        required=False,
        label="Filière"
    )
    university_year = forms.ChoiceField(
        choices=[(1, 'Licence 1'), (2, 'Licence 2'), (3, 'Licence 3'), (4, 'Master 1'), (5, 'Master 2')],
        required=False,
        label="Année d'étude"
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))
            if age < 6:
                raise ValidationError("Tu dois avoir au moins 6 ans")
            if age > 25:
                raise ValidationError("L'âge maximum est de 25 ans")
        return dob
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        
        if level == 'high':
            if not cleaned_data.get('high_school_speciality'):
                self.add_error('high_school_speciality', 'La spécialité est obligatoire')
            if not cleaned_data.get('high_school_year'):
                self.add_error('high_school_year', "L'année est obligatoire")
        elif level == 'university':
            if not cleaned_data.get('university_major'):
                self.add_error('university_major', 'La filière est obligatoire')
            if not cleaned_data.get('university_year'):
                self.add_error('university_year', "L'année est obligatoire")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.date_of_birth = self.cleaned_data['date_of_birth']
        user.phone = self.cleaned_data.get('phone', '')
        
        if commit:
            user.save()
            
            # Créer le profil étudiant
            StudentProfile.objects.create(
                user=user,
                level=self.cleaned_data['level'],
                school_name=self.cleaned_data['school_name'],
                high_school_speciality=self.cleaned_data.get('high_school_speciality'),
                high_school_year=self.cleaned_data.get('high_school_year'),
                university_major=self.cleaned_data.get('university_major'),
                university_year=self.cleaned_data.get('university_year'),
                anonymous_id=f"ETU{user.id:06d}"
            )
        return user


class ParentRegisterForm(UserCreationForm):
    """Formulaire d'inscription pour les parents"""
    
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'parent'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        
        if commit:
            user.save()
            from .models import ParentProfile
            ParentProfile.objects.create(user=user)
        return user


class TeacherRegisterForm(UserCreationForm):
    """Formulaire d'inscription pour les professeurs"""
    
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    subject = forms.ChoiceField(choices=TeacherProfile.SUBJECT_CHOICES, required=True, label="Matière enseignée")
    school = forms.CharField(max_length=200, required=True, label="Établissement")
    years_of_experience = forms.IntegerField(min_value=0, max_value=50, required=True, label="Années d'expérience")
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'teacher'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        
        if commit:
            user.save()
            TeacherProfile.objects.create(
                user=user,
                subject=self.cleaned_data['subject'],
                school=self.cleaned_data['school'],
                years_of_experience=self.cleaned_data['years_of_experience']
            )
        return user


class CounselorRegisterForm(UserCreationForm):
    """Formulaire d'inscription pour les conseillers"""
    
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    speciality = forms.ChoiceField(choices=CounselorProfile.SPECIALITY_CHOICES, required=True, label="Spécialité")
    license_number = forms.CharField(max_length=50, required=True, label="Numéro de licence professionnelle")
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'counselor'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        
        if commit:
            user.save()
            CounselorProfile.objects.create(
                user=user,
                speciality=self.cleaned_data['speciality'],
                license_number=self.cleaned_data['license_number']
            )
        return user