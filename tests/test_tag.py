import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from common import normalize, read_json
from tag import GeminiAPIError, call_gemini, tag_menu, validate_tag


def test_once_per_normalized_name_and_cache_survives_rerun(tmp_path, make_dish):
    d, t = make_dish("Gemüsecurry")
    calls = []
    def caller(dish, model, key):
        calls.append(dish["name"])
        return t
    path = tmp_path / "cache.json"
    menu = {"dishes": [d, {**d, "name": " GEMÜSECURRY "}]}
    tag_menu(menu, path, "gemini-3.8-flash", "test-key", caller)
    tag_menu(menu, path, "gemini-3.8-flash", None, caller)
    assert calls == ["Gemüsecurry"]
    assert read_json(path) == {normalize(d["name"]): t}


def test_retry_once_and_persist_success_before_next_failure(tmp_path, make_dish):
    d, t = make_dish()
    responses = iter([{"invalid": True}, t])
    path = tmp_path / "cache.json"
    calls = []
    def retry(*args):
        calls.append(1)
        return next(responses)
    tag_menu({"dishes": [d]}, path, "gemini-3.8-flash", "test", retry)
    assert len(calls) == 2
    def invalid(*args):
        calls.append(1)
        return {}
    with pytest.raises(RuntimeError, match="2 attempts"):
        tag_menu({"dishes": [d, {**d, "name": "Other dish"}]}, path, "gemini-3.8-flash", "test", invalid)
    assert len(calls) == 4
    assert read_json(path)[normalize(d["name"])] == t


@pytest.mark.parametrize("field,value", [("kcal_per_100g", -1), ("protein_per_100g", float('nan')),
    ("protein_per_100g", True), ("carbs_per_100g", 150), ("texture", "crunchy"), ("role", "main+side"),
    ("is_per_piece", "false"), ("piece_weight_g", 150), ("typical_portion_g", {"min": 300, "max": 100})])
def test_validation_rejects_bad_values(field, value, make_dish):
    d, t = make_dish()
    t[field] = value
    with pytest.raises(ValueError):
        validate_tag(t)


def test_missing_key_cannot_invent_tags(tmp_path, make_dish):
    d, t = make_dish()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        tag_menu({"dishes": [d]}, tmp_path / "cache.json", "gemini-3.8-flash")
    assert not (tmp_path / "cache.json").exists()
    assert tag_menu({"dishes": []}, tmp_path / "cache.json", "gemini-3.8-flash") == {}


@pytest.mark.parametrize("name", ["Schnitzel (1 Stück) mit Sauce", "Seelachsfilet (1Stück)"])
def test_explicit_single_piece_cannot_be_tagged_as_scoops(name, make_dish, monkeypatch):
    dish, tag = make_dish(name)
    with pytest.raises(ValueError, match="single-piece"):
        validate_tag(tag, name=name)
    tag.update(is_per_piece=True, piece_weight_g=200)
    assert validate_tag(tag, name=name) == tag
    requests = []
    def generate(prompt, payload, schema, model, key):
        requests.append(schema)
        return tag
    monkeypatch.setattr("tag.generate_json", generate)
    assert call_gemini(dish, "test-model", "test-key") == tag
    assert requests[0]["properties"]["is_per_piece"]["enum"] == [True]


def test_explicit_single_piece_rejects_bad_cached_tag(tmp_path, make_dish):
    dish, tag = make_dish("Schnitzel (1 Stück)")
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({normalize(dish["name"]): tag}))
    with pytest.raises(ValueError, match="single-piece"):
        tag_menu({"dishes": [dish]}, path, "test-model")


def test_gemini_request_schema_header_and_response(monkeypatch, make_dish):
    """Check the real adapter contract without a network call or secret."""
    d, t = make_dish()
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "private thought", "thought": True}, {"text": json.dumps(t)}]}}]}).encode()
    def fake_urlopen(request, timeout):
        requests.append(request)
        return Response()
    monkeypatch.setattr("tag.urlopen", fake_urlopen)
    assert call_gemini(d, "gemini-3.8-flash", "test-secret") == t
    request = requests[0]
    assert request.full_url.endswith('/gemini-3.8-flash:generateContent')
    assert "test-secret" not in request.full_url
    assert request.get_header("X-goog-api-key") == "test-secret"
    body = json.loads(request.data)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False


