import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_API_ACCESS = _env_bool("LOG_API_ACCESS", True)
LOG_AI_CLASSIFICATION_DETAIL = _env_bool("LOG_AI_CLASSIFICATION_DETAIL", False)
LOG_FILE_ENABLED = _env_bool("LOG_FILE_ENABLED", True)
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/app.log").strip()
try:
    LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
except ValueError:
    LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
try:
    LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
except ValueError:
    LOG_FILE_BACKUP_COUNT = 5

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

try:
    AI_CLASSIFICATION_CONFIDENCE_THRESHOLD = float(
        os.getenv("AI_CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.7")
    )
except ValueError:
    AI_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7

try:
    AI_CONFIDENCE_REVIEW_THRESHOLD = float(
        os.getenv("AI_CONFIDENCE_REVIEW_THRESHOLD", "0.8")
    )
except ValueError:
    AI_CONFIDENCE_REVIEW_THRESHOLD = 0.8

# Supabase Auth 連携。dev / prod ともに別々の Supabase プロジェクトを使う。
# 既定は JWT Signing Keys（ES256 等）を SUPABASE_URL の JWKS で検証する。
# Legacy HS256 のみのプロジェクトでは SUPABASE_JWT_SECRET を追加で設定する。
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated").strip()
SUPABASE_JWT_ALGORITHMS_LEGACY = ("HS256",)
SUPABASE_JWT_ALGORITHMS_ASYMMETRIC = frozenset(
    alg.strip()
    for alg in os.getenv(
        "SUPABASE_JWT_ALGORITHMS_ASYMMETRIC",
        "ES256,RS256",
    ).split(",")
    if alg.strip()
)
