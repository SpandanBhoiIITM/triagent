"""
FastAPI app. ALL endpoints are plain `def` functions (synchronous).



Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""

import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from rq import Queue

from app import db
from app.cache import r as redis_conn, cache_get, cache_set, is_rate_limited
from app.ml.classifier import load_model, predict_category, predict_sentiment
from app.worker import analysis_job
from app.email_notify import notify_needs_review

app = FastAPI(title="Ticket Intelligence API")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Simple middleware: runs BEFORE and AFTER every request.
    Interview point: middleware wraps every endpoint without editing each
    one -- here it times the request and logs method, path, status, and
    duration. Same pattern is used for auth checks, CORS, error handling.

    Note: FastAPI middleware must be declared `async def` -- this is the
    ONE place FastAPI requires async, because middleware sits directly in
    the ASGI request chain. Every endpoint below stays a plain sync `def`.
    `await call_next(request)` just hands off to the next step in the
    chain (eventually your sync endpoint, run safely in a threadpool).
    """
    start = time.time()
    response = await call_next(request)    # runs the actual endpoint
    duration_ms = round((time.time() - start) * 1000, 1)
    print(f"{request.method} {request.url.path} -> "
          f"{response.status_code} ({duration_ms}ms)")
    return response

queue = Queue("analysis", connection=redis_conn)  # RQ task queue on Redis

# load ML model once at startup, reuse for every request
model = load_model()


class TicketIn(BaseModel):
    subject: str
    body: str


class AnalysisIn(BaseModel):
    query: str


@app.post("/tickets")
def create_ticket(ticket: TicketIn, request: Request):
    # rate limit by client IP: 20 requests per minute
    client_ip = request.client.host
    if is_rate_limited(client_ip, limit=20, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests")

    category = predict_category(model, ticket.subject, ticket.body)
    sentiment = predict_sentiment(ticket.subject, ticket.body)
    ticket_id, status = db.insert_ticket(ticket.subject, ticket.body,
                                         category, sentiment)
    invalidate_ticket_cache()
    if status == "needs_review":
        notify_needs_review(ticket_id, ticket.subject, sentiment)
    return {"id": ticket_id, "category": category,
            "sentiment": sentiment, "status": status}


@app.get("/tickets")
def list_tickets(category: str = None):
    # cache-aside: check Redis first, fall back to MySQL
    cache_key = f"tickets:{category or 'all'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return {"source": "cache", "tickets": cached}

    tickets = db.get_tickets(category=category)
    for t in tickets:  # timestamps are not JSON serializable
        t["created_at"] = str(t["created_at"])
        t["resolved_at"] = str(t.get("resolved_at") or "")
    cache_set(cache_key, tickets, ttl=60)
    return {"source": "database", "tickets": tickets}


@app.post("/analyze")
def start_analysis(body: AnalysisIn):
    """
    The async-job pattern WITHOUT async code:
    1. create a job row in MySQL
    2. push the job onto the Redis queue (RQ)
    3. return the job_id immediately -- client polls /jobs/{id}
    The heavy agent work happens in a separate worker process.
    """
    job_id = str(uuid.uuid4())
    db.create_job(job_id, body.query)
    queue.enqueue(analysis_job, job_id, body.query, job_timeout=300)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    result = {"job_id": job_id, "status": job["status"]}
    if job["status"] == "done":
        report = db.get_report(job_id)
        if report:
            result["report"] = report["content"]
    return result


def invalidate_ticket_cache():
    """
    Write-through invalidation: whenever tickets change, drop the cached
    lists so the next read comes fresh from MySQL.
    Interview point: this is how you handle cache staleness on writes.
    """
    for key in redis_conn.scan_iter("tickets:*"):
        redis_conn.delete(key)


@app.get("/search")
def search(q: str):
    tickets = db.search_tickets(q)
    for t in tickets:
        t["created_at"] = str(t["created_at"])
        t["resolved_at"] = str(t.get("resolved_at") or "")
    return {"tickets": tickets}


@app.get("/review")
def review_queue():
    tickets = db.get_review_queue()
    for t in tickets:
        t["created_at"] = str(t["created_at"])
        t["resolved_at"] = str(t.get("resolved_at") or "")
    return {"tickets": tickets}


@app.post("/tickets/{ticket_id}/resolve")
def resolve(ticket_id: int):
    ok = db.resolve_ticket(ticket_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Ticket not found")
    invalidate_ticket_cache()
    return {"id": ticket_id, "status": "resolved"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup_cleanup():
    """Retention policy: delete resolved tickets older than 7 days."""
    try:
        deleted = db.cleanup_resolved(days=7)
        print(f"Retention cleanup: deleted {deleted} old resolved tickets")
    except Exception as e:
        print(f"Cleanup skipped: {e}")


@app.get("/")
def serve_ui():
    """Serve the frontend from the same origin -- no CORS needed."""
    return FileResponse("static/index.html")
