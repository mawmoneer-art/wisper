#!/usr/bin/env python3
"""Build a local snapshot of Vapi's LLM-facing docs from the VapiAI/docs source.

docs.vapi.ai publishes /llms.txt and /llms-full.txt, but the source of truth
is the public repo https://github.com/VapiAI/docs (Fern docs). This script
regenerates equivalent files from that repo so the snapshot can be refreshed
without depending on the hosted site being reachable.

Usage:
    git clone --depth 1 https://github.com/VapiAI/docs /tmp/vapi-docs
    python3 scripts/build-vapi-llms-docs.py /tmp/vapi-docs docs/vapi

Outputs (in the output dir):
    llms.txt            index of every doc page with title, URL, one-line summary
    llms-full.txt       full markdown body of every doc page (excluding changelog)
    llms-changelog.txt  full changelog entries, newest first
    openapi.json        the Vapi REST API OpenAPI 3 spec, copied verbatim
    SNAPSHOT.json       provenance: upstream commit, date, page counts
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SITE = "https://docs.vapi.ai"

# Upstream docs contain placeholder credentials in examples. GitHub push
# protection matches on shape, not validity, so rewrite them to an obviously
# templated form that scanners ignore.
REDACTIONS = [
    (re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+"),
     "https://hooks.slack.com/services/<TEAM_ID>/<CHANNEL_ID>/<TOKEN>"),
]


def redact(text):
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return data, text[m.end():]


def slug_from_path(rel):
    return rel[:-4] if rel.endswith(".mdx") else rel


class Builder:
    def __init__(self, src, out):
        self.src = Path(src)
        self.fern = self.src / "fern"
        self.out = Path(out)
        self.docs_yml = yaml.safe_load((self.fern / "docs.yml").read_text())
        self.index_lines = []
        self.full_parts = []
        self.seen = set()
        self.page_count = 0
        self.link_count = 0

    # -- navigation walk -------------------------------------------------
    def walk(self, items, depth):
        for item in items:
            if "page" in item and "path" in item:
                self.page(item, depth)
            elif "section" in item:
                title = item["section"].strip()
                if title:
                    self.index_lines.append("")
                    self.index_lines.append("#" * min(depth, 6) + " " + title)
                self.walk(item.get("contents", []), depth + 1)
            elif "link" in item:
                self.index_lines.append(f"- [{item['link']}]({item['href']})")
                self.link_count += 1
            elif "api" in item:
                self.api_reference(item, depth)
            elif "changelog" in item:
                pass

    def page(self, item, depth):
        rel = item["path"]
        path = self.fern / rel
        if not path.exists():
            print(f"warning: missing {rel}", file=sys.stderr)
            return
        text = path.read_text(encoding="utf-8")
        fm, body = frontmatter(text)
        title = str(fm.get("title") or item["page"]).strip()
        subtitle = str(fm.get("subtitle") or fm.get("description") or "").strip()
        slug = str(fm.get("slug") or slug_from_path(rel)).strip("/")
        url = f"{SITE}/{slug}"
        line = f"- [{title}]({url})"
        if subtitle:
            line += f": {subtitle}"
        if item.get("availability"):
            line += f" [{item['availability']}]"
        self.index_lines.append(line)
        if rel in self.seen:
            return
        self.seen.add(rel)
        self.page_count += 1
        header = f"# {title}\n\nSource: {url}\n"
        if subtitle:
            header += f"\n{subtitle}\n"
        self.full_parts.append(header + "\n" + redact(body.strip()) + "\n")

    # -- API reference -----------------------------------------------------
    def api_reference(self, item, depth):
        name = item["api-name"]
        api_dir = self.fern / "apis" / name
        spec_path = next((p for p in api_dir.iterdir() if p.name.startswith("openapi.") and p.suffix in (".json", ".yml", ".yaml")), None)
        if spec_path is None:
            return
        spec = json.loads(spec_path.read_text()) if spec_path.suffix == ".json" else yaml.safe_load(spec_path.read_text())
        self.index_lines.append("")
        self.index_lines.append("#" * min(depth, 6) + " " + item["api"])
        if name == "api":
            self.index_lines.append(f"- [API reference overview]({SITE}/api-reference)")
            self.index_lines.append("- [OpenAPI spec (JSON)](https://api.vapi.ai/api-json)")
            self.index_lines.append("- [Swagger UI](https://api.vapi.ai/api)")
            self.index_lines.append(f"- Base URL: {spec.get('servers', [{}])[0].get('url', 'https://api.vapi.ai')}")
            self.index_lines.append("- Local copy of the spec: docs/vapi/openapi.json")
            shutil.copy(spec_path, self.out / "openapi.json")
        by_tag = {}
        for route, ops in spec.get("paths", {}).items():
            for method, op in ops.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                for tag in op.get("tags") or ["Other"]:
                    by_tag.setdefault(tag, []).append((method.upper(), route, op.get("summary") or op.get("operationId") or ""))
        for tag, ops in by_tag.items():
            self.index_lines.append("")
            self.index_lines.append("#" * min(depth + 1, 6) + " " + tag)
            for method, route, summary in ops:
                self.index_lines.append(f"- {method} {route}: {summary}")

    # -- changelog -----------------------------------------------------------
    def changelog(self):
        cl = self.fern / "changelog"
        parts = []
        files = sorted((f for f in cl.glob("*.mdx") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.stem)), reverse=True)
        for f in files:
            fm, body = frontmatter(f.read_text(encoding="utf-8"))
            body = body.strip()
            if not body:
                continue
            parts.append(f"# {f.stem}\n\nSource: {SITE}/whats-new\n\n{redact(body)}\n")
        return files, parts

    # -- output ----------------------------------------------------------------
    def build(self):
        self.out.mkdir(parents=True, exist_ok=True)
        commit = subprocess.run(["git", "-C", str(self.src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        commit_date = subprocess.run(["git", "-C", str(self.src), "log", "-1", "--format=%cI"], capture_output=True, text=True).stdout.strip()
        tabs = {t: v for t, v in self.docs_yml.get("tabs", {}).items()}
        for tab in self.docs_yml["navigation"]:
            tab_id = tab["tab"]
            meta = tabs.get(tab_id, {})
            self.index_lines.append("")
            self.index_lines.append(f"## {meta.get('display-name', tab_id)}")
            if tab_id == "changelog":
                self.index_lines.append(f"- [What's New (changelog)]({SITE}/whats-new): dated product updates, newest first; full text in docs/vapi/llms-changelog.txt")
                continue
            self.walk(tab.get("layout", []), 3)

        cl_files, cl_parts = self.changelog()
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        preamble = (
            "# Vapi\n\n"
            "> Vapi is a developer platform for building voice AI agents that make and receive phone calls, "
            "run in the browser, and integrate with custom tools, workflows, and a REST API.\n\n"
            f"This file mirrors {SITE}/llms.txt. It was generated from the public docs source "
            f"(https://github.com/VapiAI/docs, commit {commit[:12]}, {commit_date[:10]}) on {generated}.\n"
            "Full page bodies are in llms-full.txt next to this file; the changelog is in llms-changelog.txt; "
            "the REST API contract is in openapi.json.\n"
        )
        (self.out / "llms.txt").write_text(preamble + "\n".join(self.index_lines).rstrip() + "\n", encoding="utf-8")
        (self.out / "llms-full.txt").write_text(
            f"# Vapi documentation (full text)\n\nMirror of {SITE}/llms-full.txt, generated from VapiAI/docs commit {commit[:12]} ({commit_date[:10]}).\n\n"
            + "\n---\n\n".join(self.full_parts),
            encoding="utf-8",
        )
        (self.out / "llms-changelog.txt").write_text(
            f"# Vapi changelog\n\nGenerated from VapiAI/docs commit {commit[:12]} ({commit_date[:10]}). Newest first.\n\n"
            + "\n---\n\n".join(cl_parts),
            encoding="utf-8",
        )
        (self.out / "SNAPSHOT.json").write_text(json.dumps({
            "source_repo": "https://github.com/VapiAI/docs",
            "source_commit": commit,
            "source_commit_date": commit_date,
            "generated_on": generated,
            "site": SITE,
            "pages": self.page_count,
            "external_links": self.link_count,
            "changelog_entries": len(cl_files),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"pages={self.page_count} links={self.link_count} changelog={len(cl_files)} -> {self.out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    Builder(sys.argv[1], sys.argv[2]).build()
