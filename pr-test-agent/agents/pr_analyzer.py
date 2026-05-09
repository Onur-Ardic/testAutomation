"""
PR Analyzer Agent
PR diff ve metadata'yı analiz ederek etkilenen alanları, risk skorlarını
ve test edilmesi gereken bileşenleri tespit eder.
"""
from __future__ import annotations
import json
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from integrations.github_client import PRInfo
from config.settings import settings

SYSTEM_PROMPT = """Sen bir kıdemli yazılım mühendisisin. PR diff'lerini analiz edip
etkilenen alanları ve test risklerini tespit etmekle görevlisin.

Verilen PR bilgilerini analiz et ve SADECE aşağıdaki JSON formatında yanıt ver:

{
  "summary": "PR'ın kısa özeti",
  "affected_components": ["component1", "component2"],
  "affected_files": ["file1.ts", "file2.ts"],
  "changed_functions": ["functionName1", "functionName2"],
  "changed_api_endpoints": ["/api/endpoint1"],
  "risk_level": "low|medium|high|critical",
  "risk_reasons": ["sebep1", "sebep2"],
  "test_focus_areas": {
    "e2e": ["kullanıcı senaryosu 1", "kullanıcı senaryosu 2"],
    "api": ["endpoint testi 1"],
    "unit": ["fonksiyon testi 1"]
  },
  "suggested_test_types": ["e2e", "api", "unit"]
}

Yanıtın sadece JSON olsun, başka açıklama ekleme."""


def build_pr_analyzer_agent() -> AssistantAgent:
    model_client = OpenAIChatCompletionClient(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return AssistantAgent(
        name="PRAnalyzerAgent",
        model_client=model_client,
        system_message=SYSTEM_PROMPT,
    )


def build_pr_analysis_message(pr: PRInfo) -> str:
    files_summary = "\n".join(
        f"- [{f.status}] {f.filename} (+{f.additions}/-{f.deletions})"
        for f in pr.files
    )
    diff_excerpt = pr.diff_text[:6000] if pr.diff_text else "(diff yok)"

    return f"""
## PR Bilgileri
- **Başlık**: {pr.title}
- **PR No**: #{pr.number}
- **URL**: {pr.html_url}
- **Base Branch**: {pr.base_branch}
- **Head Branch**: {pr.head_branch}
- **Açıklama**: {pr.body or '(yok)'}

## Değişen Dosyalar
{files_summary}

## Diff (ilk 6000 karakter)
```diff
{diff_excerpt}
```

Yukarıdaki PR'ı analiz et ve JSON formatında yanıt ver.
""".strip()


def parse_analysis_result(response_text: str) -> dict:
    """Agent yanıtından JSON'ı çıkarır."""
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)
