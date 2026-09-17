#!/usr/bin/env python3
"""Atualiza a lista de commits públicos recentes no README do perfil."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


USERNAME = os.environ.get("GITHUB_USERNAME", "rsilvamedeiros")
TOKEN = os.environ.get("GH_TOKEN", "")
README = Path(os.environ.get("README_PATH", "README.md"))
LIMIT = int(os.environ.get("COMMITS_LIMIT", "5"))
START = "<!-- RECENT-COMMITS:START -->"
END = "<!-- RECENT-COMMITS:END -->"
AUTOMATION_MESSAGE = "docs: atualizar commits recentes"


def github_api(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API retornou HTTP {error.code}: {detail}") from error


def recent_commits() -> list[dict]:
    query = quote(f"author:{USERNAME}")
    url = (
        "https://api.github.com/search/commits"
        f"?q={query}&sort=committer-date&order=desc&per_page={max(LIMIT * 3, 20)}"
    )
    items = github_api(url).get("items", [])
    return [
        item
        for item in items
        if item.get("commit", {}).get("message", "").splitlines()[0]
        != AUTOMATION_MESSAGE
    ][:LIMIT]


def escape_markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def format_date(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%d/%m/%Y")


def render(commits: list[dict]) -> str:
    if not commits:
        return "_Nenhum commit público recente encontrado._"

    lines = []
    for item in commits:
        commit = item["commit"]
        message = escape_markdown(commit["message"].splitlines()[0])
        repository = item["repository"]["full_name"]
        repo_name = repository.split("/", 1)[-1]
        date = format_date(commit["committer"]["date"])
        short_sha = item["sha"][:7]
        lines.append(
            f"- [`{short_sha}`]({item['html_url']}) — {message} "
            f"em [{repo_name}](https://github.com/{repository}) · {date}"
        )
    return "\n".join(lines)


def update_readme(content: str) -> str:
    replacement = f"{START}\n{render(recent_commits())}\n{END}"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise RuntimeError("Marcadores de commits recentes não encontrados no README.")
    return updated


def main() -> int:
    original = README.read_text(encoding="utf-8")
    updated = update_readme(original)
    if updated != original:
        README.write_text(updated, encoding="utf-8", newline="\n")
        print(f"{README} atualizado.")
    else:
        print("Nenhuma alteração necessária.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        raise SystemExit(1)
