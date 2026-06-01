from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('student/', views.dashboard_student, name='student'),
    path('teacher/', views.dashboard_teacher, name='teacher'),
    path('counselor/', views.dashboard_counselor, name='counselor'),
    path('parent/', views.dashboard_parent, name='parent'),  # ← Ajoute cette ligne
]