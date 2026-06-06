# education/urls_social.py

from django.urls import path
from . import views_social

urlpatterns = [

    # ── TikTok ────────────────────────────────────────────────────────────────
    path('tiktok/submit_answer/<int:quiz_id>/', views_social.tiktok_submit_answer, name='tiktok_submit_answer'),
    path('tiktok/like/<int:quiz_id>/',          views_social.tiktok_like,           name='tiktok_like'),
    path('tiktok/share/<int:quiz_id>/',         views_social.tiktok_share,          name='tiktok_share'),

    # ── Instagram ─────────────────────────────────────────────────────────────
    path('instagram/submit_answer/<int:quiz_id>/', views_social.instagram_submit_answer, name='instagram_submit_answer'),
    path('instagram/like/<int:quiz_id>/',           views_social.instagram_like,          name='instagram_like'),
    path('instagram/share/<int:quiz_id>/',          views_social.instagram_share,         name='instagram_share'),

    # ── Snapchat ──────────────────────────────────────────────────────────────
    path('snapchat/submit_answer/<int:quiz_id>/', views_social.snapchat_submit_answer, name='snapchat_submit_answer'),
    path('snapchat/like/<int:quiz_id>/',           views_social.snapchat_like,          name='snapchat_like'),

    # ── Facebook ──────────────────────────────────────────────────────────────
    path('facebook/submit_answer/<int:quiz_id>/', views_social.facebook_submit_answer, name='facebook_submit_answer'),
    path('facebook/like/<int:quiz_id>/',           views_social.facebook_like,          name='facebook_like'),
    path('facebook/share/<int:quiz_id>/',          views_social.facebook_share,         name='facebook_share'),
    path('facebook/comment/<int:quiz_id>/',        views_social.facebook_comment,       name='facebook_comment'),
]
