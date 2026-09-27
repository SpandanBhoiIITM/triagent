# Triagent — AI Agent System for Support Ticket Triage

Support teams waste hours manually triaging tickets. Triagent automatically classifies incoming tickets with ML, routes risky ones to a human review queue, and uses a LangGraph multi-agent pipeline to generate grounded analysis reports on demand — behind a production-style backend with caching, rate limiting, and an async job queue.

## Architecture

<img src="docs/architecture.svg" alt="Triagent architecture: Web UI to FastAPI, Redis for cache and queue, MySQL for storage, RQ worker running a LangGraph retriever-analyst-critic pipeline with a retry loop" width="700"/>

The `/analyze` endpoint returns a `job_id` in milliseconds; the heavy agent work runs in a separate worker process, and the client polls `/jobs/{id}`. This is the classic async-job pattern, implemented almost entirely with plain synchronous Python functions.


## Setup (5 steps)

```bash
# 1. Start MySQL and Redis
docker compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Train the ML model (use a bigger Kaggle dataset for real scores)
python -m app.ml.classifier

# 4. Load sample data
python seed_data.py
# (existing installs only: python migrate.py  -- adds status columns)

# 5. Run everything (2 terminals)
python -m uvicorn app.main:app --reload
python -m rq.cli worker analysis --worker-class rq.worker.SimpleWorker
```
Open http://localhost:8001 — the web UI is served by FastAPI itself (same origin, no CORS needed). API docs: http://localhost:8001/docs

Windows notes (skip on Mac/Linux):

--worker-class rq.worker.SimpleWorker is required — RQ's default worker uses os.fork(), which doesn't exist on Windows.
Don't use --reload on uvicorn — its subprocess reloader can break local import shims (see xxhash.py below). Restart uvicorn manually after code changes instead.
If a package's compiled dependency gets blocked by a Windows security/antivirus policy (ImportError: DLL load failed ... Application Control policy has blocked this file), see xxhash.py in the project root — it's a pure-Python stand-in that avoids this exact issue for one of LangGraph's dependencies. Same technique works for other blocked native dependencies: write a small pure-Python module with the same name, place it in the project root, Python finds it before the installed (blocked) package.

Optional: export ANTHROPIC_API_KEY=... (or set on Windows) makes the Analyst agent write reports with Claude instead of the template. The system works fully without it.

Important: use a real dataset

data/sample_tickets.csv has only 25 rows — enough to run the system, far too small for a meaningful model 

Features beyond the core pipeline

Human-in-the-loop review. ML routes risky tickets to a human instead of full automation: negative-sentiment tickets always require review, and neutral billing tickets do too (money issues are risky even when the customer sounds calm). They wait in the Review queue tab until a human marks them resolved. Interview point: this is how ML systems are actually deployed — automate the easy 80%, keep humans on the high-risk slice.

Data retention policy. Resolved tickets are deleted 7 days after resolution (cleanup_resolved), so the database doesn't grow forever. Runs at API startup and piggybacked after each analysis job; in production it would run on a scheduler (cron / rq-scheduler).

Cache invalidation on writes. Creating or resolving a ticket deletes the cached ticket lists (invalidate_ticket_cache), so reads after a write are never stale. Interview point: cache-aside for reads + invalidate-on-write is the standard answer to "how do you keep the cache consistent?"

Search. /search?q= does SQL LIKE over subject and body. Upgrade path: full-text index (MySQL FULLTEXT) or embedding-based semantic search.


