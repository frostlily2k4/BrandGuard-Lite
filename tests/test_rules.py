import json

from brandguard.rules import default_rules, load_rules, normalize_rules, save_rules


def test_normalize_cleans_blanks_duplicates_and_nan():
    rules = normalize_rules({
        "brand_name": "  Acme  ",
        "preferred_terms": ["Easy to use", "easy to use", "", None],
        "banned_terms": [{"term": "Cheap", "replacement": None}, {"term": "cheap", "replacement": "x"},
                         {"term": None, "replacement": "y"}, "hype"],
        "approved_facts": [{"fact": "", "source": "s"}, {"fact": "Fact A", "source": float("nan")}],
    })
    assert rules["brand_name"] == "Acme"
    assert rules["preferred_terms"] == ["Easy to use"]
    assert rules["banned_terms"] == [{"term": "Cheap", "replacement": ""}, {"term": "hype", "replacement": ""}]
    assert rules["approved_facts"] == [{"fact": "Fact A", "source": ""}]


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "rules.json"
    saved = save_rules({"brand_name": "Test", "banned_terms": [{"term": "bad", "replacement": "good"}]}, path)
    assert load_rules(path) == saved
    assert json.loads(path.read_text(encoding="utf-8"))["brand_name"] == "Test"


def test_missing_or_broken_file_falls_back_to_defaults(tmp_path):
    assert load_rules(tmp_path / "missing.json") == default_rules()
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert load_rules(broken) == default_rules()
