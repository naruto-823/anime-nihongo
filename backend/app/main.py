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

    from app.api import conversation, episodes, grammar, series, srs, study
    for module in (series, episodes, study, srs, grammar, conversation):
        app.include_router(module.router)

    return app


app = create_app()
