"""
Test Planner Agent
PR analizine göre test senaryoları planlar ve önceliklendirir.
"""
from __future__ import annotations
import json
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from config.settings import settings

SYSTEM_PROMPT = """Sen bir QA mühendisisin. PR analiz sonuçlarına göre detaylı test planı oluşturmakla görevlisin.

Verilen analizi inceleyerek SADECE aşağıdaki JSON formatında test planı üret:

{
  "test_plan_summary": "Test planının kısa özeti",
  "e2e_scenarios": [
    {
      "id": "e2e_001",
      "title": "Senaryo başlığı",
      "priority": "high|medium|low",
      "steps": ["Adım 1", "Adım 2"],
      "expected_result": "Beklenen sonuç",
      "test_data": {"key": "value"}
    }
  ],
  "api_scenarios": [
    {
      "id": "api_001",
      "title": "API test başlığı",
      "priority": "high|medium|low",
      "method": "GET|POST|PUT|DELETE",
      "endpoint": "/api/endpoint",
      "request_body": {},
      "expected_status": 200,
      "expected_response": {}
    }
  ],
  "unit_scenarios": [
    {
      "id": "unit_001",
      "title": "Unit test başlığı",
      "priority": "high|medium|low",
      "function": "functionName",
      "inputs": [],
      "expected_output": null
    }
  ],
  "regression_scenarios": ["Regresyon testi 1"],
  "estimated_duration_minutes": 15
}

Yanıtın sadece JSON olsun."""


def build_test_planner_agent() -> AssistantAgent:
    model_client = OpenAIChatCompletionClient(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return AssistantAgent(
        name="TestPlannerAgent",
        model_client=model_client,
        system_message=SYSTEM_PROMPT,
    )


def build_planner_message(analysis: dict, test_types: list[str]) -> str:
    return f"""
## PR Analiz Sonucu
```json
{json.dumps(analysis, ensure_ascii=False, indent=2)}
```

## İstenen Test Türleri
{', '.join(test_types)}

Yukarıdaki analiz sonucuna göre kapsamlı bir test planı oluştur.
Sadece istenen test türleri için senaryo üret.
""".strip()


def parse_plan_result(response_text: str) -> dict:
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)
