BSCS23192 — [Rana Hammad Ahmad]

# PDC-Sp24-BSCS23192-[Ahmad]

Circuit Breaker implementation for the StudySync LLM fault tolerance problem.

## How to run

1. Clone this repo
2. Create and activate a virtual environment:
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
3. Install dependencies:
   pip install fastapi uvicorn httpx pytest pytest-asyncio
4. Start the server:
   uvicorn main:app --reload
5. Open http://localhost:8000/docs to explore the API

## How to run tests

pytest test_circuit_breaker.py -v

## Demo scenario

- With LLM_IS_DOWN = False in main.py: /llm/suggest returns normal responses
- With LLM_IS_DOWN = True: after 3 calls the circuit opens and returns a fallback
- Use POST /circuit/reset to reset between demos