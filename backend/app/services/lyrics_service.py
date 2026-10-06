"""Lyric post-processing and export (TXT / SRT / VTT).

Post-processing only tidies what Whisper produced. It never adds words and it
keeps repeated lines, because repetition is normal in songs.
"""

import re
from dataclasses import dataclass

# Lines Whisper is known to hallucinate over music/silence (from subtitle training data).
_ARTIFACT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^(thanks|thank you)( so much)? for watching[.!]*$",
        r"^(please )?(like(,| and)? )?subscribe( to (my|the|our) channel)?[.!]*$",
        r"^subtitles? (by|from) .*$",
        r"^(sub)?titles? (by )?the amara\.org community$",
        r"^(transcribed|translated|captioned|captions) by .*$",
        r"^www\.[^\s]+$",
    )
]
# Bracketed sound tags such as [Music], (applause), *music*.
_SOUND_TAG = re.compile(
    r"[\[(*]\s*(music|musik|applause|laughter|instrumental|silence|संगीत|సంగీతం)[^\])*]*[\])*]",
    re.IGNORECASE,
)
_MUSIC_SYMBOLS = re.compile(r"[♪♫♬♩🎵🎶]+")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.!?;:।])")
_REPEATED_PUNCTUATION = re.compile(r"([,!?;:।])\1+")
_LONG_ELLIPSIS = re.compile(r"\.{4,}")
_WHITESPACE = re.compile(r"\s+")
_HAS_WORD_CHARACTER = re.compile(r"\w", re.UNICODE)

# A fragment this short that sits right after the previous line is merged into it.
TINY_FRAGMENT_MAX_CHARS = 3
TINY_FRAGMENT_MAX_GAP_SECONDS = 0.5


@dataclass(frozen=True)
class LyricSegment:
    start: float
    end: float
    text: str


def clean_text(text: str) -> str:
    """Tidy one line of transcript; returns "" when nothing meaningful is left."""
    cleaned = _SOUND_TAG.sub(" ", text)
    cleaned = _MUSIC_SYMBOLS.sub(" ", cleaned)
    cleaned = cleaned.replace("…", "...")
    cleaned = _LONG_ELLIPSIS.sub("...", cleaned)
    cleaned = _REPEATED_PUNCTUATION.sub(r"\1", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", cleaned)

    if not _HAS_WORD_CHARACTER.search(cleaned):
        return ""
    if any(pattern.match(cleaned) for pattern in _ARTIFACT_PATTERNS):
        return ""
    return cleaned


def post_process(segments: list) -> list[LyricSegment]:
    """Clean raw Whisper segments (anything with .start/.end/.text) into lyric lines."""
    lines: list[LyricSegment] = []
    for segment in sorted(segments, key=lambda item: item.start):
        text = clean_text(segment.text)
        if not text:
            continue
        start = max(0.0, float(segment.start))
        end = max(start, float(segment.end))

        previous = lines[-1] if lines else None
        is_tiny = len(text) <= TINY_FRAGMENT_MAX_CHARS
        if previous and is_tiny and start - previous.end <= TINY_FRAGMENT_MAX_GAP_SECONDS:
            lines[-1] = LyricSegment(previous.start, end, f"{previous.text} {text}")
            continue
        lines.append(LyricSegment(round(start, 3), round(end, 3), text))
    return lines


def build_full_text(lines: list) -> str:
    return "\n".join(line.text for line in lines)


def format_clock(seconds: float) -> str:
    """mm:ss (or h:mm:ss) for display next to a lyric line."""
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _subtitle_timestamp(seconds: float, separator: str) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def to_txt(lines: list, *, timestamps: bool = False) -> str:
    if timestamps:
        body = "\n".join(f"[{format_clock(line.start)}] {line.text}" for line in lines)
    else:
        body = build_full_text(lines)
    return body + "\n"


def to_srt(lines: list) -> str:
    blocks = []
    for number, line in enumerate(lines, start=1):
        start = _subtitle_timestamp(line.start, ",")
        end = _subtitle_timestamp(line.end, ",")
        blocks.append(f"{number}\n{start} --> {end}\n{line.text}\n")
    return "\n".join(blocks)


def to_vtt(lines: list) -> str:
    blocks = ["WEBVTT\n"]
    for line in lines:
        start = _subtitle_timestamp(line.start, ".")
        end = _subtitle_timestamp(line.end, ".")
        blocks.append(f"{start} --> {end}\n{line.text}\n")
    return "\n".join(blocks)
