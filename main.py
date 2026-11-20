import sys
import logging
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from database.session import init_db
from routes.health import router as health_router
from routes.automation import router as automation_router

# Configure Structured Logging
log_file = settings.LOGS_DIR / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EmailAutomation")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database tables on startup."""
    logger.info("Initializing application and database tables...")
    await init_db()
    logger.info(f"{settings.APP_NAME} started on http://{settings.HOST}:{settings.PORT}")
    yield
    logger.info("Application shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Assisted Google/Gmail Account Registration and Login Workflow Automation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup for local interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(automation_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
# https://accounts.google.com/signup