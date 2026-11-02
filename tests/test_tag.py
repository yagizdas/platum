import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from common import normalize, read_json
from tag import call_gemini, tag_menu, validate_tag


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
    with pytest.raises(RuntimeError, match="two attempts"):
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
    with pytest.raises(ValueError, match="Gemini HTTP 503") as error:
        call_gemini(d, "gemini-3.8-flash", "test-secret")
    assert "test-secret" not in str(error.value)
