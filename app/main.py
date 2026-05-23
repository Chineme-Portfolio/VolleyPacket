import os
import logging
import sys
from contextlib import asynccontextmanager

# Production logging — Railway captures stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import templates, upload, generate, jobs
from app.routes import auth, email_settings, billing, ai_email
from app.database import init_db
from app.middleware import RequestLoggingMiddleware
from app import config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure local working directories exist (even in containers)
    for folder in (config.UPLOAD_FOLDER, config.OUTPUT_FOLDER, config.TEMPLATE_FOLDER,
                   config.LOG_FOLDER, config.DATA_FOLDER, config.JOBS_FOLDER):
        os.makedirs(folder, exist_ok=True)

    init_db()
    logger.info("Database initialized — jobs load on demand from DB")

    yield


app = FastAPI(title="VolleyPacket", version="2.0.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "app": "VolleyPacket", "version": "2.1.0"}


@app.get("/debug/db")
def debug_db():
    """Temporary diagnostic endpoint — check DB table state."""
    from app.database import get_session
    from sqlalchemy import text
    session = get_session()
    try:
        # Check which tables exist
        result = session.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        tables = [row[0] for row in result]
        return {"tables": tables, "has_jobs": "jobs" in tables}
    except Exception as e:
        # SQLite fallback
        try:
            result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            return {"tables": tables, "has_jobs": "jobs" in tables, "db": "sqlite"}
        except Exception as e2:
            return {"error": str(e), "sqlite_error": str(e2)}
    finally:
        session.close()


# Public
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Protected
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(upload.router, prefix="/upload", tags=["Upload & Parse"])
app.include_router(generate.router, prefix="/generate", tags=["AI Generate"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(email_settings.router, prefix="/email-settings", tags=["Email Settings"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(ai_email.router, prefix="/ai-email", tags=["AI Email"])
