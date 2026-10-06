"""FastAPI app for the FinVerse dashboard.

    uvicorn api.server:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from . import presets, sentiment
from .jobs import JobManager, QueueFull, engine_version, list_runs, payload_path
from .schema import RunParams

manager: Optional[JobManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager
    # created here (not at import) so spawned worker processes, which
    # re-import this package, never start a second job thread
    manager = JobManager()
    yield


app = FastAPI(title="FinVerse dashboard API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    """400 with a readable message (instead of FastAPI's default 422 dump)."""
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        msgs.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return JSONResponse(status_code=400, content={"detail": "; ".join(msgs)})


@app.get("/api/health")
def health():
    return {"ok": True, "engine_version": engine_version(), "finbert_available": sentiment.available()}


@app.get("/api/news/presets")
def news_presets():
    return presets.presets()


@app.post("/api/simulations")
def start_simulation(params: RunParams):
    try:
        params.check_news_in_session()
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        job = manager.submit(params)
    except QueueFull as e:
        raise HTTPException(429, str(e))
    return {"run_id": job.run_id, "status": job.status}


@app.get("/api/simulations/{run_id}")
def simulation_status(run_id: str):
    job = manager.get(run_id)
    if job is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return job.view()


@app.delete("/api/simulations/{run_id}")
def cancel_simulation(run_id: str):
    """Cancel a queued run. A run already executing finishes in the background."""
    return {"cancelled": manager.cancel(run_id)}


@app.get("/api/simulations/{run_id}/data")
def simulation_data(run_id: str):
    path = payload_path(run_id)
    if not path.exists():
        raise HTTPException(404, f"no data for run {run_id} (not finished?)")
    return Response(content=path.read_bytes(), media_type="application/json")


@app.get("/api/runs")
def runs():
    return [
        {k: m[k] for k in ("run_id", "params", "created_at", "wall_time_s", "summary")}
        for m in list_runs()
    ]


class SentimentRequest(BaseModel):
    headline: str = Field(min_length=1, max_length=200)


@app.post("/api/sentiment")
def score_sentiment(req: SentimentRequest):
    try:
        return sentiment.score(req.headline)
    except sentiment.SentimentUnavailable as e:
        raise HTTPException(503, str(e))
