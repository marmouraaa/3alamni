# health/urls.py
from django.urls import path
from strawberry.django.views import GraphQLView
from . import views
from .schema import schema

app_name = 'health'

urlpatterns = [
    # GraphQL - Version corrigée
    path('graphql/', GraphQLView.as_view(schema=schema), name='graphql'),
    
    # Étudiant
    path('new/', views.new_request, name='new_request'),
    path('chat/<uuid:request_id>/', views.chat_view, name='chat'),
    path('timeline/<uuid:request_id>/', views.timeline_view, name='timeline'),
    
    # Conseiller
    path('dashboard/', views.counselor_dashboard, name='counselor_dashboard'),
    path('requests/', views.requests_list, name='requests_list'),
    path('override/<uuid:request_id>/', views.override_category, name='override_category'),
    path('close/<uuid:request_id>/', views.close_request, name='close_request'),
    
    # Admin
    path('audit-log/', views.security_audit_log, name='audit_log'),
]