"""
FastAPI integration — expose agentpipe as an HTTP API.

Usage:
    pip install fastapi uvicorn
    python -m examples.20_fastapi_integration

Then:
    curl "http://localhost:8000/ask?q=What+is+Python"
    curl "http://localhost:8000/cascade?q=Explain+recursion&profile=free-only"
"""

from fastapi import FastAPI
from pydantic import BaseModel

from agentpipe import Agent, CascadeResult, cascade


class AskRequest(BaseModel):
    q: str


class CascadeRequest(BaseModel):
    q: str
    profile: str = "free-only"


app = FastAPI(title="agentpipe API")


@app.get("/ask")
async def ask(q: str):
    agent = Agent("gemini-flash", timeout=30)
    try:
        text = await agent.generate(q)
        return {"answer": text, "model": agent.model}
    except Exception as e:
        return {"error": str(e), "model": agent.model}


@app.get("/cascade")
async def cascade_ask(q: str, profile: str = "free-only"):
    try:
        result: CascadeResult = await cascade(q, profile=profile, per_attempt_timeout=30)
        return {
            "answer": result.text,
            "model": result.successful_model,
            "provider": result.successful_provider,
            "attempts": result.attempt_count,
            "duration": result.total_duration_seconds,
            "cost": result.total_cost_usd,
        }
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
