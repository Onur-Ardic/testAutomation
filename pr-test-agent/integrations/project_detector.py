"""
Project Detector
Hedef projenin framework/stack'ini otomatik tespit eder.
Bu bilgi agent'lara context olarak verilir → framework'e uygun test üretilir.
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ProjectContext:
    root: str
    framework: str                    # react | nextjs | vue | nuxt | angular | svelte | django | fastapi | express | laravel | unknown
    language: str                     # typescript | javascript | python | php | java
    test_runner: str                  # playwright | jest | vitest | pytest | unknown
    has_api: bool = False
    api_base_path: str = "/api"
    router_type: str = "unknown"      # app-router | pages-router | vue-router | unknown
    component_dir: str = ""
    page_dir: str = ""
    extra: dict = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Framework: {self.framework}",
            f"Language: {self.language}",
            f"Test runner: {self.test_runner}",
            f"API: {'var, base=' + self.api_base_path if self.has_api else 'yok'}",
        ]
        if self.router_type != "unknown":
            lines.append(f"Router: {self.router_type}")
        if self.component_dir:
            lines.append(f"Component dizini: {self.component_dir}")
        if self.page_dir:
            lines.append(f"Page/route dizini: {self.page_dir}")
        return "\n".join(lines)


def detect_project(project_root: str) -> ProjectContext:
    """Proje dizinini tarayarak framework/stack'i tespit eder."""
    root = Path(project_root).resolve()
    ctx = ProjectContext(root=str(root), framework="unknown", language="javascript", test_runner="unknown")

    # ── package.json varsa (JS/TS projesi) ───────────────────────────────────
    pkg_file = root / "package.json"
    if pkg_file.exists():
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
        deps = {
            **pkg.get("dependencies", {}),
            **pkg.get("devDependencies", {}),
        }
        ctx.language = "typescript" if (root / "tsconfig.json").exists() else "javascript"
        ctx.test_runner = _detect_js_test_runner(deps, root)
        ctx = _detect_js_framework(deps, pkg, root, ctx)

    # ── Python projesi ────────────────────────────────────────────────────────
    elif (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        ctx.language = "python"
        ctx = _detect_python_framework(root, ctx)

    # ── PHP/Laravel ───────────────────────────────────────────────────────────
    elif (root / "composer.json").exists():
        composer = json.loads((root / "composer.json").read_text(encoding="utf-8"))
        if "laravel/framework" in composer.get("require", {}):
            ctx.framework = "laravel"
            ctx.language = "php"
            ctx.has_api = True
            ctx.api_base_path = "/api"
            ctx.page_dir = "resources/views"

    return ctx


def _detect_js_framework(deps: dict, pkg: dict, root: Path, ctx: ProjectContext) -> ProjectContext:
    # Next.js
    if "next" in deps:
        ctx.framework = "nextjs"
        ctx.has_api = True
        ctx.api_base_path = "/api"
        # App Router veya Pages Router
        if (root / "app").exists():
            ctx.router_type = "app-router"
            ctx.page_dir = "app"
        elif (root / "pages").exists():
            ctx.router_type = "pages-router"
            ctx.page_dir = "pages"
        ctx.component_dir = _find_dir(root, ["components", "src/components"])

    # Nuxt
    elif "nuxt" in deps or "@nuxt/core" in deps:
        ctx.framework = "nuxt"
        ctx.has_api = True
        ctx.api_base_path = "/api"
        ctx.page_dir = "pages"
        ctx.component_dir = _find_dir(root, ["components"])

    # Vue
    elif "vue" in deps:
        ctx.framework = "vue"
        ctx.router_type = "vue-router" if "vue-router" in deps else "unknown"
        ctx.component_dir = _find_dir(root, ["src/components", "components"])
        ctx.page_dir = _find_dir(root, ["src/views", "src/pages"])
        ctx.has_api = "axios" in deps or "ky" in deps or "@tanstack/vue-query" in deps

    # Angular
    elif "@angular/core" in deps:
        ctx.framework = "angular"
        ctx.language = "typescript"
        ctx.component_dir = "src/app"
        ctx.has_api = True

    # Svelte / SvelteKit
    elif "@sveltejs/kit" in deps:
        ctx.framework = "svelte"
        ctx.has_api = True
        ctx.api_base_path = "/api"
        ctx.page_dir = "src/routes"
        ctx.component_dir = "src/lib"
    elif "svelte" in deps:
        ctx.framework = "svelte"
        ctx.component_dir = "src"

    # React (CRA, Vite, etc.)
    elif "react" in deps:
        ctx.framework = "react"
        ctx.component_dir = _find_dir(root, ["src/components", "components", "src"])
        ctx.page_dir = _find_dir(root, ["src/pages", "pages", "src/views"])
        ctx.has_api = "axios" in deps or "@tanstack/react-query" in deps

    # Express / Node backend
    elif "express" in deps:
        ctx.framework = "express"
        ctx.has_api = True
        ctx.api_base_path = ""

    return ctx


def _detect_python_framework(root: Path, ctx: ProjectContext) -> ProjectContext:
    reqs = ""
    if (root / "requirements.txt").exists():
        reqs = (root / "requirements.txt").read_text(encoding="utf-8").lower()

    if "django" in reqs:
        ctx.framework = "django"
        ctx.has_api = "djangorestframework" in reqs or "drf" in reqs
        ctx.api_base_path = "/api"
        ctx.page_dir = "templates"
    elif "fastapi" in reqs:
        ctx.framework = "fastapi"
        ctx.has_api = True
        ctx.api_base_path = ""
    elif "flask" in reqs:
        ctx.framework = "flask"
        ctx.has_api = True
        ctx.api_base_path = ""
    
    # Python test runner
    if "pytest" in reqs or (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        ctx.test_runner = "pytest"

    return ctx


def _detect_js_test_runner(deps: dict, root: Path) -> str:
    if "@playwright/test" in deps:
        return "playwright"
    if "vitest" in deps:
        return "vitest"
    if "jest" in deps or "@jest/core" in deps:
        return "jest"
    if (root / "playwright.config.ts").exists() or (root / "playwright.config.js").exists():
        return "playwright"
    return "playwright"  # default olarak playwright öneriyoruz


def _find_dir(root: Path, candidates: list[str]) -> str:
    for c in candidates:
        if (root / c).is_dir():
            return c
    return candidates[0] if candidates else ""
