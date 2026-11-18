from src.hunter.collect import review_documents
from src.hunter.report import render
from src.hunter.state import blank_state


def test_previous_news_is_reanalyzed_even_if_rss_is_unchanged(monkeypatch):
    import src.hunter.collect as collect

    monkeypatch.setattr(
        collect, "fetch_article",
        lambda client, url, allowed_hosts: {
            "status": "full_text",
            "text": "This collector set includes Aurora Mascot figurine and Lunar Crest badge.",
            "image_url": "https://example.org/news-image.jpg",
        },
    )
    state = blank_state()
    state["documents"]["legacy"] = {
        "source": "official", "kind": "official",
        "url": "https://example.org/old-article", "title": "A Collector Box",
        "first_seen": "2026-11-17T12:00:00+00:00",
        "published_at": "2026-11-17T09:00:00+00:00",
    }
    settings = {"max_article_fetches_per_run": 8}
    sources = [{"id": "official", "enabled": True, "region": "global",
                "language": "en", "article_hosts": ["example.org"]}]
    summary = {"new_objects": 0}
    review_documents(state, sources, settings, None, summary)
    assert summary["articles_reviewed"] == 1
    assert summary["article_full_text"] == 1
    assert summary["new_objects"] > 0
    assert state["documents"]["legacy"]["analysis_status"] == "full_text"
    assert any(o.get("image_url") for o in state["opportunities"].values())


def test_report_does_not_hide_original_news_if_no_objects():
    state = blank_state()
    state["documents"]["sample"] = {
        "title": "New Collector's Edition for Game",
        "url": "https://example.org/official",
        "source": "official",
        "kind": "official",
        "published_at": "2026-11-18T14:00:00+00:00",
        "summary": "Physical boxed game launch.",
    }
    html = render(state, "2026-11-18")
    assert "أهم الأخبار والإشارات" in html
    assert "New Collector" in html
    assert "غير مفحوص" in html or "لم يُستخرج" in html
    assert "الرابط" not in html or "فتح الخبر الأصلي" in html
