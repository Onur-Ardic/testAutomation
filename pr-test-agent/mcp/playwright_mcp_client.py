"""
Playwright MCP Client
Playwright MCP server ile JSON-RPC üzerinden iletişim kurar.
MCP server: npx @playwright/mcp@latest --port 8931
"""
from __future__ import annotations
import asyncio
import json
import uuid
import httpx
from pathlib import Path
from config.settings import settings


class PlaywrightMCPClient:
    def __init__(self, host: str = "", port: int = 0):
        self.host = host or settings.playwright_mcp_host
        self.port = port or settings.playwright_mcp_port
        self.base_url = f"http://{self.host}:{self.port}"

    async def _call(self, method: str, params: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        async with httpx.AsyncClient(timeout=settings.agent_timeout) as client:
            resp = await client.post(f"{self.base_url}/rpc", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error']}")
            return data.get("result", {})

    async def run_test_file(self, test_file: str) -> dict:
        """Belirtilen Playwright test dosyasını çalıştırır."""
        return await self._call("playwright.runTests", {
            "testFile": test_file,
            "headless": settings.playwright_headless,
            "baseURL": settings.playwright_base_url,
        })

    async def run_test_suite(self, test_dir: str, grep: str = "") -> dict:
        """Dizindeki tüm testleri çalıştırır. grep ile filtrelenebilir."""
        params: dict = {
            "testDir": test_dir,
            "headless": settings.playwright_headless,
            "baseURL": settings.playwright_base_url,
        }
        if grep:
            params["grep"] = grep
        return await self._call("playwright.runTests", params)

    async def get_report(self, run_id: str) -> dict:
        """Tamamlanan test çalışmasının raporunu getirir."""
        return await self._call("playwright.getReport", {"runId": run_id})

    async def ping(self) -> bool:
        """MCP server'ın ayakta olup olmadığını kontrol eder."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


class LocalPlaywrightRunner:
    """
    MCP server yokken veya lokal ortamda doğrudan 'npx playwright test' çalıştırır.
    Fallback olarak kullanılır.
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    async def run_test_file(self, test_file: str) -> dict:
        return await self._run(["npx", "playwright", "test", test_file, "--reporter=json"])

    async def run_test_suite(self, test_dir: str, grep: str = "") -> dict:
        cmd = ["npx", "playwright", "test", test_dir, "--reporter=json"]
        if grep:
            cmd += ["--grep", grep]
        return await self._run(cmd)

    async def _run(self, cmd: list[str]) -> dict:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.project_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        raw = stdout.decode("utf-8", errors="replace")
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"raw_output": raw}

        result["returncode"] = proc.returncode
        result["stderr"] = stderr.decode("utf-8", errors="replace")
        return result


async def get_runner(project_root: str = ".") -> PlaywrightMCPClient | LocalPlaywrightRunner:
    """MCP server varsa MCP client, yoksa lokal runner döndürür."""
    client = PlaywrightMCPClient()
    if await client.ping():
        return client
    return LocalPlaywrightRunner(project_root)
