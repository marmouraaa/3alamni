# MCP (Model Context Protocol) - Early Warning Service

## Tool Name
`intervention_suggestion`

## Description
Génère une suggestion d'intervention pédagogique pour un étudiant à risque de décrochage scolaire basée sur ses indicateurs (absences, notes, comportement).

## Input Schema
```json
{
  "type": "object",
  "properties": {
    "student_name": {
      "type": "string",
      "description": "Nom complet de l'étudiant"
    },
    "absences": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Taux d'absence en pourcentage"
    },
    "avg_grade": {
      "type": "number",
      "minimum": 0,
      "maximum": 20,
      "description": "Moyenne générale sur 20"
    },
    "behavior_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10,
      "description": "Score de comportement sur 10"
    },
    "risk_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 100,
      "description": "Score de risque calculé"
    },
    "risk_level": {
      "type": "string",
      "enum": ["low", "medium", "high"],
      "description": "Niveau de risque"
    }
  },
  "required": ["student_name", "absences", "avg_grade", "behavior_score", "risk_score", "risk_level"]
}