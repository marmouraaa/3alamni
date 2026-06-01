import uuid
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.contrib import messages
from django.conf import settings
from .models import User, StudentProfile
from audit.services import log_action

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

def _lockout_key(ip, username):
    return f"login_attempts:{ip}:{username}"

def _is_locked_out(ip, username):
    key = _lockout_key(ip, username)
    attempts = cache.get(key, 0)
    return attempts >= MAX_ATTEMPTS

def _register_failed_attempt(ip, username):
    key = _lockout_key(ip, username)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, LOCKOUT_SECONDS)
    return attempts

def _clear_attempts(ip, username):
    cache.delete(_lockout_key(ip, username))

def _redirect_by_role(user):
    """Redirection après connexion selon le rôle"""
    if user.role == 'student':
        return redirect('iphone_home')
    elif user.role == 'teacher':
        return redirect('teacher_dashboard')
    elif user.role == 'counselor':
        return redirect('counselor_dashboard')
    elif user.role == 'parent':
        return redirect('parent_dashboard')
    elif user.role == 'admin':
        return redirect('/admin/')
    else:
        return redirect('/')

# ========== VUES D'AUTHENTIFICATION ==========



from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import User

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Redirection selon le rôle
            if user.role == 'student':
                return redirect('dashboard:student')
            elif user.role == 'teacher':
                return redirect('dashboard:teacher')
            elif user.role == 'counselor':
                return redirect('dashboard:counselor')
            elif user.role == 'parent':
                return redirect('dashboard:parent')  # ← CORRIGÉ
            else:
                return redirect('iphone_home')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect')
    
    return render(request, 'accounts/login.html')
@login_required
def logout_view(request):
    if request.method == 'POST':
        if 'log_action' in globals():
            log_action(user=request.user, action='logout', result='success', request=request)
        logout(request)
        messages.info(request, "Tu as été déconnecté.")
        return redirect('login')
    return render(request, 'accounts/logout_confirm.html')

# ========== VUES D'INSCRIPTION ==========

def register_choice_view(request):
    """Page de choix du rôle"""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    return render(request, 'accounts/register_choice.html')

def register_student(request):
    """Inscription étudiant"""
    if request.user.is_authenticated:
        return redirect('iphone_home')
    
    if request.method == 'POST':
        from .forms import StudentRegisterForm
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Le save gère tout maintenant
            login(request, user)
            messages.success(request, f"Bienvenue {user.first_name} !")
            return redirect('iphone_home')
        else:
            # Afficher les erreurs pour le débogage
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        from .forms import StudentRegisterForm
        form = StudentRegisterForm()
    
    return render(request, 'accounts/register_student.html', {'form': form})

def register_parent(request):
    """Inscription parent"""
    if request.user.is_authenticated:
        return redirect('parent_dashboard')
    
    if request.method == 'POST':
        from .forms import ParentRegisterForm
        form = ParentRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Bienvenue {user.first_name} !")
            return redirect('parent_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        from .forms import ParentRegisterForm
        form = ParentRegisterForm()
    
    return render(request, 'accounts/register_parent.html', {'form': form})

def register_teacher(request):
    """Inscription professeur"""
    if request.user.is_authenticated:
        return redirect('teacher_dashboard')
    
    if request.method == 'POST':
        from .forms import TeacherRegisterForm
        form = TeacherRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Bienvenue Professeur {user.last_name} !")
            return redirect('teacher_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        from .forms import TeacherRegisterForm
        form = TeacherRegisterForm()
    
    return render(request, 'accounts/register_teacher.html', {'form': form})

def register_counselor(request):
    """Inscription conseiller"""
    if request.user.is_authenticated:
        return redirect('counselor_dashboard')
    
    if request.method == 'POST':
        from .forms import CounselorRegisterForm
        form = CounselorRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Bienvenue Conseiller {user.last_name} !")
            return redirect('counselor_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        from .forms import CounselorRegisterForm
        form = CounselorRegisterForm()
    
    return render(request, 'accounts/register_counselor.html', {'form': form})

# ========== VUES DE PROFIL ==========

@login_required
def profile_view(request):
    """Vue de profil utilisateur"""
    return render(request, 'accounts/profile.html', {'user': request.user})

def home_redirect(request):
    """Redirection vers la page d'accueil"""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    return redirect('login')