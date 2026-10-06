"""Research evaluation: does vocal separation improve lyric transcription?

Compares two pipelines on the same songs:

    baseline  : song -> Whisper
    separated : song -> Demucs -> vocals -> Whisper

and reports WER, CER and processing time for each. CER is the more meaningful
number for Hindi and Telugu, where word boundaries and spelling variants make
WER harsh.

Usage (from the backend/ directory):

    python -m evaluation.evaluate --manifest evaluation/dataset/manifest.json

See evaluation/dataset/README.md for the dataset format.
"""

import argparse
import csv
import json
import re
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import jiwer

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services import audio_service, lyrics_service
from app.services.language_service import AUTO_LANGUAGE
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import whisper_service
from app.utils.ffmpeg import probe

PIPELINES = ("baseline", "separated")


@dataclass
class EvaluationRow:
    sample_id: str
    language: str
    pipeline: str
    detected_language: str
    audio_duration: float
    processing_time: float
    wer: float
    cer: float
    model: str
    device: str
    hypothesis: str


def normalize_for_scoring(text: str) -> str:
    """Lower-case, drop punctuation and collapse whitespace (script-agnostic)."""
    text = unicodedata.normalize("NFC", text).lower()
    kept = [
        " " if unicodedata.category(char)[0] in ("P", "S", "Z", "C") else char for char in text
    ]
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def transcribe_file(wav_path: Path, language: str, workdir: Path) -> tuple[str, str]:
    """Run the Whisper half of the pipeline; returns (lyrics, language used)."""
    whisper_input = audio_service.convert_for_whisper(wav_path, workdir / "whisper.wav")
    audio = whisper_service.load_audio(whisper_input)
    if language == AUTO_LANGUAGE:
        language, _ = whisper_service.detect_language(audio)
    lines = lyrics_service.post_process(whisper_service.transcribe(audio, language))
    return lyrics_service.build_full_text(lines), language


def evaluate_sample(sample: dict, dataset_dir: Path, language_mode: str) -> list[EvaluationRow]:
    media_path = dataset_dir / sample["file"]
    reference = normalize_for_scoring((dataset_dir / sample["reference"]).read_text("utf-8"))
    requested = sample["language"] if language_mode == "given" else AUTO_LANGUAGE
    duration = probe(media_path).duration
    rows = []

    for pipeline in PIPELINES:
        with tempfile.TemporaryDirectory(prefix="lyricalai-eval-") as tmp:
            workdir = Path(tmp)
            started = time.perf_counter()
            mix = audio_service.normalize_for_separation(media_path, workdir / "mix.wav")
            source = mix
            if pipeline == "separated":
                source = vocal_separation_service.separate_vocals(mix, workdir / "vocals.wav")
            hypothesis, language = transcribe_file(source, requested, workdir)
            elapsed = time.perf_counter() - started

        scored = normalize_for_scoring(hypothesis)
        rows.append(
            EvaluationRow(
                sample_id=sample["id"],
                language=sample["language"],
                pipeline=pipeline,
                detected_language=language,
                audio_duration=round(duration, 2),
                processing_time=round(elapsed, 2),
                wer=round(jiwer.wer(reference, scored), 4),
                cer=round(jiwer.cer(reference, scored), 4),
                model=whisper_service.model_name,
                device=whisper_service.device or "cpu",
                hypothesis=hypothesis,
            )
        )
    return rows


def print_report(rows: list[EvaluationRow]) -> None:
    header = f"{'sample':<20}{'lang':<6}{'pipeline':<11}{'WER':>8}{'CER':>8}{'time(s)':>9}{'RTF':>7}"
    print("\n" + header)
    print("-" * len(header))
    for row in rows:
        rtf = row.processing_time / row.audio_duration if row.audio_duration else 0.0
        print(
            f"{row.sample_id:<20}{row.language:<6}{row.pipeline:<11}"
            f"{row.wer:>8.3f}{row.cer:>8.3f}{row.processing_time:>9.1f}{rtf:>7.2f}"
        )

    print("\nAverages")
    for language in sorted({row.language for row in rows}) + ["all"]:
        for pipeline in PIPELINES:
            subset = [
                row
                for row in rows
                if row.pipeline == pipeline and language in (row.language, "all")
            ]
            if subset:
                wer = sum(row.wer for row in subset) / len(subset)
                cer = sum(row.cer for row in subset) / len(subset)
                print(f"  {language:<5}{pipeline:<11} WER {wer:.3f}   CER {cer:.3f}   (n={len(subset)})")


def save_results(rows: list[EvaluationRow], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"evaluation-{stamp}.json"
    json_path.write_text(
        json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2), "utf-8"
    )
    with (output_dir / f"evaluation-{stamp}.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [name for name in asdict(rows[0]) if name != "hypothesis"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    return json_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/dataset/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    parser.add_argument(
        "--language-mode",
        choices=("given", "auto"),
        default="given",
        help="'given' passes the manifest language to Whisper; 'auto' also tests detection",
    )
    arguments = parser.parse_args()

    configure_logging(get_settings().log_level)
    if not arguments.manifest.is_file():
        parser.error(
            f"{arguments.manifest} not found. Copy manifest.example.json and add your samples "
            "(see evaluation/dataset/README.md)."
        )
    samples = json.loads(arguments.manifest.read_text("utf-8"))["samples"]
    dataset_dir = arguments.manifest.parent

    rows: list[EvaluationRow] = []
    for sample in samples:
        print(f"Evaluating {sample['id']} ({sample['language']}) ...", flush=True)
        rows.extend(evaluate_sample(sample, dataset_dir, arguments.language_mode))

    if not rows:
        parser.error("The manifest contains no samples.")
    print_report(rows)
    print(f"\nSaved to {save_results(rows, arguments.output)}")


if __name__ == "__main__":
    main()
