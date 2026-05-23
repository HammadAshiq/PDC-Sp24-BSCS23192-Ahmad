import time
import random
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sympy import false

app = FastAPI()

# ─────────────────────────────────────────
# Custom Middleware: X-Student-ID header
# (REQUIRED — missing this = zero for Part 3)
# ─────────────────────────────────────────
@app.middleware("http")
async def add_student_id_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Student-ID"] = "BSCS23192"
    return response


# ─────────────────────────────────────────
# Circuit Breaker Implementation
# ─────────────────────────────────────────

class CircuitBreaker:
    """
    Three states:
      CLOSED     → normal, requests pass through
      OPEN       → tripped, requests fail immediately with fallback
      HALF_OPEN  → one test request allowed to check if LLM recovered
    """
    
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold=3, recovery_timeout=15):
        self.state             = self.CLOSED
        self.failure_count     = 0
        self.failure_threshold = failure_threshold   # trip after 3 failures
        self.recovery_timeout  = recovery_timeout    # wait 15s before trying again
        self.last_failure_time = None

    def call(self, fn, *args, **kwargs):
        """
        Wraps a function call with circuit breaker logic.
        Raises RuntimeError with a fallback message if the circuit is OPEN.
        """
        if self.state == self.OPEN:
            # Check if enough time has passed to try again
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                print("[CircuitBreaker] Trying HALF_OPEN...")
                self.state = self.HALF_OPEN
            else:
                raise RuntimeError("circuit_open")

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        self.failure_count = 0
        self.state = self.CLOSED
        print(f"[CircuitBreaker] Success. State → CLOSED")

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        print(f"[CircuitBreaker] Failure #{self.failure_count}")
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            print(f"[CircuitBreaker] Threshold reached. State → OPEN")


# Single shared circuit breaker instance
cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)


# ─────────────────────────────────────────
# Simulated LLM call (replace with real one)
# ─────────────────────────────────────────

# Toggle this to True to simulate the LLM being broken
LLM_IS_DOWN =False

def call_llm_api(prompt: str) -> str:
    """
    Simulates an external LLM API call.
    When LLM_IS_DOWN=True, raises an exception just like a real crashed API would.
    """
    if LLM_IS_DOWN:
        raise ConnectionError("LLM API is unreachable (simulated failure)")
    
    # Simulate a successful response
    return f"[LLM Response] Here is a study tip for: '{prompt}'"


# ─────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "StudySync API running", "student_id": "BSCS23192"}


@app.get("/llm/suggest")
def get_suggestion(prompt: str = "default study topic"):
    """
    Calls the LLM through the circuit breaker.
    Returns a fallback message if the circuit is OPEN.
    """
    try:
        result = cb.call(call_llm_api, prompt)
        return {
            "status":          "success",
            "circuit_state":   cb.state,
            "response":        result
        }
    except RuntimeError as e:
        if str(e) == "circuit_open":
            # Circuit is tripped — return degraded but friendly response
            return JSONResponse(
                status_code=503,
                content={
                    "status":        "degraded",
                    "circuit_state": cb.state,
                    "response":      "AI suggestions are temporarily unavailable. Please try again shortly.",
                    "failure_count": cb.failure_count
                }
            )
    except Exception:
        # LLM threw an error — circuit breaker already updated internally
        return JSONResponse(
            status_code=502,
            content={
                "status":          "error",
                "circuit_state":   cb.state,
                "response":        "LLM call failed. Retrying will be attempted automatically.",
                "failure_count":   cb.failure_count
            }
        )


@app.get("/circuit/status")
def circuit_status():
    """Shows the current state of the circuit breaker."""
    return {
        "state":           cb.state,
        "failure_count":   cb.failure_count,
        "threshold":       cb.failure_threshold,
        "recovery_timeout": cb.recovery_timeout
    }


@app.post("/circuit/reset")
def reset_circuit():
    """Manually reset the circuit breaker (useful for demos)."""
    cb.state = CircuitBreaker.CLOSED
    cb.failure_count = 0
    cb.last_failure_time = None
    return {"message": "Circuit breaker reset to CLOSED"}