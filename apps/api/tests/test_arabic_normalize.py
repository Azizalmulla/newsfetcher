from app.core.arabic import normalize_text


def test_normalize_alef_and_diacritics() -> None:
    assert normalize_text("إيهْ آيْ") == normalize_text("ايه اي")


def test_normalize_tatweel_and_digits() -> None:
    assert normalize_text("شــركة") == "شركة"
    assert normalize_text("١٢٣") == "123"


def test_preserve_meaningful_letters() -> None:
    assert normalize_text("AI Octopus") == "ai octopus"
