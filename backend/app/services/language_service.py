"""Supported languages. Add an entry to SUPPORTED_LANGUAGES to enable another one."""

from dataclasses import dataclass

AUTO_LANGUAGE = "auto"


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1 code as used by Whisper
    name: str
    native_name: str


SUPPORTED_LANGUAGES: dict[str, Language] = {
    language.code: language
    for language in (
        Language("en", "English", "English"),
        Language("hi", "Hindi", "हिन्दी"),
        Language("te", "Telugu", "తెలుగు"),
    )
}


def is_valid_request(code: str) -> bool:
    return code == AUTO_LANGUAGE or code in SUPPORTED_LANGUAGES


def language_name(code: str | None) -> str | None:
    if code is None:
        return None
    language = SUPPORTED_LANGUAGES.get(code)
    return language.name if language else code


def pick_supported_language(probabilities: list[tuple[str, float]]) -> tuple[str, float] | None:
    """Most likely supported language from Whisper's per-language probabilities."""
    supported = [(code, prob) for code, prob in probabilities if code in SUPPORTED_LANGUAGES]
    if not supported:
        return None
    return max(supported, key=lambda item: item[1])
