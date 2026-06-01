from django.test import TestCase

# Create your tests here.
# audit/tests.py

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import AuditLog
from .services import log_action, log_error, log_success, log_blocked

User = get_user_model()


@pytest.mark.django_db
class TestAuditLogModel:
    """Tests pour le modèle AuditLog - avec pytest"""

    def test_create_audit_log(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass',
            role='teacher'
        )
        
        log = AuditLog.objects.create(
            user=user,
            action='import_csv',
            result='success',
            reason='Import réussi',
            ip_address='127.0.0.1'
        )
        
        assert log.user.username == 'testuser'
        assert log.action == 'import_csv'
        assert log.result == 'success'

    def test_audit_log_str(self):
        log = AuditLog.objects.create(
            action='export_csv',
            result='success'
        )
        assert 'Export CSV' in str(log)


@pytest.mark.django_db
class TestAuditServices:
    """Tests pour les services d'audit"""

    def test_log_action_success(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass',
            role='teacher'
        )
        
        log = log_action(
            user=user,
            action='create_intervention',
            result='success',
            reason='Intervention créée',
            case_id='42'
        )
        
        assert log is not None
        assert log.action == 'create_intervention'
        assert log.result == 'success'

    def test_log_error(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass',
            role='teacher'
        )
        
        log = log_error(
            user=user,
            action='import_csv_error',
            error='Fichier CSV malformé'
        )
        
        assert log.result == 'error'
        assert 'CSV malformé' in log.reason

    def test_log_blocked(self):
        user = User.objects.create_user(
            username='student',
            password='studentpass',
            role='student'
        )
        
        log = log_blocked(
            user=user,
            action='unauthorized_access',
            reason='Rôle non autorisé'
        )
        
        assert log.result == 'blocked'
        assert log.reason == 'Rôle non autorisé'