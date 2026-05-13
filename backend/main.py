from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import categories, fixed_expenses, health, manual_expenses, rules, statements_v2
from app.core.logging import configure_logging
from app.core.request_logging import RequestLoggingMiddleware


configure_logging()

app = FastAPI(title="Family Budget API", version="0.1.0")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(statements_v2.router, prefix="/statements", tags=["statements"])
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(fixed_expenses.router)
app.include_router(manual_expenses.router)
