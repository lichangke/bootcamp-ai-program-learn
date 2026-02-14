from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.dbs import router as dbs_router
from src.api.v1.query import router as query_router
from src.services.llm_service import LlmService
from src.storage.sqlite_store import init_storage

app = FastAPI(title="DB Query Tool API", version="0.1.0")
llm_service = LlmService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_storage()


app.include_router(dbs_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/llm")
def health_llm() -> dict[str, str | bool | int]:
    return llm_service.health_probe()
