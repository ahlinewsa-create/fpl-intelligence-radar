"""Regression cases from the 2026-11-20 Global Hunter report."""
from src.hunter.objects import extract_objects, english_entity_name


def test_dangling_article_phrases_are_not_products():
    for phrase in (
        "since that figure",
        "base to help her stand",
        "appear as a prize figure",
        "in Japan as prize figures",
        "Banpresto storefront like other mascots",
        "All Sanrio mascots",
    ):
        assert english_entity_name(phrase) == "", phrase


def test_valid_named_products_remain():
    text = (
        "Rebuild of Evangelion Asuka Figure Wears Her Cat Hat. "
        "The collector box includes Aurora Mascot figurine and "
        "Beacon Display stand. since that figure base to help her stand."
    )
    objects = extract_objects(text)
    names = [obj["name"] for obj in objects]
    assert any("Asuka Figure" in name for name in names), names
    assert any("Aurora Mascot figurine" in name for name in names), names
    assert any("Beacon Display stand" in name for name in names), names
    assert all("since that" not in name and "base to help" not in name for name in names)
    assert all(obj.get("source_span") for obj in objects)


def test_partial_clause_does_not_expand_into_market_search():
    assert extract_objects("The figure has a base to help her stand.") == []
