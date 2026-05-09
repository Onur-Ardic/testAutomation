"""
Orchestrator — Ana AutoGen orkestratörü
PR analiz → test planlama → test üretimi → test çalıştırma akışını yönetir.
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Awaitable

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from integrations.github_client import PRInfo
from integrations.project_detector import detect_project, ProjectContext
from agents.pr_analyzer import (
    build_pr_analyzer_agent,
    build_pr_analysis_message,
    parse_analysis_result,
)
from agents.test_planner import (
    build_test_planner_agent,
    build_planner_message,
    parse_plan_result,
)
from agents.test_generator import (
    build_test_generator_agent,
    build_generator_message,
    extract_and_write_tests,
)
from agents.test_runner import (
    build_test_runner_agent,
    run_tests,
    build_runner_message,
    parse_runner_result,
    save_report,
)
from config.settings import settings


ProgressCallback = Callable[[str, str], Awaitable[None]]


@dataclass
class OrchestrationResult:
    pr_number: int | str
    project_context: ProjectContext | None = None
    analysis: dict = field(default_factory=dict)
    test_plan: dict = field(default_factory=dict)
    generated_files: list[str] = field(default_factory=list)
    run_results: dict = field(default_factory=dict)
    final_report: dict = field(default_factory=dict)
    saved_reports: dict[str, str] = field(default_factory=dict)
    error: str = ""
    success: bool = False


async def _agent_respond(agent: AssistantAgent, message: str) -> str:
    """Tek bir agent'a mesaj gönderir ve yanıtını string olarak alır."""
    response = await agent.on_messages(
        [TextMessage(content=message, source="user")],
        cancellation_token=CancellationToken(),
    )
    return response.chat_message.content


async def run_orchestration(
    pr: PRInfo,
    test_types: list[str] | None = None,
    project_root: str = ".",
    progress_cb: ProgressCallback | None = None,
) -> OrchestrationResult:
    """
    Tam orkestrasyon akışını çalıştırır.
    progress_cb(stage, message) ile ilerleme bildirimi gönderir.
    """
    types = test_types or ["e2e", "api", "unit"]
    result = OrchestrationResult(pr_number=pr.number or "manual")

    async def emit(stage: str, msg: str):
        if progress_cb:
            await progress_cb(stage, msg)

    # ── 0. PROJE TESPİTİ ─────────────────────────────────────────────────────
    await emit("detect", f"Proje analiz ediliyor: {project_root}")
    proj_ctx = detect_project(project_root)
    result.project_context = proj_ctx
    await emit("detect", f"Tespit edildi: {proj_ctx.framework} / {proj_ctx.language}")

    # Base URL: settings'deki değer yoksa otomatik öner
    if settings.playwright_base_url == "http://localhost:3000":
        suggested = _suggest_base_url(proj_ctx)
        if suggested != settings.playwright_base_url:
            await emit("detect", f"Önerilen base URL: {suggested}")

    # ── 1. PR ANALİZ ─────────────────────────────────────────────────────────
    await emit("analyze", "PR analiz ediliyor...")
    try:
        analyzer = build_pr_analyzer_agent()
        raw = await _agent_respond(analyzer, build_pr_analysis_message(pr))
        result.analysis = parse_analysis_result(raw)
        await emit("analyze", f"Analiz tamamlandı. Risk: {result.analysis.get('risk_level','?')}")
    except Exception as exc:
        result.error = f"PR analizi başarısız: {exc}"
        return result

    # ── 2. TEST PLANLAMA ──────────────────────────────────────────────────────
    await emit("plan", "Test senaryoları planlanıyor...")
    try:
        planner = build_test_planner_agent()
        raw = await _agent_respond(planner, build_planner_message(result.analysis, types))
        result.test_plan = parse_plan_result(raw)
        total = sum(
            len(result.test_plan.get(f"{t}_scenarios", []))
            for t in ["e2e", "api", "unit"]
        )
        await emit("plan", f"Test planı hazır. {total} senaryo planlandı.")
    except Exception as exc:
        result.error = f"Test planlama başarısız: {exc}"
        return result

    # ── 3. TEST KODU ÜRETİMİ ─────────────────────────────────────────────────
    await emit("generate", f"Test kodları üretiliyor ({proj_ctx.framework})...")
    try:
        from config.settings import PACKAGE_ROOT
        generator = build_test_generator_agent(framework=proj_ctx.framework)
        raw = await _agent_respond(
            generator,
            build_generator_message(
                result.test_plan,
                settings.playwright_base_url,
                pr.title,
                project_context=proj_ctx.summary(),
            ),
        )
        # Test dosyaları her zaman PACKAGE_ROOT/tests/generated altına yazılır
        output_dir = PACKAGE_ROOT / settings.test_output_dir
        result.generated_files = extract_and_write_tests(raw, str(output_dir))
        await emit("generate", f"{len(result.generated_files)} test dosyası oluşturuldu.")
    except Exception as exc:
        result.error = f"Test üretimi başarısız: {exc}"
        return result

    # ── 4. TEST ÇALIŞTIRMA ────────────────────────────────────────────────────
    await emit("run", "Testler çalıştırılıyor...")
    try:
        result.run_results = await run_tests(result.generated_files, project_root)
        runner_agent = build_test_runner_agent()
        raw = await _agent_respond(
            runner_agent,
            build_runner_message(result.run_results, result.generated_files),
        )
        result.final_report = parse_runner_result(raw)
        status = result.final_report.get("overall_status", "?")
        await emit("report", f"Testler tamamlandı. Durum: {status.upper()}")
    except Exception as exc:
        result.error = f"Test çalıştırma başarısız: {exc}"
        return result

    # ── 5. RAPOR KAYDETME ─────────────────────────────────────────────────────
    try:
        result.saved_reports = save_report(result.final_report, result.pr_number)
        for fmt, path in result.saved_reports.items():
            await emit("report", f"Rapor kaydedildi ({fmt.upper()}): {path}")
    except Exception as exc:
        await emit("report", f"Rapor kaydedilemedi: {exc}")

    result.success = True
    return result


def _suggest_base_url(ctx: ProjectContext) -> str:
    """Framework'e göre varsayılan geliştirme sunucusu URL'si."""
    ports = {
        "nextjs": 3000, "react": 3000, "vue": 5173,
        "nuxt": 3000, "angular": 4200, "svelte": 5173,
        "django": 8000, "fastapi": 8000, "flask": 5000,
        "express": 3000, "laravel": 8000,
    }
    port = ports.get(ctx.framework, 3000)
    return f"http://localhost:{port}"