def test_gemini_error_explains_service_failure_without_leaking_key(monkeypatch, make_dish):
    d, t = make_dish()
    def overloaded(request, timeout):
        body = json.dumps({"error": {"message": "Model overloaded; test-secret"}}).encode()
        raise HTTPError(request.full_url, 503, "Service Unavailable", {}, BytesIO(body))
    monkeypatch.setattr("tag.urlopen", overloaded)
    with pytest.raises(GeminiAPIError, match="Gemini HTTP 503") as error:
        call_gemini(d, "gemini-3.8-flash", "test-secret")
    assert error.value.status_code == 503
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize("overload_count", [2, 9])
@pytest.mark.parametrize("failure", [GeminiAPIError(503, "High demand"), TimeoutError("Read timed out"), URLError(TimeoutError("Connection timed out"))], ids=["503", "timeout", "wrapped-timeout"])
def test_service_failures_wait_thirty_seconds_then_cache_success(tmp_path, make_dish, monkeypatch, overload_count, failure):
    d, t = make_dish()
    calls, waits = [], []
    monkeypatch.setattr("tag.time.sleep", waits.append)
    def caller(*args):
        calls.append(1)
        if len(calls) <= overload_count:
            raise failure
        return t
    path = tmp_path / "cache.json"
    tag_menu({"dishes": [d]}, path, "gemini-3.8-flash", "test-key", caller)
    assert len(calls) == overload_count + 1
    assert waits == [30] * overload_count
    assert read_json(path) == {normalize(d["name"]): t}
    tag_menu({"dishes": [d]}, path, "gemini-3.8-flash", None, caller)
    assert len(calls) == overload_count + 1 # successful tags are never requested again


@pytest.mark.parametrize("failure", [GeminiAPIError(503, "High demand"), TimeoutError("Read timed out"), URLError(TimeoutError("Connection timed out"))], ids=["503", "timeout", "wrapped-timeout"])
def test_service_failures_stop_after_ten_total_attempts_without_final_sleep(tmp_path, make_dish, monkeypatch, failure):
    d, t = make_dish()
    calls, waits = [], []
    monkeypatch.setattr("tag.time.sleep", waits.append)
    def overloaded(*args):
        calls.append(1)
        raise failure
    path = tmp_path / "cache.json"
    with pytest.raises(RuntimeError, match="after 10 attempts"):
        tag_menu({"dishes": [d]}, path, "gemini-3.8-flash", "test-key", overloaded)
    assert len(calls) == 10
    assert waits == [30] * 9
    assert not path.exists()


@pytest.mark.parametrize("error", [GeminiAPIError(429, "Quota"), GeminiAPIError(400, "Bad request"), ValueError("Invalid JSON")])
def test_other_failures_keep_original_single_retry(tmp_path, make_dish, monkeypatch, error):
    d, t = make_dish()
    calls, waits = [], []
    monkeypatch.setattr("tag.time.sleep", waits.append)
    def failing(*args):
        calls.append(1)
        raise error
    with pytest.raises(RuntimeError, match="after 2 attempts"):
        tag_menu({"dishes": [d]}, tmp_path / "cache.json", "gemini-3.8-flash", "test-key", failing)
    assert len(calls) == 2
    assert waits == [1]


def test_mixed_failures_preserve_single_validation_retry(tmp_path, make_dish, monkeypatch):
    d, t = make_dish()
    errors = [ValueError("Invalid JSON"), GeminiAPIError(503, "High demand"), ValueError("Still invalid")]
    waits = []
    monkeypatch.setattr("tag.time.sleep", waits.append)
    def failing(*args):
        raise errors.pop(0)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        tag_menu({"dishes": [d]}, tmp_path / "cache.json", "gemini-3.8-flash", "test-key", failing)
    assert not errors
    assert waits == [1, 30]


def test_alternating_503_and_timeout_share_ten_attempt_limit(tmp_path, make_dish, monkeypatch):
    d, t = make_dish()
    calls, waits = [], []
    monkeypatch.setattr("tag.time.sleep", waits.append)
    def failing(*args):
        calls.append(1)
        if len(calls) % 2:
            raise GeminiAPIError(503, "High demand")
        raise TimeoutError("Read timed out")
    with pytest.raises(RuntimeError, match="after 10 attempts"):
        tag_menu({"dishes": [d]}, tmp_path / "cache.json", "gemini-3.8-flash", "test-key", failing)
    assert len(calls) == 10
    assert waits == [30] * 9
