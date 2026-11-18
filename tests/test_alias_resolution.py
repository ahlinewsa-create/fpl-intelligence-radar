from src.hunter.objects import extract_objects
from src.hunter.collect import review_documents
from src.hunter.report import render
from src.hunter.state import blank_state, stable_id


JAPANESE_NEWS = (
    "「ソードカービィ&ドラグーン」「ノワールデデデ&ハイドラ」"
    "のamiiboは本日発売。"
)
FULL_CONTENT = (
    "カービィのエアライダーシリーズ amiibo、ドラグーン amiibo、"
    "ノワールデデデ&ハイドラ フィギュア、ハイドラ フィギュア、"
    "育成可能フィギュア。"
)


def test_japanese_aliases_collapse_to_two_quoted_products():
    objects = extract_objects(JAPANESE_NEWS + " " + FULL_CONTENT)
    names = [item["name"] for item in objects]
    assert len(names) == 2, names
    assert any("ソードカービィ&ドラグーン" in n for n in names)
    assert any("ノワールデデデ&ハイドラ" in n for n in names)
    assert any(item["aliases"] for item in objects)


def test_older_unverified_aliases_get_retired_not_deleted(monkeypatch):
    import src.hunter.collect as collect

    monkeypatch.setattr(
        collect, "fetch_article",
        lambda *args: {"status": "full_text", "text": FULL_CONTENT, "image_url": None},
    )
    state = blank_state()
    state["documents"]["old_article"] = {
        "source": "nintendo", "kind": "official", "title": JAPANESE_NEWS,
        "url": "https://www.nintendo.com/jp/news/example", "summary": "",
        "published_at": "2026-11-18T01:00:00+00:00",
        "first_seen": "2026-11-18T01:15:00+00:00",
        "extractor_version": "horizon-inspired-article-v2",
    }
    alias_id = stable_id("object", "old_article", "ドラグーン amiibo")
    state["opportunities"][alias_id] = {
        "id": alias_id, "name": "ドラグーン amiibo",
        "kind": "figurine", "rights_status": "unverified",
        "demand_evidence": [], "competition": {"status": "not_checked"},
        "evidence": [{"url": "https://www.nintendo.com/jp/news/example"}],
    }
    result = {"new_objects": 0}
    review_documents(
        state,
        [{"id": "nintendo", "enabled": True,
          "article_hosts": ["www.nintendo.com"], "language": "ja"}],
        {"max_article_fetches_per_run": 3}, None, result,
    )
    assert alias_id in state["opportunities"]
    assert state["opportunities"][alias_id]["status"] == "superseded"
    html = render(state, "2026-11-18")
    assert "ドラグーン amiibo" not in html
    assert "ソードカービィ" in html
