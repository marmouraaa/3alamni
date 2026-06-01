"""
Service d'intégration avec Open Trivia Database API
Documentation: https://opentdb.com/api_config.php
"""

import requests
import logging
import html
import random
from typing import Dict, List, Optional, Tuple
from django.utils import timezone

logger = logging.getLogger(__name__)


class OpenTriviaService:
    """Service complet pour interagir avec l'API OpenTrivia"""
    
    BASE_URL = "https://opentdb.com"
    API_URL = f"{BASE_URL}/api.php"
    
    # Mapping des catégories OpenTrivia (ID → Nom)
    CATEGORIES = {
        9: "Culture Générale",
        10: "Livres",
        11: "Films",
        12: "Musique",
        13: "Comédies Musicales",
        14: "Télévision",
        15: "Jeux Vidéo",
        16: "Jeux de Société",
        17: "Sciences et Nature",
        18: "Informatique",
        19: "Mathématiques",
        20: "Mythologie",
        21: "Sports",
        22: "Géographie",
        23: "Histoire",
        24: "Politique",
        25: "Art",
        26: "Célébrités",
        27: "Animaux",
        28: "Véhicules",
        29: "BD",
        30: "Gadgets",
        31: "Anime et Manga",
        32: "Cartoon"
    }
    
    DIFFICULTY_LEVELS = {
        'easy': 'Facile',
        'medium': 'Moyen',
        'hard': 'Difficile'
    }
    
    @classmethod
    def get_all_categories(cls) -> List[Dict]:
        """Récupère toutes les catégories disponibles"""
        return [{"id": k, "name": v} for k, v in cls.CATEGORIES.items()]
    
    @classmethod
    def fetch_questions(
        cls,
        amount: int = 10,
        category: int = None,
        difficulty: str = None,
        question_type: str = None,
    ) -> Dict:
        """
        Récupère des questions depuis OpenTrivia API
        """
        amount = max(1, min(50, amount))
        
        params = {"amount": amount}
        
        if category and category != 0:
            params["category"] = category
        if difficulty and difficulty in cls.DIFFICULTY_LEVELS:
            params["difficulty"] = difficulty
        if question_type and question_type in ['multiple', 'boolean']:
            params["type"] = question_type
        
        try:
            logger.info(f"Appel OpenTrivia API: {params}")
            response = requests.get(cls.API_URL, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                response_code = data.get('response_code', 0)
                
                if response_code == 0:
                    questions = []
                    for q in data.get('results', []):
                        questions.append(cls._format_question(q))
                    
                    return {
                        "success": True,
                        "questions": questions,
                        "total": len(questions),
                    }
                else:
                    error_messages = {
                        1: "Pas assez de questions disponibles",
                        2: "Paramètre invalide",
                        3: "Token non trouvé",
                        4: "Plus de questions disponibles",
                        5: "Trop de requêtes (attendez 5 secondes)"
                    }
                    return {
                        "success": False,
                        "error": error_messages.get(response_code, "Erreur inconnue"),
                        "questions": []
                    }
            else:
                return {"success": False, "error": f"Erreur HTTP {response.status_code}", "questions": []}
                
        except Exception as e:
            logger.error(f"Erreur OpenTrivia: {e}")
            return {"success": False, "error": str(e), "questions": []}
    
    @classmethod
    def _format_question(cls, question: Dict) -> Dict:
        """Formate et décode une question"""
        decoded_question = html.unescape(question.get('question', ''))
        decoded_correct = html.unescape(question.get('correct_answer', ''))
        decoded_incorrect = [html.unescape(ans) for ans in question.get('incorrect_answers', [])]
        
        question_type = question.get('type', 'multiple')
        if question_type == 'boolean':
            decoded_correct = "Vrai" if decoded_correct.lower() == "true" else "Faux"
            decoded_incorrect = ["Faux" if decoded_correct == "Vrai" else "Vrai"]
        
        all_options = [decoded_correct] + decoded_incorrect
        random.shuffle(all_options)
        
        return {
            "question": decoded_question,
            "correct_answer": decoded_correct,
            "all_options": all_options,
            "category": html.unescape(question.get('category', '')),
            "difficulty": question.get('difficulty', 'medium'),
            "difficulty_label": cls.DIFFICULTY_LEVELS.get(question.get('difficulty', 'medium'), 'Moyen'),
            "type": question_type,
        }


class TriviaQuizManager:
    """Gestionnaire de quiz OpenTrivia"""
    
    @staticmethod
    def create_quiz_from_trivia(
        teacher,
        subject_id: int,
        amount: int,
        category: int = None,
        difficulty: str = None,
        question_type: str = None,
        title: str = None
    ) -> Tuple[Optional[List], Optional[str]]:
        """Crée des quiz à partir d'OpenTrivia"""
        from .models import Subject, Quiz
        
        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            return None, f"Matière non trouvée"
        
        result = OpenTriviaService.fetch_questions(
            amount=amount,
            category=category,
            difficulty=difficulty,
            question_type=question_type
        )
        
        if not result['success']:
            return None, result.get('error', 'Erreur de récupération')
        
        if not result['questions']:
            return None, "Aucune question récupérée"
        
        created_quizzes = []
        category_name = OpenTriviaService.CATEGORIES.get(category, "Général") if category else "Général"
        
        for idx, q_data in enumerate(result['questions']):
            quiz_title = title or f"Quiz {subject.name} - {category_name}"
            if len(result['questions']) > 1:
                quiz_title = f"{quiz_title} #{idx+1}"
            
            quiz = Quiz.objects.create(
                title=quiz_title,
                subject=subject,
                teacher=teacher,
                question=q_data['question'],
                options=q_data['all_options'],
                correct_answer=q_data['correct_answer'],
                explanation=f"Catégorie: {q_data['category']} | Difficulté: {q_data['difficulty_label']}",
                difficulty=q_data['difficulty'],
                status='published',
                validated_by=teacher,
                validated_at=timezone.now(),
                source='trivia',
                trivia_category_id=category,
                trivia_category_name=q_data['category']
            )
            created_quizzes.append(quiz)
        
        return created_quizzes, None
    
    @staticmethod
    def get_available_configurations() -> Dict:
        """Retourne les configurations disponibles"""
        return {
            "categories": OpenTriviaService.get_all_categories(),
            "difficulties": [
                {'value': None, 'label': '🎲 Tous niveaux'},
                {'value': 'easy', 'label': '🌟 Facile'},
                {'value': 'medium', 'label': '⭐ Moyen'},
                {'value': 'hard', 'label': '🔥 Difficile'}
            ],
            "types": [
                {'value': None, 'label': '📋 Tous types'},
                {'value': 'multiple', 'label': '🔘 Choix multiples'},
                {'value': 'boolean', 'label': '✓/✗ Vrai/Faux'}
            ],
            "max_questions": 50,
            "min_questions": 1,
        }


class QuizScoreService:
    """Gestion des scores"""
    
    @staticmethod
    def update_student_stats(student, quiz_attempt):
        """Met à jour les stats de l'étudiant"""
        from accounts.models import StudentProfile
        
        try:
            profile = student.student_profile
        except:
            profile = StudentProfile.objects.create(user=student)
        
        profile.total_quizzes_completed += 1
        
        if quiz_attempt.is_correct:
            profile.total_correct_answers += 1
            score = 100
        else:
            score = 0
        
        profile.total_quiz_points += score
        quiz_attempt.score = score
        quiz_attempt.save()
        
        # Gestion du streak
        if quiz_attempt.is_correct:
            profile.current_streak += 1
            if profile.current_streak > profile.best_streak:
                profile.best_streak = profile.current_streak
        else:
            profile.current_streak = 0
        
        profile.save()
        
        return {
            'points_earned': score,
            'new_total': profile.total_quiz_points,
            'streak': profile.current_streak,
            'success_rate': round((profile.total_correct_answers / profile.total_quizzes_completed * 100), 1) if profile.total_quizzes_completed > 0 else 0,
        }


class BadgeService:
    """Service des badges"""
    
    @staticmethod
    def check_and_award_badges(user, attempt):
        """Vérifie et attribue les badges"""
        from .models import Badge, UserBadge, QuizAttempt
        
        awarded = []
        
        total_correct = QuizAttempt.objects.filter(student=user, is_correct=True).count()
        
        # Compter le streak
        consecutive = 0
        for att in QuizAttempt.objects.filter(student=user).order_by('-created_at'):
            if att.is_correct:
                consecutive += 1
            else:
                break
        
        badge_rules = {
            'first_quiz': {'required': 1, 'name': '🌟 Premier Pas', 'description': 'Premier quiz complété!'},
            'perfect_score': {'required': 5, 'name': '💯 Score Parfait', 'description': '5 réponses correctes'},
            'quiz_master': {'required': 20, 'name': '🎓 Maître des Quiz', 'description': '20 quiz réussis'},
            'streak_5': {'required': 5, 'name': '🔥 En Rafale', 'description': '5 bonnes réponses consécutives'},
            'streak_10': {'required': 10, 'name': '⚡ Légende', 'description': '10 bonnes réponses consécutives'},
        }
        
        for badge_key, rule in badge_rules.items():
            badge, _ = Badge.objects.get_or_create(
                badge_type=badge_key,
                defaults={
                    'name': rule['name'],
                    'description': rule['description'],
                    'required_correct_answers': rule['required']
                }
            )
            
            if UserBadge.objects.filter(user=user, badge=badge).exists():
                continue
            
            earned = False
            if badge_key == 'streak_5' and consecutive >= 5:
                earned = True
            elif badge_key == 'streak_10' and consecutive >= 10:
                earned = True
            elif total_correct >= rule['required']:
                earned = True
            
            if earned:
                UserBadge.objects.create(user=user, badge=badge)
                awarded.append(badge)
        
        return awarded