from src.hunter.article import allowed_url, article_image, article_text
from src.hunter.objects import extract_objects


def test_source_host_allowlist_does_not_allow_arbitrary_hosts():
    hosts = ["www.nintendo.com", "www.nintendo.co.jp"]
    assert allowed_url("https://www.nintendo.com/jp/topics/article/a", hosts)
    assert not allowed_url("http://www.nintendo.com/jp/news", hosts)
    assert not allowed_url("https://example.com/", hosts)
    assert not allowed_url("https://www.nintendo.com.attacker.test/news", hosts)
    assert not allowed_url("https://localhost/private", hosts)
    assert not allowed_url("https://127.0.0.1/secret", hosts)
    assert not allowed_url("https://www.nintendo.com:abc/news", hosts)


def test_full_article_extraction_and_image_from_html():
    html = """
    <html><head><meta property="og:image" content="/media/collector.webp"></head>
    <body><nav>Skip</nav><article><h1>Collector announcement</h1>
    <p>The box includes Aurora Mascot figurine and Lunar Crest badge.
    This fictional sample is enough to illustrate that the collector bundle
    contains more than a generic package name.</p></article></body></html>
    """
    extracted = article_text(html)
    assert "Aurora Mascot figurine" in extracted
    assert "Skip" not in extracted
    assert article_image(html, "https://www.nintendo.com/jp/news") == (
        "https://www.nintendo.com/media/collector.webp"
    )


def test_japanese_named_amiibo_is_a_source_backed_candidate():
    text = '「ソードカービィ&ドラグーン」「ノワールデデデ&ハイドラ」のamiiboは本日発売。'
    results = extract_objects(text)
    assert any("ソードカービィ" in x["name"] for x in results)
    assert all(0 < x["extraction_confidence"] < 1 for x in results)
