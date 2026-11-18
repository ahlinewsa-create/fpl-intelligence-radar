from src.hunter.objects import extract_objects, detect_demand, plain_text


def test_multiple_objects_from_collector_box():
    text = (
        "The Limited Edition includes Aurora Mascot figurine, "
        "Lunar Crest badge and Beacon Display stand."
    )
    result = extract_objects(text)
    assert len(result) >= 2
    assert all(0 <= entry["extraction_confidence"] < 0.8 for entry in result)


def test_strip_untrusted_script_markup():
    assert plain_text("<script>malicious</script><p>Collector statue</p>") == "Collector statue"


def test_silent_demand_categories():
    result = detect_demand("I only want the figure. Is it sold separately? Too expensive!")
    assert "separate_purchase" in result
    assert "price_objection" in result


def test_popularity_is_not_purchase_intent():
    assert detect_demand("Amazing trailer! Millions of likes!") == []
