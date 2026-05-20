import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import templates, upload, generate, jobs
from app.routes import auth, email_settings, billing, ai_email
from app.services.jobs import load_all_jobs
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_all_jobs()
    yield


app = FastAPI(title="VolleyPacket", version="2.0.0", lifespan=lifespan)

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
    return {"status": "ok", "app": "VolleyPacket", "version": "2.0.0"}


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
