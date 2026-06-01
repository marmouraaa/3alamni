# early_warning/apps.py
from django.apps import AppConfig


class EarlyWarningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'early_warning'
    verbose_name = 'Système d\'alerte précoce'
    
    def ready(self):
        # Importer les signaux ici si besoin
        pass