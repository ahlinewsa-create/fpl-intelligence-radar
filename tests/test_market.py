from src.hunter.market import classify_match, scan, work_context, update_market
from src.hunter.report import render
from src.hunter.scoring import compute
from src.hunter.state import blank_state


def test_exact_object_phrase_is_only_a_name_candidate():
    assert classify_match(
        "Aurora Mascot", "Aurora Mascot STL model"
    ) == "name_only_candidate"
    assert classify_match("Aurora Mascot", "Generic dragon") == "irrelevant"


def test_silent_statue_does_not_match_silent_hill_statues():
    q = "Silent Statue"
    origin = "Once Human: Season 5 gameplay showcases new boss"
    unrelated = [
        "Bubble Head Nurse Statue - Silent Hill 2",
        "Pyramid Head Silent Hill 2 printable statue",
        "Silence is Gold Abstract Statue Keep Silent",
        "Silent Sorrow Statue Decor Low Poly",
        "Puppet Nurse - Silent Hill printable statue",
    ]
    for title in unrelated:
        assert classify_match(q, title, origin) != "contextual_name_candidate"


def test_source_game_context_must_match_for_better_name_candidate():
    origin = "Once Human: Season 5 gameplay showcases new boss"
    assert classify_match(
        "Silent Statue", "Silent Statue - Once Human 3D Printable", origin
    ) == "contextual_name_candidate"
    assert classify_match(
        "Silent Statue", "Silent Statue - Silent Hill 2 printable", origin
    ) == "name_only_candidate"
    assert work_context(origin) == {"once", "human"}


def test_unicode_name_search_does_not_match_random_english():
    assert classify_match(
        "ソードカービィ&ドラグーン amiibo", "Generic Cute Dragon STL"
    ) == "irrelevant"


def test_no_api_credentials_is_not_zero_competitors(monkeypatch):
    monkeypatch.delenv("CULTS_USERNAME", raising=False)
    monkeypatch.delenv("CULTS_API_KEY", raising=False)
    result = scan("Aurora Mascot")
    assert result["status"] == "not_checked"
    assert "verified_exact_count" not in result


def test_previous_schema_gets_rescanned_and_history_kept(monkeypatch):
    monkeypatch.setenv("CULTS_USERNAME", "test-user")
    monkeypatch.setenv("CULTS_API_KEY", "dummy")
    import src.hunter.market as market
    monkeypatch.setattr(
        market, "scan",
        lambda *args: {
            "status": "sampled", "schema_version": 2, "sample_size": 8,
            "contextual_name_candidates": 0, "name_only_candidates": 0,
            "similar_name_candidates": 0,
            "verified_exact_count": None, "listings": [],
        },
    )
    state = blank_state()
    state["opportunities"]["o"] = {
        "name": "Silent Statue",
        "origin": "Once Human: Season 5",
        "competition": {
            "status": "sampled",
            "exact_name_candidates": 12,
            "sample_size": 20,
            "checked_at": "2026-11-18T12:00:00Z",
        },
    }
    assert update_market(state, 4) == 1
    assert state["opportunities"]["o"]["competition"]["schema_version"] == 2
    assert len(state["opportunities"]["o"]["competition_history"]) == 1
    assert state["opportunities"]["o"]["competition_history"][0]["schema_version"] == 1


def test_scoring_does_not_invent_market_gap():
    op = {
        "name": "Silent Statue",
        "origin": "Once Human: Season 5",
        "first_signal_date": "2026-11-18T12:00:00Z",
        "kind": "statue",
        "evidence": [{"type": "official_article", "url": "https://example.com"}],
        "demand_evidence": [],
        "competition": {
            "status": "sampled", "schema_version": 2,
            "sample_size": 20, "verified_exact_count": None,
        },
    }
    result = compute(op)
    assert "gap" in result["missing_factors"]
    assert result["decision"] == "WATCH"
    state = blank_state()
    state["opportunities"]["s"] = {**op, "score": result}
    html = render(state, "2026-11-19")
    assert "فُحصت عينة من 20 نتيجة" in html
    assert "لم يُثبت عدد الملفات المطابقة" in html
