from src.hunter.market import classify_match, scan


def test_cults_name_matching_is_only_candidate():
    assert classify_match("Aurora Mascot", "Aurora Mascot STL model") == "exact_name_candidate"
    assert classify_match("Aurora Mascot", "Generic dragon") == "irrelevant"


def test_no_api_credentials_is_not_zero_competitors(monkeypatch):
    monkeypatch.delenv("CULTS_USERNAME", raising=False)
    monkeypatch.delenv("CULTS_API_KEY", raising=False)
    result = scan("Aurora Mascot")
    assert result["status"] == "not_checked"
    assert "exact_name_candidates" not in result
