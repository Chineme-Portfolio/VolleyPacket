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
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Encryption key for stored credentials (Fernet key, 32 bytes base64-encoded)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# APIs
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
