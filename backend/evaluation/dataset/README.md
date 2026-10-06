# Evaluation dataset

This folder holds the small test set used by `evaluation/evaluate.py`. **No audio is
shipped with the project** - commercial songs are copyrighted and must not be
redistributed, so you add your own samples locally (the folder is git-ignored).

## Layout

```
dataset/
├── manifest.json          # copy of manifest.example.json, edited
├── audio/                 # .mp3 / .wav / .m4a / .mp4 ...
│   ├── english-01.mp3
│   ├── hindi-01.mp3
│   └── telugu-01.mp4
└── lyrics/                # ground-truth lyrics, UTF-8, native script
    ├── english-01.txt
    ├── hindi-01.txt
    └── telugu-01.txt
```

Each manifest entry needs `id`, `language` (`en`, `hi` or `te`), `file` and `reference`.
Write the reference lyrics exactly as sung (including repeated lines), in the
language's own script (Devanagari for Hindi, Telugu script for Telugu), because
that is what Whisper outputs. Punctuation and letter case are ignored when scoring.

## Where to get legal samples

- Songs you recorded or own the rights to.
- Creative Commons music with lyrics (for example from the Free Music Archive or
  ccMixter) - keep the attribution in the `source` field.
- Public-domain / folk songs performed by you or a friend.
- For a quick smoke test: text-to-speech over an instrumental backing track.

Aim for 3-5 clips per language, 30-90 seconds each, with a mix of slow and fast songs.

## Run

```bash
cd backend
python -m evaluation.evaluate --manifest evaluation/dataset/manifest.json
```

Results (JSON + CSV) are written to `evaluation/results/`.
