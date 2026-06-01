from django.urls import path
from . import views

urlpatterns = [
    path('tiktok/', views.tiktok_feed, name='tiktok_feed'),
    path('instagram/', views.instagram_feed, name='instagram_feed'),
    path('snapchat/', views.snapchat_feed, name='snapchat_feed'),
    path('facebook/', views.facebook_feed, name='facebook_feed'),
]