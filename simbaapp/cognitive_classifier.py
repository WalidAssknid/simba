"""
SIMBA — Classification cognitive en temps réel
================================================
Classe chaque message étudiant (role='user') dans les codes Dedoose définis
par Morgane pour le projet SIMBA (cf. SIMBACompilationTechnicalRepport +
Rapport technique du dashboard). Le résultat est stocké directement dans
Message.metadata['cognitive'], ce qui évite toute migration de base de
données.

Utilisation typique (voir hook dans api.py::create_message_api) :

    from . import cognitive_classifier
    cognitive_classifier.classify_message_async(str(message.id))

La classification tourne dans un thread daemon pour ne jamais bloquer la
réponse HTTP de création de message (donc ne jamais bloquer le chat).
"""

import json
import logging
import threading

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

CLASSIFIER_MODEL = "gpt-4o-mini"

# ─── Codebook (Morgane, Dedoose) ─────────────────────────────────────────────
# Clés = mêmes noms courts que dans simba_dashboard.py / cognitive_scores.py
COGNITIVE_CODES = {
    "E": {
        "label": "Aide exécutive",
        "definition": (
            "L'étudiant demande à l'IA de réaliser la tâche à sa place "
            "(rédiger, résumer, reformuler directement à sa place)."
        ),
    },
    "I": {
        "label": "Aide instrumentale",
        "definition": (
            "L'étudiant demande comment faire ou quelle méthode utiliser, "
            "en gardant le contrôle de la production lui-même."
        ),
    },
    "V": {
        "label": "Vérification d'erreur",
        "definition": (
            "L'étudiant signale, conteste ou corrige une erreur produite par "
            "l'IA (ex. « Non ce n'est pas ce que j'avais demandé », "
            "« Cette information est incorrecte »)."
        ),
    },
    "S": {
        "label": "Demande de sources",
        "definition": (
            "L'étudiant exige une référence ou une justification pour une "
            "affirmation produite par l'IA (ex. « D'où vient cette "
            "information ? », « Cite tes sources »)."
        ),
    },
    "A": {
        "label": "Accès à l'information",
        "definition": (
            "L'étudiant utilise l'IA comme outil de mesure factuelle sur sa "
            "propre production (ex. « Est-ce que ça fait 300 mots ? », "
            "« Le texte est bien structuré ? »)."
        ),
    },
    "Mb": {
        "label": "Monitoring — compréhension basique",
        "definition": "L'étudiant vérifie sa compréhension de base du contenu.",
    },
    "Md": {
        "label": "Monitoring — compréhension approfondie",
        "definition": (
            "L'étudiant vérifie une compréhension plus profonde, avec "
            "réflexivité (implications, liens, nuances)."
        ),
    },
    "Pb": {
        "label": "Définition des buts",
        "definition": "L'étudiant définit ou clarifie ses objectifs pour la tâche.",
    },
    "Pp": {
        "label": "Définition du problème",
        "definition": "L'étudiant définit ou reformule le problème à résoudre.",
    },
    "Am": {
        "label": "Amélioration des prompts",
        "definition": (
            "L'étudiant reformule ou affine volontairement sa propre "
            "requête pour obtenir une meilleure réponse (itération "
            "stratégique de prompt)."
        ),
    },
    "Cd": {
        "label": "Clarification approfondie",
        "definition": "Demande de clarification qui approfondit la réflexion.",
    },
    "Cs": {
        "label": "Clarification simple",
        "definition": "Demande de clarification simple, de surface.",
    },
}

_SYSTEM_PROMPT = f"""Tu es un classifieur linguistique pour un projet de recherche en \
learning analytics (SIMBA, IRIT). Tu reçois UN SEUL message tapé par un étudiant \
à un chatbot tuteur. Tu dois indiquer, pour chacun des 12 codes ci-dessous, s'il \
s'applique à ce message précis (true/false). Un message peut activer plusieurs \
codes, ou aucun.

Codes :
{json.dumps({k: v['definition'] for k, v in COGNITIVE_CODES.items()}, ensure_ascii=False, indent=2)}

Réponds STRICTEMENT en JSON, avec une clé par code, valeur booléenne. Aucun \
texte hors JSON."""


def _get_client() -> OpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def classify_message_sync(content: str) -> dict:
    """
    Appelle GPT-4o-mini pour classifier un message étudiant. Retourne un dict
    {code: bool} pour les 12 codes du codebook. En cas d'erreur, retourne un
    dict tout à False (fail-safe, ne bloque jamais le pipeline de chat).
    """
    fallback = {code: False for code in COGNITIVE_CODES}
    if not content or not content.strip():
        return fallback

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Message étudiant : {content}"},
            ],
            max_tokens=300,
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        result = {code: bool(parsed.get(code, False)) for code in COGNITIVE_CODES}
        return result
    except Exception as e:
        logger.error(f"[cognitive_classifier] Classification failed: {e}")
        return fallback


def classify_and_store(message_id: str) -> None:
    """
    Classifie un message déjà en base (par id) et fusionne le résultat dans
    Message.metadata['cognitive']. Conçu pour tourner en tâche de fond.
    """
    # Import local pour éviter les soucis de chargement circulaire d'apps Django
    from .models import Message

    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        logger.warning(f"[cognitive_classifier] Message {message_id} introuvable.")
        return

    codes = classify_message_sync(message.content)

    metadata = message.metadata or {}
    metadata["cognitive"] = codes
    message.metadata = metadata
    message.save(update_fields=["metadata"])
    logger.info(f"[cognitive_classifier] Message {message_id} classifié : {codes}")


def classify_message_async(message_id: str) -> None:
    """
    Lance classify_and_store dans un thread daemon pour ne jamais ralentir la
    réponse HTTP de création de message (donc ne jamais ralentir le chat).

    NB pour une VM de prod avec plusieurs workers Gunicorn, un vrai système de
    tâches (Celery/RQ) serait préférable à terme ; un thread suffit pour le
    prototype et le volume actuel de SIMBA.
    """
    thread = threading.Thread(
        target=classify_and_store, args=(message_id,), daemon=True
    )
    thread.start()
