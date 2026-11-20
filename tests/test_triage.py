from src.hunter.triage import group_events, demand_coverage, select_news
from src.hunter.report import render
from src.hunter.state import blank_state


def object_from_article(name, url, first_signal_date, kind="replica"):
    return {
        "name": name,
        "kind": kind,
        "origin": "World of Fallout Exhibit at the Las Vegas Atomic Museum",
        "first_signal_date": first_signal_date,
        "discovery_date": "2026-11-19T02:00:00+03:00",
        "evidence": [{"type": "official_article", "url": url}],
        "demand_evidence": [],
        "competition": {"status": "not_checked"},
        "score": {"lower": 21.5, "confidence": 49, "decision": "WATCH"},
    }


def test_two_objects_one_announcement_are_one_event():
    url = "https://news.xbox.com/en-us/fallout-exhibit/"
    state = blank_state()
    state["opportunities"] = {
        "x": object_from_article("Mister Handy replica", url, "2026-11-18T01:10:00+00:00"),
        "y": object_from_article("terminal replicas", url, "2026-11-18T01:10:00+00:00"),
    }
    groups = group_events(list(state["opportunities"].values()), "2026-11-19")
    assert len(groups) == 1
    assert len(groups[0]["members"]) == 1
    assert groups[0]["type"] == "exhibition"
    html = render(state, "2026-11-19")
    assert "Mister Handy replica" in html
    assert "terminal replicas" not in html
    assert html.count("🔎 عنصر مرشح") == 1
    assert "معرض / محتوى متحفي" in html
    assert "مصادر النقاش غير مفحوصة" in html


def test_old_announcement_does_not_become_new_when_reextracted():
    state = blank_state()
    op = object_from_article(
        "Legacy amiibo",
        "https://www.nintendo.co.jp/articles/old",
        "2026-10-11T06:00:00+00:00",
    )
    op["discovery_date"] = "2026-11-19T07:00:00+03:00"
    state["opportunities"]["legacy"] = op
    groups = group_events([op], "2026-11-19")
    assert groups == []
    html = render(state, "2026-11-19")
    assert "Legacy amiibo" not in html
    assert "عناصر في السجل" in html


def test_disabled_community_source_means_unchecked_not_zero_demand():
    state = blank_state()
    state["source_health"] = {
        "community_placeholder": {"kind": "community", "status": "disabled"},
        "nintendo_jp": {"kind": "official", "status": "ok"},
    }
    assert demand_coverage(state) is False


def test_news_filter_avoids_digital_marketplace_and_duplicate_story():
    state = blank_state()
    state["documents"] = {
        "software": {
            "kind": "official", "source": "xbox",
            "title": "Marketplace Exclusive Flight Simulator DLC",
            "url": "https://news.xbox.com/entry1",
            "published_at": "2026-11-18T00:00:00+00:00",
        },
        "collector": {
            "kind": "official", "source": "nintendo",
            "title": "New collectible amiibo merchandise preorder",
            "url": "https://www.nintendo.co.jp/entry2",
            "published_at": "2026-11-18T00:00:00+00:00",
        },
    }
    chosen = select_news(state, "2026-11-19", set(), limit=5)
    assert len(chosen) == 1
    assert "amiibo" in chosen[0]["title"]


def test_report_escapes_untrusted_article_titles():
    state = blank_state()
    doc = {
        "kind": "official", "source": "official",
        "url": "https://example.org/news",
        "title": "<img src=x onerror=evil()> Exclusive Collector Edition",
        "published_at": "2026-11-18T10:00:00+00:00",
    }
    state["documents"]["x"] = doc
    result = render(state, "2026-11-19")
    assert "&lt;img" in result
    assert '<img src=x onerror=evil()>' not in result
