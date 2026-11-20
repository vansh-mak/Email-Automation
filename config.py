import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EmailAutomation"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False

    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"

    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'app.db'}"

    # Fernet encryption key for credentials at rest.
    # If not set in environment, a key is auto-generated and stored in data/secret.key
    ENCRYPTION_KEY: str = ""

    # Browser automation settings
    HEADLESS: bool = False  # Headed by default for interactive desktop use
    BROWSER_TIMEOUT_MS: int = 30000

    # Target URLs
    GOOGLE_SIGNUP_URL: str = "https://accounts.google.com/signup"
    GOOGLE_LOGIN_URL: str = "https://accounts.google.com/signin"

    # Local Mock URLs for automated testing
    MOCK_SIGNUP_URL: str = "http://127.0.0.1:8001/signup"
    MOCK_LOGIN_URL: str = "http://127.0.0.1:8001/login"

settings = Settings()

# Ensure runtime directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)

# Initialize or load encryption key
key_file = settings.DATA_DIR / "secret.key"
if not settings.ENCRYPTION_KEY:
    if key_file.exists():
        settings.ENCRYPTION_KEY = key_file.read_text(encoding="utf-8").strip()
    else:
        generated_key = Fernet.generate_key().decode("utf-8")
        key_file.write_text(generated_key, encoding="utf-8")
        settings.ENCRYPTION_KEY = generated_key
