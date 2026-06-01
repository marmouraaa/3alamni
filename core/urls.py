# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from early_warning import views as early_warning_views  # Import early_warning views

# ========== VUES DES DASHBOARDS ==========

@login_required
def dashboard_redirect(request):
    if request.user.role == 'student':
        return HttpResponseRedirect(reverse('student_stats'))
    elif request.user.role == 'teacher':
        # Utiliser le dashboard early_warning
        return HttpResponseRedirect(reverse('teacher_dashboard'))
    elif request.user.role == 'counselor':
        return HttpResponseRedirect(reverse('counselor_dashboard'))
    elif request.user.role == 'parent':
        return HttpResponseRedirect(reverse('parent_dashboard'))
    else:
        return HttpResponseRedirect('/admin/')

@login_required
def student_stats(request):
    return render(request, 'dashboard/student_stats.html', {'user': request.user})

# Cette vue utilise maintenant early_warning
@login_required
def teacher_dashboard(request):
    # Appeler la vue dashboard de early_warning
    return early_warning_views.dashboard(request)

@login_required
def counselor_dashboard(request):
    return render(request, 'dashboard/counselor.html', {'user': request.user})

@login_required
def parent_dashboard(request):
    return render(request, 'dashboard/parent.html', {'user': request.user})

@login_required
def iphone_home(request):
    return render(request, 'iphone/home.html', {'user': request.user})

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('dashboard/redirect/', dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/student/', student_stats, name='student_stats'),
    path('dashboard/teacher/', teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/counselor/', counselor_dashboard, name='counselor_dashboard'),
    path('dashboard/parent/', parent_dashboard, name='parent_dashboard'),
    path('iphone/', iphone_home, name='iphone_home'),
    path('profile/', profile_view, name='profile'),
    path('warning/', include('early_warning.urls')),
    path('health/', include('health.urls')),
    path('education/', include('education.urls')),
    path('study/', include('study.urls')),
    path('parental/', include('parental.urls')),
    path('audit/', include('audit.urls')),
    path('api/', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)