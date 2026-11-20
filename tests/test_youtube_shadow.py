"""YouTube shadow must be opt-in, bounded and never imply purchases."""
import httpx
from src.hunter.youtube import classify_comment, probe, update_youtube
from src.hunter.state import blank_state


def test_classify_only_direct_printing_interest():
    assert classify_comment("Where can I download the STL for this?") == "stl_request"
    assert classify_comment("I want to 3D print it!") == "print_interest"
    assert classify_comment("Amazing trailer with millions of views") is None


def test_youtube_disabled_without_opt_in(monkeypatch):
    monkeypatch.delenv("HUNTER_YOUTUBE_SHADOW", raising=False)
    state = blank_state()
    state["opportunities"]["x"] = {"name": "Aurora Mascot figurine"}
    assert update_youtube(state) == 0
    assert "youtube_probe" not in state["opportunities"]["x"]


def test_shadow_probe_counts_bounded_comments_not_sales():
    def reply(request):
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": [
                {"id": {"videoId": "12345678901"}, "snippet": {
                    "title": "Aurora Mascot model STL",
                    "publishedAt": "2026-11-20T00:00:00Z",
                }},
                {"id": {"videoId": "12345678902"}, "snippet": {
                    "title": "Unrelated airplane",
                }},
            ]})
        if request.url.path.endswith("/commentThreads"):
            return httpx.Response(200, json={"items": [
                {"snippet": {"topLevelComment": {"snippet": {
                    "textDisplay": "Where can I find the STL?",
                }}}},
                {"snippet": {"topLevelComment": {"snippet": {
                    "textDisplay": "Awesome video!",
                }}}},
            ]})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        result = probe("Aurora Mascot figurine", client, "dummy")
    assert result["status"] == "sampled"
    assert result["mode"] == "shadow"
    assert result["videos_sampled"] == 1
    assert result["comments_sampled"] == 2
    assert result["requests_found"] == 1
    assert "sales" not in result


def test_missing_key_records_unchecked_not_zero(monkeypatch):
    monkeypatch.setenv("HUNTER_YOUTUBE_SHADOW", "1")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    state = blank_state()
    assert update_youtube(state) == 0
    assert state["source_health"]["youtube_shadow"]["status"] == "not_configured"
