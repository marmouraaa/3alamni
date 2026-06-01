from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.study_start, name='study_start'),
    path('api/start/', views.api_start_session, name='api_start_session'),
    path('api/complete/', views.api_complete_session, name='api_complete_session'),
    path('api/my-badges/', views.check_user_badges, name='my_badges'),
]