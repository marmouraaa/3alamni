# audit/urls.py
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('logs/', views.audit_logs, name='logs'),
    path('stats/', views.audit_stats, name='stats'),
]