from django.urls import path
from . import views

urlpatterns = [
    path('', views.iphone_home, name='iphone_home'),
    path('redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('student/', views.dashboard_student, name='dashboard_student'),
    path('teacher/', views.dashboard_teacher, name='dashboard_teacher'),
    path('counselor/', views.dashboard_counselor, name='dashboard_counselor'),
    path('parent/', views.dashboard_parent, name='dashboard_parent'),
]