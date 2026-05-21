from app.shared.utils import slugs


def test_generate_unique_stage_slug_adds_random_suffix_on_collision(monkeypatch):
    suffixes = iter(["frrufd"])
    monkeypatch.setattr(slugs, "random_slug_suffix", lambda length=6: next(suffixes))
    used = {"interview-1"}

    generated = slugs.generate_unique_slug("Interview 1", used, fallback="stage")

    assert generated == "interview-1-frrufd"
    assert generated in used


def test_generate_unique_stage_slug_retries_until_suffix_is_unique(monkeypatch):
    suffixes = iter(["taken1", "fresh2"])
    monkeypatch.setattr(slugs, "random_slug_suffix", lambda length=6: next(suffixes))
    used = {"interview-1", "interview-1-taken1"}

    generated = slugs.generate_unique_slug("Interview 1", used, fallback="stage")

    assert generated == "interview-1-fresh2"
    assert generated in used
