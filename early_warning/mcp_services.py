# early_warning/mcp_service.py

"""
Service MCP pour Early Warning — utilise Groq API (Llama3)
Protocol MCP v1.0 — outil : intervention_suggestion
"""
import json
import uuid
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MCPEarlyWarningService:
    """
    Service MCP pour générer des suggestions d'intervention.
    Utilise Groq API avec Llama3.
    Fallback déterministe si l'API est indisponible.
    """

    TOOL_NAME = "intervention_suggestion"

    def __init__(self):
        self.api_key = getattr(settings, 'GROQ_API_KEY', '')
        self.model = "llama3-70b-8192"  # ou "llama3-8b-8192"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self._available = bool(self.api_key)
        if not self._available:
            logger.warning("[MCP EW] GROQ_API_KEY manquante — fallback actif.")

    def suggest_intervention(self, risk_score_obj):
        """
        Appel MCP synchrone : génère une suggestion d'intervention.
        Retourne un dict normalisé.
        """
        trace_id = f"ew_{risk_score_obj.id}_{uuid.uuid4().hex[:6]}"
        logger.info(f"[MCP] {self.TOOL_NAME} — trace_id={trace_id}")

        if not self._available:
            return self._fallback(risk_score_obj, trace_id, "Groq key manquante")

        prompt = self._build_prompt(risk_score_obj, trace_id)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es un assistant pédagogique spécialisé dans la prévention "
                            "du décrochage scolaire. Réponds UNIQUEMENT en JSON valide, "
                            "sans markdown, sans texte avant ou après le JSON."
                        )
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            }

            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=15
            )
            response.raise_for_status()

            raw = response.json()["choices"][0]["message"]["content"].strip()

            # Nettoyage des backticks et du markdown
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)

            # Validation de l'action
            valid_actions = {"quiz", "meeting", "followup", "counseling"}
            if result.get("action") not in valid_actions:
                result["action"] = "followup"

            self._log_success(trace_id, result)

            return {
                "action": result["action"],
                "description": result.get("description", ""),
                "primary_factor": result.get("primary_factor", ""),
                "secondary_factor": result.get("secondary_factor", ""),
                "basis": (
                    f"Analyse IA: {risk_score_obj.absences}% absences, "
                    f"{risk_score_obj.avg_grade}/20, "
                    f"comportement {risk_score_obj.behavior_score}/10"
                ),
                "confidence": float(result.get("confidence", 0.8)),
                "explanation": result.get("explanation", ""),
                "fallback_used": False,
                "trace_id": trace_id,
            }

        except json.JSONDecodeError as e:
            logger.error(f"[MCP] JSON invalide: {e}")
            return self._fallback(risk_score_obj, trace_id, f"JSON invalide: {e}")
        except requests.exceptions.Timeout:
            logger.error("[MCP] Timeout API Groq")
            return self._fallback(risk_score_obj, trace_id, "Timeout API Groq")
        except requests.exceptions.HTTPError as e:
            logger.error(f"[MCP] Erreur HTTP: {e.response.status_code} - {e.response.text}")
            return self._fallback(risk_score_obj, trace_id, f"Erreur HTTP: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[MCP] Erreur inattendue: {e}")
            return self._fallback(risk_score_obj, trace_id, str(e))

    def _build_prompt(self, r, trace_id):
        """Construire le prompt pour l'IA"""
        return f"""
[MCP trace_id: {trace_id}] [Outil: {self.TOOL_NAME}]

Étudiant à risque de décrochage scolaire:
- Nom: {r.student_name}
- Taux d'absences: {r.absences}%
- Moyenne générale: {r.avg_grade}/20
- Score comportement: {r.behavior_score}/10
- Score de risque global: {r.risk_score:.1f}/100
- Niveau de risque: {r.risk_level}

Actions possibles:
- quiz: Quiz personnalisé pour identifier les lacunes
- meeting: Réunion avec les parents
- followup: Séances de suivi pédagogique
- counseling: Orientation vers un psychologue scolaire

Réponds UNIQUEMENT en JSON avec cette structure exacte:
{{
    "action": "meeting",
    "description": "Description détaillée de l'action proposée",
    "primary_factor": "Facteur principal du risque",
    "secondary_factor": "Facteur secondaire",
    "confidence": 0.85,
    "explanation": "Explication de la suggestion"
}}

Assure-toi que le JSON est valide et ne contient pas de texte supplémentaire.
"""

    def _log_success(self, trace_id, result):
        """Loguer le succès de l'appel"""
        logger.info(f"[MCP] Succès {trace_id}: action={result.get('action')}, confiance={result.get('confidence')}")

    def _fallback(self, r, trace_id, reason):
        """
        Règles déterministes si Groq est indisponible
        """
        logger.warning(f"[MCP:{trace_id}] Fallback utilisé — {reason}")

        score = r.risk_score
        absences = r.absences
        avg = r.avg_grade
        behavior = r.behavior_score

        # Règles de décision
        if absences > 20:
            action = 'meeting'
            desc = f"Réunion urgente parents-professeurs. {absences}% d'absences, seuil critique dépassé."
            primary = f"Absences excessives ({absences}%)"
            conf = 0.85
        elif avg < 8:
            action = 'followup'
            desc = f"Soutien scolaire intensif immédiat. Moyenne {avg}/20, bien en dessous de la moyenne."
            primary = f"Moyenne très faible ({avg}/20)"
            conf = 0.82
        elif behavior < 5:
            action = 'counseling'
            desc = f"Orientation vers le psychologue scolaire. Comportement noté {behavior}/10."
            primary = f"Difficultés comportementales ({behavior}/10)"
            conf = 0.78
        elif score >= 70:
            action = 'meeting'
            desc = "Plan d'intervention urgent multi-axes. Score de risque très élevé."
            primary = f"Score de risque critique ({score:.0f}/100)"
            conf = 0.80
        elif score >= 40:
            action = 'quiz'
            desc = f"Quiz personnalisés pour identifier les lacunes. Moyenne actuelle: {avg}/20."
            primary = f"Difficultés académiques modérées (score {score:.0f}/100)"
            conf = 0.68
        else:
            action = 'quiz'
            desc = f"Quiz de consolidation et suivi préventif. Moyenne: {avg}/20."
            primary = "Surveillance préventive"
            conf = 0.60

        # Facteurs secondaires
        secondary = []
        if absences > 15:
            secondary.append(f"Absences ({absences}%)")
        if avg < 10:
            secondary.append(f"Moyenne faible ({avg}/20)")
        if behavior < 5:
            secondary.append(f"Comportement ({behavior}/10)")

        return {
            "action": action,
            "description": desc,
            "primary_factor": primary,
            "secondary_factor": ", ".join(secondary) if secondary else "Aucun facteur secondaire significatif",
            "basis": (
                f"Règles de fallback: {absences}% absences, {avg}/20 de moyenne, "
                f"comportement {behavior}/10"
            ),
            "confidence": conf,
            "explanation": f"[Mode fallback] {reason[:100]}",
            "fallback_used": True,
            "trace_id": trace_id,
        }


# Singleton
mcp_ew_service = MCPEarlyWarningService()