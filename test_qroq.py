# test_ai.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from early_warning.ai_service import get_ai_suggestion

# Tester avec des données
student_data = {
    'student_name': 'Ahmed Ben Ali',
    'absences': 25,
    'avg_grade': 8.5,
    'behavior_score': 5,
    'risk_score': 74,
    'risk_level': 'high'
}

result = get_ai_suggestion(student_data)
print("Suggestion:", result['suggestion'])
print("Explication:", result['explanation'])
print("Confiance:", result['confidence'])
print("Source:", result['source'])