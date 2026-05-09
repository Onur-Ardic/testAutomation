"""
Test Runner Agent
Üretilen testleri çalıştırır, sonuçları analiz eder ve rapor üretir.
"""
from __future__ import annotations
import json
import asyncio
from pathlib import Path
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from mcp.playwright_mcp_client import get_runner
from config.settings import settings

SYSTEM_PROMPT = """Sen bir test sonuç analisti ve QA mühendisisin.
Test çalıştırma sonuçlarını analiz edip net bir rapor üretmekle görevlisin.

Verilen test sonuçlarını inceleyerek SADECE aşağıdaki JSON formatında yanıt ver:

{
  "overall_status": "passed|failed|partial",
  "total_tests": 0,
  "passed": 0,
  "failed": 0,
  "skipped": 0,
  "duration_ms": 0,
  "failed_tests": [
    {
      "test_name": "Test adı",
      "error": "Hata mesajı",
      "file": "dosya.spec.ts",
      "suggestion": "Olası çözüm önerisi"
    }
  ],
  "coverage_assessment": "Test kapsamının değerlendirmesi",
  "pr_safe_to_merge": true,
  "recommendations": ["Öneri 1", "Öneri 2"]
}"""


def build_test_runner_agent() -> AssistantAgent:
    model_client = OpenAIChatCompletionClient(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return AssistantAgent(
        name="TestRunnerAgent",
        model_client=model_client,
        system_message=SYSTEM_PROMPT,
    )


async def run_tests(test_files: list[str], project_root: str = ".") -> dict:
    """Playwright MCP veya lokal runner ile testleri çalıştırır."""
    runner = await get_runner(project_root)
    all_results: list[dict] = []

    for test_file in test_files:
        result = await runner.run_test_file(test_file)
        result["file"] = test_file
        all_results.append(result)

    return {"runs": all_results}


def build_runner_message(run_results: dict, test_files: list[str]) -> str:
    return f"""
## Çalıştırılan Test Dosyaları
{chr(10).join(f'- {f}' for f in test_files)}

## Test Çalıştırma Sonuçları
```json
{json.dumps(run_results, ensure_ascii=False, indent=2)[:8000]}
```

Sonuçları analiz et ve JSON formatında rapor üret.
""".strip()


def parse_runner_result(response_text: str) -> dict:
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


def save_report(report: dict, pr_number: int | str, formats: list[str] | None = None) -> dict[str, str]:
    """Raporu HTML ve/veya JSON olarak kaydeder."""
    formats = formats or settings.report_formats
    report_dir = Path(settings.report_dir)
    report_dir.mkdir(exist_ok=True)
    saved: dict[str, str] = {}

    if "json" in formats:
        path = report_dir / f"pr_{pr_number}_report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        saved["json"] = str(path)

    if "html" in formats:
        path = report_dir / f"pr_{pr_number}_report.html"
        path.write_text(_render_html(report, pr_number), encoding="utf-8")
        saved["html"] = str(path)

    return saved


def _render_html(report: dict, pr_number: int | str) -> str:
    status_color = {
        "passed": "#22c55e",
        "failed": "#ef4444",
        "partial": "#f59e0b",
    }.get(report.get("overall_status", ""), "#6b7280")

    failed_rows = "".join(
        f"<tr><td>{t['test_name']}</td><td>{t['file']}</td>"
        f"<td style='color:#ef4444'>{t['error']}</td><td>{t['suggestion']}</td></tr>"
        for t in report.get("failed_tests", [])
    )

    recommendations = "".join(
        f"<li>{r}</li>" for r in report.get("recommendations", [])
    )

    safe_badge = (
        '<span style="color:#22c55e;font-weight:bold">✅ MERGE EDİLEBİLİR</span>'
        if report.get("pr_safe_to_merge")
        else '<span style="color:#ef4444;font-weight:bold">❌ MERGE EDİLEMEZ</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>PR #{pr_number} Test Raporu</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #f8fafc; }}
    h1 {{ color: #1e293b; }}
    .badge {{ display:inline-block; padding:6px 16px; border-radius:20px; color:white; font-weight:bold; background:{status_color}; }}
    .stats {{ display:flex; gap:20px; margin:20px 0; }}
    .stat {{ background:white; border-radius:8px; padding:16px 24px; box-shadow:0 1px 3px rgba(0,0,0,.1); text-align:center; }}
    .stat .num {{ font-size:2rem; font-weight:bold; }}
    table {{ width:100%; border-collapse:collapse; background:white; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
    th {{ background:#1e293b; color:white; padding:10px; text-align:left; }}
    td {{ padding:10px; border-bottom:1px solid #e2e8f0; }}
    ul {{ background:white; border-radius:8px; padding:16px 24px 16px 36px; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
  </style>
</head>
<body>
  <h1>🎭 PR #{pr_number} — Test Raporu</h1>
  <p><span class="badge">{report.get('overall_status','?').upper()}</span> &nbsp; {safe_badge}</p>

  <div class="stats">
    <div class="stat"><div class="num" style="color:#22c55e">{report.get('passed',0)}</div>Geçti</div>
    <div class="stat"><div class="num" style="color:#ef4444">{report.get('failed',0)}</div>Başarısız</div>
    <div class="stat"><div class="num" style="color:#6b7280">{report.get('skipped',0)}</div>Atlandı</div>
    <div class="stat"><div class="num">{report.get('total_tests',0)}</div>Toplam</div>
    <div class="stat"><div class="num">{report.get('duration_ms',0)}ms</div>Süre</div>
  </div>

  <h2>📋 Değerlendirme</h2>
  <p>{report.get('coverage_assessment','')}</p>

  {"<h2>❌ Başarısız Testler</h2><table><tr><th>Test</th><th>Dosya</th><th>Hata</th><th>Öneri</th></tr>" + failed_rows + "</table>" if failed_rows else ""}

  {"<h2>💡 Öneriler</h2><ul>" + recommendations + "</ul>" if recommendations else ""}
</body>
</html>"""
