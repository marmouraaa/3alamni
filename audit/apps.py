# audit/apps.py
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = "Journal d'audit"
    
    def ready(self):
        # Importer les signaux ici si besoin
        pass