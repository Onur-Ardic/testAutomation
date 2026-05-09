"""
CLI arayüzü — Typer tabanlı
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

app = typer.Typer(
    name="pr-test",
    help="🎭 PR Test Automation — AutoGen + Playwright MCP",
    add_completion=False,
)
console = Console()


def _resolve_pr(
    pr_url: Optional[str],
    diff_file: Optional[str],
):
    """PR bilgilerini yükler. URL veya diff dosyasından."""
    from integrations.github_client import GitHubClient, load_manual_diff

    if pr_url:
        console.print(f"[cyan]GitHub PR yükleniyor:[/cyan] {pr_url}")
        client = GitHubClient()
        return client.get_pr_info(pr_url)
    elif diff_file:
        console.print(f"[cyan]Diff dosyası yükleniyor:[/cyan] {diff_file}")
        return load_manual_diff(diff_file)
    else:
        console.print("[red]Hata:[/red] --pr-url veya --diff-file belirtmelisiniz.")
        raise typer.Exit(code=1)


@app.command()
def run(
    pr_url: Optional[str] = typer.Option(None, "--pr-url", help="GitHub PR URL'si"),
    diff_file: Optional[str] = typer.Option(None, "--diff-file", help="Manuel diff dosyası"),
    test_types: str = typer.Option("all", "--type", "-t", help="Test türleri: e2e,api,unit veya all"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Test base URL'si"),
    project_root: str = typer.Option(".", "--project-root", help="Proje kök dizini"),
    report_format: str = typer.Option("html,json", "--report-format", help="Rapor formatları"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Test çıktı dizini"),
):
    """PR'ı analiz edip testleri oluşturur ve çalıştırır."""
    # Konfigürasyon override
    from config.settings import settings
    if base_url:
        settings.playwright_base_url = base_url
    if output_dir:
        settings.test_output_dir = output_dir
    settings.report_formats = [f.strip() for f in report_format.split(",")]

    # Test türlerini çöz
    if test_types == "all":
        types = ["e2e", "api", "unit"]
    else:
        types = [t.strip() for t in test_types.split(",")]

    # PR bilgilerini yükle
    pr = _resolve_pr(pr_url, diff_file)
    console.print(f"\n[bold green]PR:[/bold green] #{pr.number} — {pr.title}")
    console.print(f"[dim]{len(pr.files)} dosya değişti[/dim]")

    # Proje tespiti — project_root belirtilmemişse CWD kullan
    from integrations.project_detector import detect_project
    root = project_root if project_root != "." else str(Path.cwd())
    proj_ctx = detect_project(root)
    console.print(f"[dim]Framework: {proj_ctx.framework} | Dil: {proj_ctx.language}[/dim]\n")

    # İlerleme göstergesi ve orkestrasyon
    stages: list[str] = []

    async def progress_cb(stage: str, message: str):
        stages.append(f"[{stage}] {message}")
        console.print(f"  [cyan]{stage.upper()}[/cyan] {message}")

    async def _run():
        from agents.orchestrator import run_orchestration
        return await run_orchestration(pr, types, project_root, progress_cb)

    console.rule("[bold]Test Otomasyonu Başlıyor")
    result = asyncio.run(_run())

    if not result.success:
        console.print(f"\n[red bold]❌ Hata:[/red bold] {result.error}")
        raise typer.Exit(code=1)

    # Sonuç tablosu
    console.rule("[bold]Sonuçlar")
    report = result.final_report
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Metrik", style="bold")
    table.add_column("Değer")
    table.add_row("Durum", report.get("overall_status", "?").upper())
    table.add_row("Toplam Test", str(report.get("total_tests", 0)))
    table.add_row("✅ Geçti", str(report.get("passed", 0)))
    table.add_row("❌ Başarısız", str(report.get("failed", 0)))
    table.add_row("Merge Güvenli?", "✅ Evet" if report.get("pr_safe_to_merge") else "❌ Hayır")
    console.print(table)

    if result.saved_reports:
        console.print("\n[bold]📄 Raporlar:[/bold]")
        for fmt, path in result.saved_reports.items():
            console.print(f"  [{fmt.upper()}] {path}")

    if result.generated_files:
        console.print(f"\n[bold]🧪 Üretilen testler ({len(result.generated_files)}):[/bold]")
        for f in result.generated_files:
            console.print(f"  {f}")


@app.command()
def analyze(
    pr_url: Optional[str] = typer.Option(None, "--pr-url"),
    diff_file: Optional[str] = typer.Option(None, "--diff-file"),
):
    """Sadece PR analizini çalıştırır, test oluşturmaz."""
    import json
    from agents.pr_analyzer import build_pr_analyzer_agent, build_pr_analysis_message, parse_analysis_result
    from autogen_agentchat.messages import TextMessage
    from autogen_core import CancellationToken

    pr = _resolve_pr(pr_url, diff_file)

    async def _run():
        agent = build_pr_analyzer_agent()
        response = await agent.on_messages(
            [TextMessage(content=build_pr_analysis_message(pr), source="user")],
            cancellation_token=CancellationToken(),
        )
        return parse_analysis_result(response.chat_message.content)

    result = asyncio.run(_run())
    console.print_json(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
):
    """Web API sunucusunu başlatır."""
    import uvicorn
    console.print(f"[green]Web UI başlatılıyor:[/green] http://localhost:{port}")
    uvicorn.run("api.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
