import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_FOLDER = str(BASE_DIR / "uploads")
OUTPUT_FOLDER = str(BASE_DIR / "output")
TEMPLATE_FOLDER = str(BASE_DIR / "templates")
LOG_FOLDER = str(BASE_DIR / "logs")
DATA_FOLDER = str(BASE_DIR / "data")
JOBS_FOLDER = str(BASE_DIR / "data" / "jobs")
DB_PATH = str(BASE_DIR / "data" / "volleypacket.db")

# Auth
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required. Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Encryption key for stored credentials (Fernet key, 32 bytes base64-encoded)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# APIs
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# AI model tiering — change model ids here only (see context/architecture.md
# "AI Generation & Model Tiering"). In-job template editing is the flagship,
# low-frequency output, so it runs on the top tier.
AI_MODEL_TEMPLATE_EDIT = os.getenv("AI_MODEL_TEMPLATE_EDIT", "claude-opus-4-8")
# Email + SMS drafting ("Ask Volley") — lower-stakes, higher-frequency than templates,
# and the user edits the draft anyway, so this is the cheaper tier (swappable here).
AI_MODEL_EMAIL_SMS = os.getenv("AI_MODEL_EMAIL_SMS", "claude-sonnet-4-6")

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_CLASSIC = os.getenv("STRIPE_PRICE_CLASSIC", "")  # Stripe Price ID for Classic tier
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")          # Stripe Price ID for Pro tier
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Storage — auto-detected from Railway env vars (BUCKET, ACCESS_KEY_ID, etc.)
# Override with STORAGE_BACKEND=local to force local filesystem
# See app/services/storage.py for full env var fallback chain

# Paystack (for Nigerian users)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_WEBHOOK_SECRET = os.getenv("PAYSTACK_WEBHOOK_SECRET")
PAYSTACK_PLAN_CLASSIC = os.getenv("PAYSTACK_PLAN_CLASSIC", "")  # Paystack plan_code for Classic
PAYSTACK_PLAN_PRO = os.getenv("PAYSTACK_PLAN_PRO", "")          # Paystack plan_code for Pro

# BulkSMS (Nigeria-focused SMS provider) — global env is the transition fallback when a
# user hasn't configured per-user SMS settings; a configured provider always wins.
BULKSMS_API_TOKEN = os.getenv("BULKSMS_API_TOKEN", "")
BULKSMS_API_URL = os.getenv("BULKSMS_API_URL", "https://www.bulksmsnigeria.com/api/v2/sms")
SMS_DEFAULT_SENDER = os.getenv("SMS_DEFAULT_SENDER", "Osalasi")  # sender_id for the env fallback
