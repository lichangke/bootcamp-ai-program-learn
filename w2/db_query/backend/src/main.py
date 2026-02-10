from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.storage.sqlite_store import init_storage

app = FastAPI(title="DB Query Tool API", version="0.1.0")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

