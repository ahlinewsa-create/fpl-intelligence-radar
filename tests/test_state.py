from src.hunter.state import blank_state, load_state, save_state, stable_id


def test_stable_identity():
    assert stable_id("Foo", " Bar ") == stable_id("foo", "bar")
    assert stable_id("foo", "baz") != stable_id("foo", "bar")


def test_ledger_persists_across_runs(tmp_path):
    path = tmp_path / "state.json"
    data = blank_state()
    data["opportunities"]["example"] = {"name": "Collector Mascot"}
    save_state(data, path)
    assert load_state(path)["opportunities"]["example"]["name"] == "Collector Mascot"


def test_missing_ledger_is_not_error(tmp_path):
    state = load_state(tmp_path / "missing.json")
    assert state["opportunities"] == {}
