from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

_ENV_FILE = Path(__file__).parent.parent / ".env"

# pr-test-agent paketinin kök dizini (playwright.config.ts buradadır)
PACKAGE_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4o"

    # GitHub
    github_token: str = ""
    github_api_url: str = "https://api.github.com"

    # Playwright MCP
    playwright_mcp_host: str = "localhost"
    playwright_mcp_port: int = 8931
    playwright_headless: bool = True
    playwright_base_url: str = "http://localhost:3000"

    # Test output
    test_output_dir: str = "tests/generated"
    report_dir: str = "reports"
    report_formats: List[str] = ["html", "json"]

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Agent tuning
    max_agent_turns: int = 20
    agent_timeout: int = 300

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()
