"""Video handling: pull the audio track out of an uploaded video with FFmpeg."""

from pathlib import Path

from app.utils.ffmpeg import run_ffmpeg

SEPARATION_SAMPLE_RATE = 44100


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """Write the first audio stream of `video_path` as stereo 44.1 kHz WAV."""
    run_ffmpeg(
        [
            "-i", str(video_path),
            "-vn",
            "-map", "0:a:0",
            "-ac", "2",
            "-ar", str(SEPARATION_SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(output_path),
        ],
        failure_message="Could not extract the audio track from this video.",
    )
    return output_path
