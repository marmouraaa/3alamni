from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_choice_view, name='register_choice'),
    path('register/student/', views.register_student, name='register_student'),
    path('register/parent/', views.register_parent, name='register_parent'),
    path('register/teacher/', views.register_teacher, name='register_teacher'),
    path('register/counselor/', views.register_counselor, name='register_counselor'),
    path('profile/', views.profile_view, name='profile'),
    path('', views.home_redirect, name='home'),
]