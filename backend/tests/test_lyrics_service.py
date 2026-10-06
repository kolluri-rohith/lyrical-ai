from app.services import lyrics_service
from app.services.language_service import pick_supported_language
from app.services.lyrics_service import LyricSegment
from app.services.whisper_service import RawSegment


def test_whitespace_and_punctuation_are_normalised():
    assert lyrics_service.clean_text("  hello    world  ,  again !! ") == "hello world, again!"


def test_artifacts_and_sound_tags_are_removed():
    assert lyrics_service.clean_text("[Music]") == ""
    assert lyrics_service.clean_text("♪♪") == ""
    assert lyrics_service.clean_text("Thanks for watching!") == ""
    assert lyrics_service.clean_text("♪ la la la ♪") == "la la la"


def test_indic_text_is_preserved():
    assert lyrics_service.clean_text(" तुम ही हो ") == "तुम ही हो"
    assert lyrics_service.clean_text("నువ్వే  నువ్వే") == "నువ్వే నువ్వే"


def test_post_process_keeps_repeats_and_timestamps():
    raw = [
        RawSegment(12.3, 17.2, " Hello darkness "),
        RawSegment(17.2, 21.0, "Hello darkness"),
        RawSegment(21.0, 22.0, "[Music]"),
        RawSegment(25.0, 28.5, "my old friend"),
    ]
    lines = lyrics_service.post_process(raw)
    assert [line.text for line in lines] == ["Hello darkness", "Hello darkness", "my old friend"]
    assert (lines[0].start, lines[0].end) == (12.3, 17.2)
    assert (lines[2].start, lines[2].end) == (25.0, 28.5)


def test_tiny_fragments_merge_into_previous_line():
    raw = [RawSegment(1.0, 3.0, "Let it"), RawSegment(3.1, 3.4, "be")]
    lines = lyrics_service.post_process(raw)
    assert lines == [LyricSegment(1.0, 3.4, "Let it be")]


def test_tiny_fragment_after_a_long_gap_stays_separate():
    raw = [RawSegment(1.0, 3.0, "Let it"), RawSegment(9.0, 9.4, "be")]
    assert len(lyrics_service.post_process(raw)) == 2


def test_srt_uses_segment_timestamps():
    lines = [LyricSegment(12.3, 17.2, "First line"), LyricSegment(3723.004, 3725.5, "Second line")]
    assert lyrics_service.to_srt(lines) == (
        "1\n00:00:12,300 --> 00:00:17,200\nFirst line\n"
        "\n"
        "2\n01:02:03,004 --> 01:02:05,500\nSecond line\n"
    )


def test_vtt_export():
    vtt = lyrics_service.to_vtt([LyricSegment(1.5, 2.0, "Line")])
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:01.500 --> 00:00:02.000\nLine" in vtt


def test_txt_export_with_and_without_timestamps():
    lines = [LyricSegment(12.0, 17.0, "First"), LyricSegment(77.0, 80.0, "Second")]
    assert lyrics_service.to_txt(lines) == "First\nSecond\n"
    assert lyrics_service.to_txt(lines, timestamps=True) == "[00:12] First\n[01:17] Second\n"


def test_language_choice_is_limited_to_supported_languages():
    probabilities = [("ta", 0.5), ("te", 0.3), ("hi", 0.15), ("en", 0.05)]
    assert pick_supported_language(probabilities) == ("te", 0.3)
    assert pick_supported_language([("ta", 1.0)]) is None
