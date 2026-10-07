"""Video handling: choose which audio track of an uploaded video to transcribe.

There is no intermediate "extracted" file. The chosen track is decoded straight from
the original container by the same FFmpeg pass an audio upload goes through
(audio_service), so a video is transcribed from exactly the samples it carries.
"""

from app.services.language_service import resolve_language
from app.utils.ffmpeg import AudioStream, MediaInfo


def select_audio_stream(info: MediaInfo, language: str | None = None) -> AudioStream:
    """The audio track to transcribe: one tagged with `language`, else the default one.

    Videos (MKV especially) often carry several tracks - dubs, commentary - and the
    first one is not necessarily the one a player would pick.
    """
    streams = info.audio_streams
    if not streams:
        raise ValueError("The media has no audio stream")

    if language:
        tagged = [s for s in streams if resolve_language(s.language) == language]
        streams = tuple(tagged) or streams
    return next((s for s in streams if s.is_default), streams[0])
