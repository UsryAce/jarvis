"""Translation skill for Jarvis - translate text between languages."""
import json
import logging
import os
from typing import Any, Dict, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

LANG_MAP = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "russian": "ru", "chinese": "zh",
    "japanese": "ja", "korean": "ko", "arabic": "ar", "hindi": "hi",
    "dutch": "nl", "polish": "pl", "turkish": "tr", "vietnamese": "vi",
    "thai": "th", "swedish": "sv", "danish": "da", "finnish": "fi",
    "czech": "cs", "romanian": "ro", "hungarian": "hu", "greek": "el",
    "hebrew": "he", "norwegian": "no", "ukrainian": "uk",
}

SIMPLE_DICT = {
    "hello": {"es": "hola", "fr": "bonjour", "de": "hallo", "it": "ciao", "pt": "olá"},
    "goodbye": {"es": "adiós", "fr": "au revoir", "de": "auf wiedersehen", "it": "arrivederci", "pt": "tchau"},
    "thank you": {"es": "gracias", "fr": "merci", "de": "danke", "it": "grazie", "pt": "obrigado"},
    "yes": {"es": "sí", "fr": "oui", "de": "ja", "it": "sì", "pt": "sim"},
    "no": {"es": "no", "fr": "non", "de": "nein", "it": "no", "pt": "não"},
    "good morning": {"es": "buenos días", "fr": "bonjour", "de": "guten morgen", "it": "buongiorno", "pt": "bom dia"},
    "good night": {"es": "buenas noches", "fr": "bonne nuit", "de": "gute nacht", "it": "buona notte", "pt": "boa noite"},
    "please": {"es": "por favor", "fr": "s'il vous plaît", "de": "bitte", "it": "per favore", "pt": "por favor"},
    "sorry": {"es": "lo siento", "fr": "désolé", "de": "entschuldigung", "it": "mi dispiace", "pt": "desculpe"},
    "how are you": {"es": "cómo estás", "fr": "comment allez-vous", "de": "wie geht es dir", "it": "come stai", "pt": "como você está"},
}


class TranslationSkill(Skill):
    name = "translation"
    description = "Translate text between different languages"
    triggers = ["translate", "translation", "translate to"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        target_lang = params.get("target_lang", self._extract_target(text))
        source_lang = params.get("source_lang", "auto")
        content = params.get("text", self._extract_text(text))

        if not content:
            return "What should I translate? Example: translate hello to spanish"

        api_key = os.environ.get("TRANSLATE_API_KEY", "")
        if api_key:
            return await self._translate_api(content, source_lang, target_lang, api_key)
        else:
            return self._translate_simple(content, target_lang)

    def _extract_target(self, text: str) -> str:
        for lang in LANG_MAP:
            if lang in text:
                return lang
        return "spanish"

    def _extract_text(self, text: str) -> str:
        for t in ["translate", "translation"]:
            text = text.replace(t, "", 1)
        for lang in LANG_MAP:
            idx = text.find(f" to {lang}")
            if idx >= 0:
                text = text[:idx]
                break
            idx = text.find(f" in {lang}")
            if idx >= 0:
                text = text[:idx]
                break
        return text.strip().strip("'\"")

    async def _translate_api(self, content: str, source: str, target: str, api_key: str) -> str:
        import urllib.request
        import urllib.parse

        target_code = LANG_MAP.get(target, target)
        source_code = LANG_MAP.get(source, source) if source != "auto" else "auto"

        try:
            url = f"https://translation-api.example.com/translate?key={api_key}"
            data = json.dumps({
                "q": content, "source": source_code, "target": target_code
            }).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
            translated = result.get("translatedText", result.get("text", ""))
            return f"{target.title()}: {translated}"
        except Exception as e:
            logger.error(f"Translation API error, falling back to simple: {e}")
            return self._translate_simple(content, target)

    def _translate_simple(self, content: str, target: str) -> str:
        target_code = LANG_MAP.get(target, target)
        content_lower = content.lower().strip()

        if content_lower in SIMPLE_DICT:
            translation = SIMPLE_DICT[content_lower].get(target_code)
            if translation:
                return f"{target.title()}: {translation}"

        target_lang_display = target.title()
        return f"[Simple translation] Could not translate '{content[:50]}' to {target_lang_display}. Set TRANSLATE_API_KEY for full API translation."
