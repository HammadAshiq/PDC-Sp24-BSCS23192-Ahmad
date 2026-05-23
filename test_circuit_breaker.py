import pytest
from fastapi.testclient import TestClient
from main import app, cb, CircuitBreaker

client = TestClient(app)


def reset_cb():
    """Helper to reset circuit breaker before each test."""
    cb.state = CircuitBreaker.CLOSED
    cb.failure_count = 0
    cb.last_failure_time = None


# ── Test 1: Custom header is always present ──────────────────────────────────
def test_student_id_header_present():
    reset_cb()
    r = client.get("/")
    assert "x-student-id" in r.headers
    assert r.headers["x-student-id"] == "BSCS23192"


# ── Test 2: LLM works normally when circuit is CLOSED ────────────────────────
def test_llm_succeeds_when_circuit_closed():
    reset_cb()
    import main
    main.LLM_IS_DOWN = False
    r = client.get("/llm/suggest?prompt=photosynthesis")
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["circuit_state"] == "CLOSED"


# ── Test 3: Circuit opens after 3 failures ───────────────────────────────────
def test_circuit_opens_after_threshold_failures():
    reset_cb()
    import main
    main.LLM_IS_DOWN = True

    # First 3 calls should fail with 502 (LLM error)
    for i in range(3):
        r = client.get("/llm/suggest")
        assert r.status_code == 502, f"Expected 502 on call {i+1}"

    # Circuit should now be OPEN
    assert cb.state == CircuitBreaker.OPEN


# ── Test 4: Circuit open → fallback response (no LLM called) ─────────────────
def test_fallback_response_when_circuit_open():
    reset_cb()
    import main
    main.LLM_IS_DOWN = True

    # Trip the circuit
    for _ in range(3):
        client.get("/llm/suggest")

    # Now request should get fallback without hitting LLM
    r = client.get("/llm/suggest")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "degraded"
    assert data["circuit_state"] == "OPEN"
    assert "temporarily unavailable" in data["response"]


# ── Test 5: Header present on error responses too ────────────────────────────
def test_student_id_header_on_error_response():
    reset_cb()
    import main
    main.LLM_IS_DOWN = True

    for _ in range(3):
        client.get("/llm/suggest")

    r = client.get("/llm/suggest")
    assert r.headers["x-student-id"] == "BSCS23192"


# ── Test 6: Manual reset endpoint works ──────────────────────────────────────
def test_manual_reset():
    reset_cb()
    import main
    main.LLM_IS_DOWN = True
    for _ in range(3):
        client.get("/llm/suggest")

    assert cb.state == CircuitBreaker.OPEN

    r = client.post("/circuit/reset")
    assert r.status_code == 200
    assert cb.state == CircuitBreaker.CLOSED