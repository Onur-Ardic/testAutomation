# 🎭 PR Test Automation

> **AutoGen + Playwright MCP** kullanarak PR'lardan otomatik test senaryosu üreten ve çalıştıran yapay zeka destekli test otomasyon sistemi.

---

## İçindekiler

- [Nasıl Çalışır?](#nasıl-çalışır)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [Konfigürasyon](#konfigürasyon)
- [Kullanım — CLI](#kullanım--cli)
- [Kullanım — Web UI](#kullanım--web-ui)
- [Desteklenen Framework'ler](#desteklenen-frameworkler)
- [Çıktılar](#çıktılar)
- [Mimarı](#mimari)
- [Sorun Giderme](#sorun-giderme)

---

## Nasıl Çalışır?

Sisteme bir GitHub PR URL'si veya diff dosyası verirsiniz. Sistem 4 adımda çalışır:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   SEN          → PR URL veya Diff gir                          │
│                                                                 │
│   1. PRAnalyzerAgent   → PR'ı okur, neyin değiştiğini anlar   │
│                          (dosyalar, fonksiyonlar, endpointler) │
│                          Risk seviyesi belirler (low/high...)  │
│                                                                 │
│   2. TestPlannerAgent  → Hangi testler yazılmalı karar verir   │
│                          E2E / API / Unit senaryoları planlar  │
│                                                                 │
│   3. TestGeneratorAgent → Playwright TypeScript test kodu yazar│
│                           Framework'e göre uyarlar             │
│                           (Next.js, React, Django vb.)         │
│                                                                 │
│   4. TestRunnerAgent   → Testleri çalıştırır                   │
│                          HTML + JSON rapor üretir              │
│                          "Merge edilebilir mi?" kararı verir   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Agent'lar Ne Yapar?

| Agent | Girdi | Çıktı |
|-------|-------|-------|
| **PRAnalyzerAgent** | PR diff, dosya listesi, açıklama | Etkilenen component'ler, risk skoru, test alanları |
| **TestPlannerAgent** | Analiz sonucu | E2E/API/Unit senaryo listesi, adımlar, beklenen sonuçlar |
| **TestGeneratorAgent** | Test planı + framework bilgisi | `tests/generated/` klasörüne Playwright `.spec.ts` dosyaları |
| **TestRunnerAgent** | Test sonuçları | HTML/JSON rapor, merge tavsiyesi |

---

## Gereksinimler

| Araç | Versiyon | Açıklama |
|------|----------|----------|
| Python | 3.11+ | Ana sistem dili |
| Node.js | 18+ | Playwright test runner |
| npm | 9+ | Node paket yöneticisi |
| OpenAI API Key | — | GPT-4o kullanımı için |
| GitHub Token | — | Private repo'lar için (public'te opsiyonel) |

---

## Kurulum

### Adım 1 — Depoyu İndir

```bash
git clone <repo-url>
cd pr-test-agent
```

veya doğrudan klasöre git:

```bash
cd C:\...\testAutomation\pr-test-agent
```

---

### Adım 2 — Python Bağımlılıklarını Kur

```bash
# Windows'ta pip PATH'te olmayabilir. Şu komutla kur:
C:\Users\OnurA\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pip install -e .

# Veya python komutunuzu bulup kullanın:
python -m pip install -e .
py -m pip install -e .
```

Bu komut `pr-test` adlı global CLI komutunu sisteme yükler. Artık **herhangi bir klasörden** `pr-test` çalıştırabilirsiniz.

> ⚠️ Kurulum sonrası terminali kapatıp yeniden açın (PATH güncellemesi için).

---

### Adım 3 — Node / Playwright Kurulumu

```bash
npm install
npx playwright install chromium
```

> Bu adım sadece bir kez yapılır. Playwright'ın Chromium browser'ı indirir (~150 MB).

---

### Adım 4 — Ortam Değişkenlerini Ayarla

```bash
copy .env.example .env
```

`.env` dosyasını bir metin editörüyle aç ve doldur:

```env
# ── ZORUNLU ────────────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-...          # OpenAI hesabından al

# ── GITHUB (private repo için zorunlu, public'te opsiyonel) ───
GITHUB_TOKEN=ghp_...                # GitHub → Settings → Developer settings → Tokens

# ── TEST ORTAMI ────────────────────────────────────────────────
PLAYWRIGHT_BASE_URL=http://localhost:3000   # Test edilen uygulamanın adresi
```

**OpenAI API Key nasıl alınır?**
1. https://platform.openai.com adresine git
2. API Keys → Create new secret key
3. Kopyala, `.env`'e yapıştır

**GitHub Token nasıl alınır?**
1. GitHub → Sağ üst avatar → Settings
2. Developer settings → Personal access tokens → Tokens (classic)
3. Generate new token → `repo` yetkisi seç → Generate
4. Kopyala, `.env`'e yapıştır

---

### Kurulum Doğrulama

```bash
pr-test --help
```

Aşağıdakini görüyorsanız kurulum tamamdır:

```
🎭 PR Test Automation — AutoGen + Playwright MCP

Commands:
  run      PR'ı analiz edip testleri oluşturur ve çalıştırır.
  analyze  Sadece PR analizini çalıştırır, test oluşturmaz.
  serve    Web API sunucusunu başlatır.
```

---

## Konfigürasyon

`.env` dosyasındaki tüm seçenekler:

```env
# LLM
OPENAI_API_KEY=sk-...           # Zorunlu
OPENAI_MODEL=gpt-4o             # Değiştirilebilir: gpt-4-turbo, gpt-3.5-turbo

# GitHub
GITHUB_TOKEN=ghp_...            # Private repo için zorunlu
GITHUB_API_URL=https://api.github.com   # GitHub Enterprise için değiştir

# Test ortamı
PLAYWRIGHT_BASE_URL=http://localhost:3000   # Uygulamanın URL'si
PLAYWRIGHT_HEADLESS=true                    # false: browser görünür açılır

# Playwright MCP (opsiyonel — yoksa otomatik lokal runner kullanılır)
PLAYWRIGHT_MCP_HOST=localhost
PLAYWRIGHT_MCP_PORT=8931

# Çıktı dizinleri
TEST_OUTPUT_DIR=tests/generated   # Üretilen testlerin yeri
REPORT_DIR=reports                # Raporların yeri

# Web API
API_HOST=0.0.0.0
API_PORT=8000

# Agent davranışı
MAX_AGENT_TURNS=20     # Agent konuşma tur limiti
AGENT_TIMEOUT=300      # Saniye cinsinden timeout
```

---

## Kullanım — CLI

### Temel Kullanım

```bash
# Test etmek istediğin projenin dizinine git
cd C:\projelerim\benim-nextjs-projem

# PR URL ile çalıştır
pr-test run --pr-url https://github.com/org/repo/pull/42
```

Sistem otomatik olarak:
- Projenin framework'ünü tespit eder (Next.js, React, Django vb.)
- PR'ı GitHub'dan çeker
- Test senaryoları üretir
- Testleri çalıştırır
- `reports/` klasörüne rapor kaydeder

---

### Tüm Komutlar

#### `pr-test run` — Ana Komut

```bash
pr-test run [SEÇENEKLER]

Seçenekler:
  --pr-url TEXT          GitHub PR URL'si
                         Örn: https://github.com/org/repo/pull/42

  --diff-file TEXT       Manuel diff dosyası (GitHub erişimi yoksa)
                         Örn: --diff-file degisiklikler.diff

  --type TEXT            Test türleri (varsayılan: all)
                         Seçenekler: e2e, api, unit veya kombinasyon
                         Örn: --type e2e,api

  --base-url TEXT        Test edilecek uygulamanın URL'si
                         Örn: --base-url http://localhost:4200

  --project-root TEXT    Proje dizini (varsayılan: bulunduğun klasör)
                         Örn: --project-root C:\projelerim\uygulama

  --report-format TEXT   Rapor formatı (varsayılan: html,json)
                         Seçenekler: html, json

  --output-dir TEXT      Test dosyalarının yazılacağı yer
                         Varsayılan: tests/generated
```

**Örnekler:**

```bash
# Temel kullanım
pr-test run --pr-url https://github.com/acme/shop/pull/15

# Sadece E2E ve API testleri
pr-test run --pr-url https://github.com/acme/shop/pull/15 --type e2e,api

# Farklı bir URL ile (staging ortamı)
pr-test run --pr-url https://github.com/acme/shop/pull/15 --base-url http://staging.acme.com

# Başka bir projeyi hedefle
pr-test run --pr-url <url> --project-root C:\diger-proje

# Manuel diff dosyası ile
pr-test run --diff-file my-changes.diff --base-url http://localhost:3000
```

---

#### `pr-test analyze` — Sadece Analiz

Test çalıştırmadan sadece PR'ı analiz eder. Ne test edilmesi gerektiğini görmek için kullanışlıdır.

```bash
pr-test analyze --pr-url https://github.com/org/repo/pull/42
```

Çıktı (JSON):
```json
{
  "summary": "Kullanıcı kayıt formu eklendi",
  "affected_components": ["RegisterForm", "AuthService"],
  "risk_level": "high",
  "suggested_test_types": ["e2e", "api"]
}
```

---

#### `pr-test serve` — Web UI

```bash
pr-test serve --port 8000
```

Tarayıcıda `http://localhost:8000` adresini aç.

---

## Kullanım — Web UI

Web arayüzü CLI'a alternatif bir kullanım sunar.

### Başlatma

```bash
pr-test serve
```

### Kullanım Adımları

1. **`http://localhost:8000`** adresini tarayıcıda aç
2. **PR URL'si** gir (veya diff içeriğini yapıştır)
3. **Test türlerini** seç: E2E / API / Unit
4. **"Analyze & Run Tests"** butonuna tıkla
5. Canlı ilerleme çubuğunu izle
6. Sonuçları gör: kaç test geçti, kaçı başarısız oldu, merge edilebilir mi?
7. **HTML raporunu indir**

---

## Desteklenen Framework'ler

Sistem proje dizinini otomatik tarayarak framework'ü tespit eder:

| Framework | Tespit Yöntemi | Varsayılan Port |
|-----------|---------------|-----------------|
| **Next.js** | `package.json` → `"next"` | 3000 |
| **React** (CRA/Vite) | `package.json` → `"react"` | 3000 |
| **Vue.js** | `package.json` → `"vue"` | 5173 |
| **Nuxt** | `package.json` → `"nuxt"` | 3000 |
| **Angular** | `package.json` → `"@angular/core"` | 4200 |
| **SvelteKit** | `package.json` → `"@sveltejs/kit"` | 5173 |
| **Django** | `requirements.txt` → `django` | 8000 |
| **FastAPI** | `requirements.txt` → `fastapi` | 8000 |
| **Flask** | `requirements.txt` → `flask` | 5000 |
| **Express** | `package.json` → `"express"` | 3000 |
| **Laravel** | `composer.json` → `laravel/framework` | 8000 |

---

## Çıktılar

Bir çalışma sonrasında şu dosyalar oluşur:

```
proje-dizinin/
├── tests/
│   └── generated/
│       ├── e2e/
│       │   └── kullanici_kayit.spec.ts    ← E2E testleri
│       ├── api/
│       │   └── auth_api.spec.ts           ← API testleri
│       └── unit/
│           └── validate_email.spec.ts     ← Unit testleri
└── reports/
    ├── pr_42_report.html                  ← Görsel HTML raporu
    └── pr_42_report.json                  ← Makine okunabilir JSON
```

### HTML Raporu İçeriği

- ✅/❌ Genel durum rozeti
- **"Merge edilebilir mi?"** kararı
- Test istatistikleri (geçti / başarısız / atlandı / süre)
- Başarısız testlerin detayı + olası çözüm önerileri
- Genel kalite değerlendirmesi

---

## Docker ile Çalıştırma

Tüm sistemi (Playwright MCP + API) container içinde çalıştırmak için:

```bash
# .env dosyasını doldur
copy .env.example .env

# Başlat
docker compose up -d

# Logları izle
docker compose logs -f

# Durdur
docker compose down
```

Web UI: `http://localhost:8000`

---

## Sorun Giderme

### ❌ `pr-test` komutu tanınmıyor

Terminal'i yeniden başlatın. Hâlâ çalışmıyorsa:

```bash
# Windows
C:\Users\<kullanici>\AppData\Local\Python\pythoncore-3.14-64\Scripts\pr-test.exe --help
```

### ❌ `ModuleNotFoundError: No module named 'typer'`

```bash
pip install typer rich pydantic-settings
```

### ❌ `GitHub API rate limit exceeded`

`.env`'e GitHub token ekleyin:
```env
GITHUB_TOKEN=ghp_...
```

### ❌ `Connection refused` (test çalıştırma hatası)

`PLAYWRIGHT_BASE_URL`'deki adresteki uygulama çalışmıyor. Uygulamayı başlatın:
```bash
npm run dev     # veya
python manage.py runserver   # Django için
```

### ❌ `OpenAI API error: insufficient_quota`

OpenAI hesabınızda kredi bitti. https://platform.openai.com/billing adresinden kredi ekleyin.

### ❌ Test dosyaları oluştu ama çalışmıyor

Playwright kurulumunu doğrulayın:
```bash
npx playwright install chromium
npx playwright test tests/generated/ --list
```


---

## Mimari

```
PR (URL/Diff)
      │
      ▼
┌─────────────────────────────────────┐
│        AutoGen Orchestrator         │
│                                     │
│  PRAnalyzer → TestPlanner →         │
│  TestGenerator → TestRunner         │
└──────────────┬──────────────────────┘
               │
               ▼
        Playwright MCP
     (Browser Automation)
               │
               ▼
    tests/generated/*.spec.ts
    reports/pr_N_report.html
```

---

## Kurulum

### Global Kurulum (Tüm Projelerden Çalıştır)

```bash
cd pr-test-agent
pip install -e .
```

Artık **herhangi bir web projesinin dizininden** çalışabilirsiniz:

```bash
cd /path/to/my-nextjs-app
pr-test run --pr-url https://github.com/org/repo/pull/42
```

### Bağımlılıklar

```bash
cd pr-test-agent
pip install -r requirements.txt
npm install && npx playwright install chromium
```

### Ortam Değişkenleri

```bash
cp .env.example .env
# .env dosyasını düzenle:
# OPENAI_API_KEY=sk-...
# GITHUB_TOKEN=ghp_... (private repo için)
```

> **Not:** `PLAYWRIGHT_BASE_URL` belirtmezseniz sistem framework'ü otomatik tespit edip doğru portu önerir (Next.js → 3000, Angular → 4200, Django → 8000 vb.)

---

## Kullanım

### CLI — Herhangi Bir Projeden

```bash
# Proje dizinine git
cd /path/to/any-web-project

# GitHub PR URL ile (framework otomatik tespit edilir)
pr-test run --pr-url https://github.com/org/repo/pull/42

# Farklı bir dizindeki projeyi hedefle
pr-test run --pr-url <url> --project-root /path/to/project

# Manuel diff ile
pr-test run --diff-file changes.diff --base-url http://localhost:3000

# Test türü seç
pr-test run --pr-url <url> --type e2e,api

# Sadece analiz (test çalıştırmadan)
pr-test analyze --pr-url <url>

# Web UI başlat
pr-test serve --port 8000
```

### Web UI

```bash
# Playwright MCP server'ı başlat (opsiyonel, yoksa lokal runner kullanılır)
npm run mcp:start

# API + Web UI başlat
python -m cli.main serve

# Tarayıcıda aç
open http://localhost:8000
```

### Docker

```bash
docker compose up -d
open http://localhost:8000
```

---

## Akış

| Adım | Agent | Ne Yapar |
|------|-------|----------|
| 1 | **PRAnalyzerAgent** | Diff'i okur, etkilenen component/fonksiyon/endpoint'leri tespit eder, risk skoru verir |
| 2 | **TestPlannerAgent** | E2E/API/Unit test senaryoları planlar ve önceliklendirir |
| 3 | **TestGeneratorAgent** | Her senaryo için Playwright TypeScript test kodu üretir |
| 4 | **TestRunnerAgent** | Testleri çalıştırır, sonuçları analiz eder, HTML/JSON rapor üretir |

---

## Çıktılar

- `tests/generated/e2e/` — Üretilen E2E test dosyaları
- `tests/generated/api/` — API test dosyaları
- `tests/generated/unit/` — Unit test dosyaları
- `reports/pr_N_report.html` — Görsel HTML raporu
- `reports/pr_N_report.json` — Makine okunabilir JSON raporu

---

## Konfigürasyon

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `OPENAI_API_KEY` | — | **Zorunlu.** OpenAI API anahtarı |
| `OPENAI_MODEL` | `gpt-4o` | Kullanılacak model |
| `GITHUB_TOKEN` | — | Private repo için GitHub token |
| `PLAYWRIGHT_BASE_URL` | `http://localhost:3000` | Test edilen uygulamanın URL'si |
| `PLAYWRIGHT_MCP_HOST` | `localhost` | Playwright MCP server host |
| `PLAYWRIGHT_MCP_PORT` | `8931` | Playwright MCP server port |
| `PLAYWRIGHT_HEADLESS` | `true` | Headless mod |
| `TEST_OUTPUT_DIR` | `tests/generated` | Üretilen testlerin dizini |
| `REPORT_DIR` | `reports` | Raporların dizini |
| `MAX_AGENT_TURNS` | `20` | Maksimum agent konuşma turları |
| `AGENT_TIMEOUT` | `300` | Agent timeout (saniye) |
