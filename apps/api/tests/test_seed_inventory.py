from app.db.seed_data import MANDATORY_PUBLISHERS, expected_channel_count, inventory_summary


def test_exactly_ten_mandatory_publishers() -> None:
    assert len(MANDATORY_PUBLISHERS) == 10


def test_all_mandatory_homepages_present() -> None:
    expected = {
        "https://www.alanba.com.kw",
        "https://alqabas.com",
        "https://www.alraimedia.com",
        "https://www.aljarida.com",
        "https://al-seyassah.com",
        "https://kuwaittimes.com",
        "https://www.arabtimesonline.com",
        "https://www.kuna.net.kw",
        "https://www.alwasat.com.kw",
        "https://alwatan.kuwait.tt",
    }
    actual = {publisher["homepage_url"] for publisher in MANDATORY_PUBLISHERS}
    assert actual == expected


def test_kuna_has_separate_ar_and_en_channels() -> None:
    kuna = next(publisher for publisher in MANDATORY_PUBLISHERS if publisher["code"] == "kuna")
    languages = {channel["language"] for channel in kuna["channels"]}
    codes = {channel["code"] for channel in kuna["channels"]}
    assert languages == {"ar", "en"}
    assert "web_ar" in codes
    assert "web_en" in codes


def test_channel_count_matches_inventory_summary() -> None:
    summary = inventory_summary()
    assert summary["publisher_count"] == 10
    assert summary["channel_count"] == expected_channel_count()
    assert summary["channel_count"] >= 11  # 9 single-channel + KUNA dual-channel
