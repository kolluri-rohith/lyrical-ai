"""Supported languages. Add an entry to SUPPORTED_LANGUAGES to enable another one."""

from dataclasses import dataclass

AUTO_LANGUAGE = "auto"


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1 code as used by Whisper
    name: str
    native_name: str
    iso639_2: str  # three-letter code, as used in video container language tags


SUPPORTED_LANGUAGES: dict[str, Language] = {
    language.code: language
    for language in (
        Language("en", "English", "English", "eng"),
        Language("hi", "Hindi", "हिन्दी", "hin"),
        Language("te", "Telugu", "తెలుగు", "tel"),
    )
}


def resolve_language(value: str | None) -> str | None:
    """Code of a supported language given its code, tag or name ("hi", "hin", "Hindi").

    Returns None for anything that is not a supported language.
    """
    wanted = (value or "").strip().lower()
    if not wanted:
        return None
    for language in SUPPORTED_LANGUAGES.values():
        if wanted in (
            language.code,
            language.iso639_2,
            language.name.lower(),
            language.native_name.lower(),
        ):
            return language.code
    return None


def resolve_request(value: str) -> str | None:
    """Normalise the language sent with an upload to "auto" or a supported code."""
    if value.strip().lower() == AUTO_LANGUAGE:
        return AUTO_LANGUAGE
    return resolve_language(value)


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
