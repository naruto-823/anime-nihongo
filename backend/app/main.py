from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import SessionLocal, init_app_db
from app.grammar_loader import load_grammar_seed


def create_app() -> FastAPI:
    app = FastAPI(title="追番日语 API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_app_db()
        db = SessionLocal()
        try:
            load_grammar_seed(db)
        finally:
            db.close()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    from app.api import episodes, series
    app.include_router(series.router)
    app.include_router(episodes.router)

    return app


app = create_app()
