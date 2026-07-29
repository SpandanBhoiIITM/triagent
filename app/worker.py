"""
Background worker job. Run the worker with:

    rq worker analysis

RQ (Redis Queue) pulls jobs from Redis and runs this plain function in a
separate process. No async, no Celery complexity.


"""

from app import db
from app.agents.graph import run_analysis


def analysis_job(job_id, query):
    db.update_job_status(job_id, "running")
    try:
        tickets = db.get_tickets(limit=500)
        if not tickets:
            raise ValueError("No tickets in database to analyze")

        report = run_analysis(query, tickets)

        db.save_report(job_id, report)
        db.update_job_status(job_id, "done")
        db.cleanup_resolved(days=7)   # retention policy piggybacked here
        return "ok"
    except Exception as e:
        db.update_job_status(job_id, "failed")
        print(f"Job {job_id} failed: {e}")
        raise
