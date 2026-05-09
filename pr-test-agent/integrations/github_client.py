# GitHub PR entegrasyonu
# PyGithub ile PR diff, dosya listesi, açıklama çekme. Manuel diff desteği.

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from github import Github, Auth
from config.settings import settings


@dataclass
class PRFile:
    filename: str
    status: str          # added | modified | removed | renamed
    additions: int
    deletions: int
    patch: str = ""
    source_content: str = ""  # Dosyanın PR head'indeki tam içeriği


@dataclass
class PRInfo:
    number: int
    title: str
    body: str
    base_branch: str
    head_branch: str
    files: list[PRFile] = field(default_factory=list)
    diff_text: str = ""
    repo_full_name: str = ""
    html_url: str = ""


class GitHubClient:
    def __init__(self, token: str = ""):
        _token = token or settings.github_token
        auth = Auth.Token(_token) if _token else None
        self._gh = Github(auth=auth)

    def get_pr_info(self, pr_url: str) -> PRInfo:
        """
        PR URL'den PR bilgilerini çeker.
        Örnek: https://github.com/org/repo/pull/42
        """
        owner, repo_name, pr_number = self._parse_pr_url(pr_url)
        repo = self._gh.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)

        files: list[PRFile] = []
        full_diff_parts: list[str] = []

        for f in pr.get_files():
            patch = f.patch or ""
            # .json ve .lock dosyalarının içeriğini alma — gereksiz gürültü
            source_content = ""
            if not f.filename.endswith((".json", ".lock", ".md")):
                try:
                    content_file = repo.get_contents(f.filename, ref=pr.head.sha)
                    source_content = content_file.decoded_content.decode("utf-8", errors="replace")
                except Exception:
                    pass

            files.append(PRFile(
                filename=f.filename,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                patch=patch,
                source_content=source_content,
            ))
            if patch:
                full_diff_parts.append(f"--- {f.filename}\n{patch}")

        return PRInfo(
            number=pr.number,
            title=pr.title,
            body=pr.body or "",
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            files=files,
            diff_text="\n\n".join(full_diff_parts),
            repo_full_name=repo.full_name,
            html_url=pr.html_url,
        )

    @staticmethod
    def _parse_pr_url(url: str) -> tuple[str, str, int]:
        pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        m = re.search(pattern, url)
        if not m:
            raise ValueError(f"Geçersiz GitHub PR URL'si: {url}")
        return m.group(1), m.group(2), int(m.group(3))


def load_manual_diff(diff_file: str) -> PRInfo:
    """Kullanıcının sağladığı diff dosyasından PRInfo oluşturur."""
    with open(diff_file, "r", encoding="utf-8") as fh:
        diff_text = fh.read()

    files: list[PRFile] = []
    for block in re.split(r"^--- ", diff_text, flags=re.MULTILINE):
        if not block.strip():
            continue
        first_line = block.split("\n")[0].strip()
        filename = first_line.lstrip("a/")
        files.append(PRFile(
            filename=filename,
            status="modified",
            additions=block.count("\n+"),
            deletions=block.count("\n-"),
            patch=block,
        ))

    return PRInfo(
        number=0,
        title="Manuel Diff",
        body="",
        base_branch="",
        head_branch="",
        files=files,
        diff_text=diff_text,
    )
