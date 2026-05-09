"""
FastAPI Web Backend
REST API + WebSocket ile canlı test progress
"""
from __future__ import annotations
import asyncio
import json
import uuid
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from agents.orchestrator import run_orchestration, OrchestrationResult
from integrations.github_client import GitHubClient, load_manual_diff
from config.settings import settings

app = FastAPI(
    title="PR Test Automation API",
    description="AutoGen + Playwright MCP tabanlı PR test otomasyon sistemi",
    version="1.0.0",
)

# Aktif test çalışmalarını bellekte tut
_runs: dict[str, dict] = {}


# ── Request/Response modelleri ────────────────────────────────────────────────

class PRRunRequest(BaseModel):
    pr_url: Optional[str] = None
    diff_content: Optional[str] = None
    test_types: list[str] = ["e2e", "api", "unit"]
    base_url: Optional[str] = None
    project_root: str = "."


class PRRunResponse(BaseModel):
    run_id: str
    message: str


# ── API Rotaları ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/runs", response_model=PRRunResponse)
async def start_run(req: PRRunRequest):
    """PR analizi ve test çalıştırmasını başlatır."""
    if not req.pr_url and not req.diff_content:
        raise HTTPException(status_code=400, detail="pr_url veya diff_content gerekli")

    run_id = str(uuid.uuid4())[:8]
    _runs[run_id] = {"status": "pending", "stages": [], "result": None}

    # Arka planda çalıştır
    asyncio.create_task(_execute_run(run_id, req))

    return PRRunResponse(run_id=run_id, message="Test çalışması başlatıldı")


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Çalışma bulunamadı")
    run = _runs[run_id]
    result: OrchestrationResult | None = run.get("result")
    return {
        "run_id": run_id,
        "status": run["status"],
        "stages": run["stages"],
        "report": result.final_report if result and result.success else None,
        "generated_files": result.generated_files if result else [],
        "saved_reports": result.saved_reports if result else {},
        "error": result.error if result else "",
    }


@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str, fmt: str = "json"):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Çalışma bulunamadı")
    result: OrchestrationResult | None = _runs[run_id].get("result")
    if not result or not result.success:
        raise HTTPException(status_code=400, detail="Tamamlanmış rapor yok")

    if fmt == "html" and "html" in result.saved_reports:
        return FileResponse(result.saved_reports["html"], media_type="text/html")
    return JSONResponse(content=result.final_report)


@app.websocket("/ws/runs/{run_id}")
async def websocket_progress(websocket: WebSocket, run_id: str):
    """Canlı test progress bildirimleri."""
    await websocket.accept()
    try:
        last_idx = 0
        while True:
            run = _runs.get(run_id, {})
            stages = run.get("stages", [])
            # Yeni stage'leri gönder
            for stage in stages[last_idx:]:
                await websocket.send_json(stage)
                last_idx += 1
            # Bitişte kapat
            if run.get("status") in ("completed", "failed"):
                await websocket.send_json({"stage": "done", "status": run["status"]})
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# ── Statik dosyalar (Web UI) ──────────────────────────────────────────────────
import os
_web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
if os.path.isdir(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="web")


# ── İç yardımcı fonksiyon ────────────────────────────────────────────────────

async def _execute_run(run_id: str, req: PRRunRequest):
    _runs[run_id]["status"] = "running"

    async def progress_cb(stage: str, message: str):
        _runs[run_id]["stages"].append({"stage": stage, "message": message})

    try:
        if req.pr_url:
            client = GitHubClient()
            pr = client.get_pr_info(req.pr_url)
        else:
            # diff_content'i geçici dosyaya yaz
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
                f.write(req.diff_content)
                tmp_path = f.name
            pr = load_manual_diff(tmp_path)
            os.unlink(tmp_path)

        if req.base_url:
            settings.playwright_base_url = req.base_url

        result = await run_orchestration(pr, req.test_types, req.project_root, progress_cb)
        _runs[run_id]["result"] = result
        _runs[run_id]["status"] = "completed" if result.success else "failed"
    except Exception as exc:
        _runs[run_id]["status"] = "failed"
        _runs[run_id]["stages"].append({"stage": "error", "message": str(exc)})
