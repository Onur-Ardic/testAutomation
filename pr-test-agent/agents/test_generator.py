"""
Test Generator Agent
Test planını alarak Playwright TypeScript test kodu üretir.
ProjectContext'e göre framework-aware testler üretir.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from config.settings import settings

SYSTEM_PROMPT_BASE = """Sen uzman bir Playwright TypeScript test yazarısın.
Verilen test planına göre gerçek çalışabilir Playwright test kodu üret.

Kurallar:
- TypeScript kullan (@playwright/test)
- Her test dosyası tek bir test türü içersin (e2e / api / unit)
- test.describe ve test() bloklarını doğru kullan
- E2E testlerinde page fixture kullan, API testlerinde request fixture
- Her test bağımsız çalışabilmeli (test isolation)
- Anlamlı locator'lar kullan (getByRole, getByLabel, getByTestId tercih et)
- Assertions için expect() kullan
- Test datalarını test içinde tanımla
- Proje context'ine göre framework'e özgü selector ve pattern kullan

SADECE kod üret, açıklama ekleme. Her dosyayı şu formatta ver:

### FILE: tests/generated/e2e/test_name.spec.ts
```typescript
// kod buraya
```

### FILE: tests/generated/api/test_name.spec.ts
```typescript
// kod buraya
```
"""

# Framework bazlı ek talimatlar
FRAMEWORK_HINTS: dict[str, str] = {
    "nextjs": """
Next.js projesinde:
- App Router kullanılıyorsa: URL yapısı /app dizini ile eşleşir
- Pages Router: /pages dizini
- API route'ları /api/* altındadır
- next/link ile navigate edilmiş linkler için getByRole('link') kullan
- Server component vs client component farkına dikkat et
""",
    "react": """
React projesinde:
- SPA olduğu için navigate sonrası URL değişimini bekle
- React Router kullanılıyor olabilir, history push ile URL değişir
- data-testid attribute'ları için getByTestId() kullan
""",
    "vue": """
Vue.js projesinde:
- Vue Router ile navigation için waitForURL kullan
- v-model ile bağlı input'lar için fill() kullan
- component event'leri DOM event'lerine dönüşür
""",
    "nuxt": """
Nuxt projesinde:
- SSR/SSG olduğu için sayfa yükleme beklemesi önemli
- /api route'ları doğrudan test edilebilir
- useRouter ile navigation için waitForURL kullan
""",
    "angular": """
Angular projesinde:
- RouterLink ile navigate için getByRole('link') kullan
- Angular Material component'leri için mat- prefix'li class'lar kullanılabilir
- Reactive forms: getByLabel() ile form alanlarına eriş
""",
    "svelte": """
SvelteKit projesinde:
- +page.svelte dosyaları route'ları temsil eder
- /api route'ları server-side endpoint'ler
- SSR için waitForLoadState('networkidle') kullan
""",
    "django": """
Django projesinde:
- URL'ler urls.py ile tanımlı, test senaryolarında gerçek URL'leri kullan
- CSRF token gerektirebilir, API testlerinde header olarak ekle
- Django REST Framework kullanılıyorsa /api/ prefix'i yaygındır
- Admin panel /admin/ altındadır
""",
    "fastapi": """
FastAPI projesinde:
- OpenAPI docs /docs veya /redoc'ta mevcut
- Tüm endpoint'ler JSON döner
- request fixture ile HTTP testleri yap, browser gerekmeyebilir
- Bearer token authentication yaygındır
""",
    "express": """
Express.js projesinde:
- REST API endpoint'lerini request fixture ile test et
- Middleware'lerin etkisini göz önünde bulundur
- JSON body için Content-Type: application/json header'ı gönder
""",
    "laravel": """
Laravel projesinde:
- CSRF token form submit'lerde gereklidir
- /api route'ları Laravel Sanctum/Passport ile korunabilir
- Blade template'leri form'ları render eder
""",
}


def build_system_prompt(framework: str = "unknown") -> str:
    hint = FRAMEWORK_HINTS.get(framework, "")
    if hint:
        return SYSTEM_PROMPT_BASE + f"\n## Framework Notları ({framework})\n{hint}"
    return SYSTEM_PROMPT_BASE


def build_test_generator_agent(framework: str = "unknown") -> AssistantAgent:
    model_client = OpenAIChatCompletionClient(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return AssistantAgent(
        name="TestGeneratorAgent",
        model_client=model_client,
        system_message=build_system_prompt(framework),
    )


def build_generator_message(test_plan: dict, base_url: str, pr_title: str, project_context: str = "") -> str:
    ctx_section = f"\n## Proje Context\n{project_context}" if project_context else ""
    return f"""
## Test Planı
```json
{json.dumps(test_plan, ensure_ascii=False, indent=2)}
```

## Proje Bilgileri
- Base URL: {base_url}
- PR: {pr_title}{ctx_section}

Yukarıdaki test planındaki tüm senaryolar için Playwright TypeScript test kodu üret.
Her senaryo için ayrı test() bloğu oluştur.
""".strip()


def extract_and_write_tests(response_text: str, output_dir: str = "") -> list[str]:
    """Agent çıktısından test dosyalarını parse edip diske yazar."""
    base = Path(output_dir or settings.test_output_dir)
    written: list[str] = []

    # ### FILE: path/to/file.spec.ts\n```typescript\n...\n``` bloklarını bul
    pattern = re.compile(
        r"###\s*FILE:\s*(.+?\.spec\.ts)\s*\n```(?:typescript|ts)\n(.*?)```",
        re.DOTALL
    )

    for match in pattern.finditer(response_text):
        relative_path = match.group(1).strip()
        code = match.group(2).strip()

        # tests/generated/ prefix'ini koru, yoksa ekle
        if not relative_path.startswith("tests/generated"):
            relative_path = f"tests/generated/{relative_path}"

        # output_dir override ile yeniden yaz
        parts = Path(relative_path).parts
        # parts[0]='tests', parts[1]='generated', rest=...
        if len(parts) > 2:
            sub = Path(*parts[2:])
        else:
            sub = Path(parts[-1])

        target = base / sub
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        written.append(str(target))

    return written
