# early_warning/tests.py

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from unittest.mock import patch

from .models import RiskScore, Alert, Intervention, ThresholdConfig

User = get_user_model()


@pytest.fixture
@pytest.mark.django_db
def teacher_user():
    return User.objects.create_user(
        username='teacher',
        password='teacher123',
        role='teacher'
    )


@pytest.fixture
@pytest.mark.django_db
def student_user():
    return User.objects.create_user(
        username='student',
        password='student123',
        role='student'
    )


@pytest.fixture
@pytest.mark.django_db
def risk_score():
    return RiskScore.objects.create(
        student_name="Ahmed Ben Ali",
        student_id="STU001",
        class_name="3ème Maths",
        absences=25,
        avg_grade=8.5,
        behavior_score=5,
        risk_score=52.0,
        risk_level='medium'
    )


@pytest.fixture
@pytest.mark.django_db
def alert(risk_score):
    return Alert.objects.create(
        risk_score=risk_score,
        message="Alerte test",
        status='pending'
    )


@pytest.fixture
@pytest.mark.django_db
def client_logged_in_teacher(client, teacher_user):
    client.force_login(teacher_user)
    return client


@pytest.fixture
@pytest.mark.django_db
def client_logged_in_student(client, student_user):
    client.force_login(student_user)
    return client


@pytest.mark.django_db
class TestRiskScoreModel:
    def test_create_risk_score(self, risk_score):
        assert risk_score.student_name == "Ahmed Ben Ali"
        assert risk_score.risk_score == 52.0

    def test_risk_level_emoji(self, risk_score):
        assert risk_score.risk_level_emoji() == '🟠'


@pytest.mark.django_db
class TestAlertModel:
    def test_create_alert(self, alert, risk_score):
        assert alert.risk_score == risk_score
        assert alert.status == 'pending'

    def test_status_color(self, alert):
        assert alert.status_color() == '#E24B4A'


@pytest.mark.django_db
class TestThresholdConfigModel:
    def test_singleton_config(self):
        config1 = ThresholdConfig.get_config()
        config2 = ThresholdConfig.get_config()
        assert config1.id == config2.id

    def test_default_values(self):
        config = ThresholdConfig.get_config()
        assert config.high_risk_threshold == 70
        assert config.medium_risk_threshold == 40


@pytest.mark.django_db
class TestViews:
    def test_dashboard_accessible_teacher(self, client_logged_in_teacher):
        response = client_logged_in_teacher.get(reverse('early_warning:dashboard'))
        assert response.status_code == 200

    def test_threshold_config_blocked_student(self, client_logged_in_student):
        response = client_logged_in_student.get(reverse('early_warning:threshold_config'))
        assert response.status_code == 403

    def test_anonymous_access_dashboard(self, client):
        response = client.get(reverse('early_warning:dashboard'))
        assert response.status_code == 302  # Redirect to login