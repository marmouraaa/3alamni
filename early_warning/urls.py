# early_warning/urls.py

from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView
from . import views
from .schema import schema

app_name = 'early_warning'

urlpatterns = [
    # URLs existantes
    path('import/', views.import_csv, name='import_csv'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('alerts/', views.alerts_list, name='alerts_list'),
    path('alert/<int:alert_id>/', views.alert_detail, name='alert_detail'),
    path('intervention/create/<int:alert_id>/', views.intervention_create, name='intervention_create'),
    path('intervention/<int:pk>/', views.intervention_detail, name='intervention_detail'),
    path('mes-interventions/', views.mes_interventions_list, name='mes_interventions'),
    path('config/', views.threshold_config, name='threshold_config'),
    path('export/csv/', views.export_risk_report_csv, name='export_csv'),
    path('export/pdf/', views.export_risk_report_pdf, name='export_pdf'),
    path('api/risk-data/', views.api_risk_data, name='api_risk_data'),
    
    # URL GraphQL avec Strawberry
    path('graphql/', csrf_exempt(GraphQLView.as_view(schema=schema)), name='graphql'),
]