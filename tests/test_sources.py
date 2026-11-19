import yaml
from src.hunter.collect import review_documents
from src.hunter.report import render
from src.hunter.state import blank_state


def test_three_official_three_press_and_no_active_fake_community_feed():
    with open("config/sources.yaml", encoding="utf-8") as stream:
        sources = yaml.safe_load(stream)["sources"]
    enabled = [s for s in sources if s["enabled"]]
    assert len([s for s in enabled if s["kind"] == "official"]) == 3
    assert len([s for s in enabled if s["kind"] == "press"]) == 3
    assert not [s for s in enabled if s["kind"] == "community"]
    assert len({s["id"] for s in sources}) == len(sources)


def test_press_article_does_not_become_fake_official_release(monkeypatch):
    import src.hunter.collect as collect
    monkeypatch.setattr(
        collect, "fetch_article",
        lambda *_: {
            "status": "full_text",
            "text": "The limited box includes Aurora Mascot figurine.",
            "image_url": None,
        },
    )
    state = blank_state()
    state["documents"]["d"] = {
        "source": "press", "kind": "press",
        "url": "https://www.siliconera.com/announcement",
        "title": "Limited edition Aurora Mascot",
        "published_at": "2026-11-19T01:00:00+00:00",
    }
    summary = {"new_objects": 0}
    review_documents(state, [{
        "id": "press", "enabled": True, "kind": "press",
        "article_hosts": ["www.siliconera.com"],
    }], {"max_article_fetches_per_run": 2}, None, summary)
    assert summary["new_objects"] > 0
    for op in state["opportunities"].values():
        assert op["source_kind"] == "press"
        assert op["evidence"][0]["type"] == "press_article"


def test_email_counts_press_and_official_source_health():
    state = blank_state()
    state["source_health"] = {
        "nintendo": {"kind": "official", "status": "ok"},
        "siliconera": {"kind": "press", "status": "ok"},
        "other": {"kind": "press", "status": "failed"},
        "community": {"kind": "community", "status": "disabled"},
    }
    output = render(state, "2026-11-19")
    assert "2/3" in output
    assert "مصادر أخبار سليمة" in output
