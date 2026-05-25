from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    from app.api import (
        conversation, episodes, grammar, progress, series, srs, study, tts,
    )
    for module in (series, episodes, study, srs, grammar, conversation, progress, tts):
        app.include_router(module.router)

    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        # 静态资源直挂；其他所有非 /api 路径都回退到 index.html，
        # 由前端 React Router 接管，避免刷新子页面被后端 404。
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        index_html = frontend_dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(str(index_html))

    return app


app = create_app()
