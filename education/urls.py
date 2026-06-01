from django.urls import path
from . import views

urlpatterns = [
    # Création de quiz
    path('create-trivia/', views.create_trivia_quiz, name='create_trivia_quiz'),
    path('list/', views.quiz_list, name='quiz_list'),
    
    # API
    path('api/submit/<int:quiz_id>/', views.submit_quiz_answer_api, name='submit_quiz_api'),
    path('api/my-stats/', views.get_my_stats_api, name='my_stats_api'),
    
    # Réseaux sociaux
    path('tiktok/', views.tiktok_feed, name='tiktok_feed'),
    path('instagram/', views.instagram_feed, name='instagram_feed'),
    path('snapchat/', views.snapchat_feed, name='snapchat_feed'),
    path('facebook/', views.facebook_feed, name='facebook_feed'),
    
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
]