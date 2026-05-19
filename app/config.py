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

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_NAME = os.getenv("SENDER_NAME", "Osalasi Company Limited")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

BULKSMS_API_URL = "https://www.bulksmsnigeria.com/api/v2/sms"
BULKSMS_API_TOKEN = os.getenv("BULKSMS_API_TOKEN")

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_EVENTS_URL = "https://api.brevo.com/v3/smtp/statistics/events"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
