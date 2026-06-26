#!/usr/bin/env python3
"""
Cutctx Lead Generation Script
==============================
Pulls warm leads from three free/low-cost sources:

  1. GitHub   — repos actively using Anthropic or OpenAI SDK (spending money)
  2. Hacker News — people discussing API costs, Claude Code, agent billing
  3. Product Hunt — recent AI DevTool launches (founders in "spend" phase)

Scores each lead 0-100 and exports a ranked CSV ready for HubSpot import.

Usage:
  pip install requests python-dotenv rich
  export GITHUB_TOKEN=ghp_xxx          # required — github.com/settings/tokens
  export PRODUCTHUNT_TOKEN=xxx         # optional — api.producthunt.com/v2/oauth/token
  python lead_gen.py
  python lead_gen.py --sources github hn     # run only specific sources
  python lead_gen.py --limit 200             # cap per source
  python lead_gen.py --output my_leads.csv   # custom output file
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ── Config ──────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PRODUCTHUNT_TOKEN = os.environ.get("PRODUCTHUNT_TOKEN", "")

OUTPUT_FILE = Path("cutctx_leads.csv")
REQUEST_DELAY = 1.0   # seconds between API calls (be polite)
GITHUB_STARS_MIN = 30  # only repos with this many stars+
MAX_PER_SOURCE = 100

# Repos/orgs to skip (already know them, competitors, etc.)
SKIP_ORGS = {
    "openai", "anthropic", "google", "microsoft", "meta-llama",
    "mistralai", "groq-inc", "portkey-ai", "helicone",
    "cutctx", "aryansingh",  # us
}

# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Lead:
    # Identity
    source: str = ""
    name: str = ""
    company: str = ""
    title: str = ""
    profile_url: str = ""
    company_url: str = ""
    email: str = ""
    location: str = ""

    # Intel
    why_relevant: str = ""
    tool_signal: str = ""      # "claude_code", "cursor", "openai_api", etc.
    repo_name: str = ""
    repo_stars: int = 0
    repo_description: str = ""
    hn_post_title: str = ""
    hn_post_url: str = ""
    ph_product: str = ""

    # Scoring
    score: int = 0
    score_breakdown: str = ""

    # Metadata
    found_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "new"
    notes: str = ""


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_lead(lead: Lead) -> Lead:
    """Score a lead 0-100 based on ICP fit signals."""
    score = 0
    breakdown: list[str] = []

    # Tool signals (highest value — they're already spending)
    tool_scores = {
        "claude_code": 15,
        "anthropic_api": 12,
        "openai_api": 10,
        "cursor": 10,
        "codex": 10,
        "aider": 8,
        "langchain": 6,
        "litellm": 6,
        "llamaindex": 5,
    }
    for tool, pts in tool_scores.items():
        if tool in lead.tool_signal:
            score += pts
            breakdown.append(f"+{pts} {tool}")

    # Repo engagement (proxy for active usage)
    if lead.repo_stars >= 500:
        score += 10; breakdown.append("+10 stars≥500")
    elif lead.repo_stars >= 100:
        score += 7; breakdown.append("+7 stars≥100")
    elif lead.repo_stars >= 30:
        score += 4; breakdown.append("+4 stars≥30")

    # Source quality
    if lead.source == "hn_cost_complaint":
        score += 15; breakdown.append("+15 HN cost complaint")
    elif lead.source == "hn_hiring":
        score += 10; breakdown.append("+10 HN hiring AI")
    elif lead.source == "github_heavy_user":
        score += 8; breakdown.append("+8 GitHub heavy user")
    elif lead.source == "producthunt":
        score += 8; breakdown.append("+8 PH recent launch")
    elif lead.source == "github_org":
        score += 5; breakdown.append("+5 GitHub org")

    # Keywords in description/title (pain signals)
    pain_words = ["cost", "expensive", "bill", "token", "budget", "agent", "autonomous"]
    text = (lead.repo_description + " " + lead.why_relevant + " " + lead.hn_post_title).lower()
    pain_hits = sum(1 for w in pain_words if w in text)
    if pain_hits >= 3:
        score += 10; breakdown.append(f"+10 pain_words={pain_hits}")
    elif pain_hits >= 1:
        score += 5; breakdown.append(f"+5 pain_words={pain_hits}")

    # Has email (actionable)
    if lead.email:
        score += 5; breakdown.append("+5 has_email")

    # Has company (not just individual)
    if lead.company and lead.company.lower() not in ("", "unknown", "none"):
        score += 3; breakdown.append("+3 has_company")

    lead.score = min(score, 100)
    lead.score_breakdown = " | ".join(breakdown)
    return lead


# ── GitHub source ─────────────────────────────────────────────────────────────

class GitHubSource:
    """
    Searches GitHub for repos that:
    - Use Anthropic SDK or OpenAI SDK in requirements.txt / pyproject.toml
    - Have meaningful stars (proxy for real usage, not toy projects)
    - Are recently updated (actively maintained)
    """

    BASE = "https://api.github.com"

    QUERIES = [
        # Python repos using Anthropic SDK
        ('language:python "anthropic" in:file filename:requirements.txt', "anthropic_api"),
        ('language:python "anthropic" in:file filename:pyproject.toml', "anthropic_api"),
        # Claude Code config files (people who wired it up)
        ('"ANTHROPIC_BASE_URL" in:file filename:.env.example', "claude_code"),
        ('"cutctx wrap" OR "cutctx proxy" in:readme', "claude_code"),
        # OpenAI heavy users
        ('language:python "openai" in:file filename:requirements.txt stars:>50', "openai_api"),
        # Agentic / agent frameworks
        ('language:python "langchain" "openai" in:file filename:requirements.txt stars:>30', "langchain"),
        # TypeScript / Next.js AI products
        ('language:typescript "openai" in:file filename:package.json stars:>30', "openai_api"),
        ('language:typescript "anthropic" in:file filename:package.json stars:>30', "anthropic_api"),
    ]

    def __init__(self, token: str, limit: int = MAX_PER_SOURCE):
        self.token = token
        self.limit = limit
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.BASE}{path}"
        r = self.session.get(url, params=params, timeout=15)
        if r.status_code == 403:
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset - int(time.time())) + 1
            print(f"  [github] rate limited, sleeping {wait}s")
            time.sleep(wait)
            r = self.session.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _search_code(self, query: str) -> list[dict]:
        results = []
        page = 1
        while len(results) < self.limit:
            try:
                data = self._get("/search/code", {"q": query, "per_page": 30, "page": page})
            except requests.HTTPError as e:
                print(f"  [github] search error: {e}")
                break
            items = data.get("items", [])
            if not items:
                break
            results.extend(items)
            if len(items) < 30:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        return results

    def _get_repo(self, full_name: str) -> dict | None:
        try:
            return self._get(f"/repos/{full_name}")
        except Exception:
            return None

    def _get_owner_info(self, owner_login: str) -> dict | None:
        try:
            return self._get(f"/users/{owner_login}")
        except Exception:
            return None

    def fetch(self) -> list[Lead]:
        if not self.token:
            print("[github] GITHUB_TOKEN not set — skipping")
            return []

        seen_repos: set[str] = set()
        leads: list[Lead] = []

        for query, tool_signal in self.QUERIES:
            if len(leads) >= self.limit:
                break
            print(f"  [github] query: {query[:60]}…")
            items = self._search_code(query)
            time.sleep(REQUEST_DELAY)

            for item in items:
                repo_info = item.get("repository", {})
                full_name = repo_info.get("full_name", "")
                owner_login = repo_info.get("owner", {}).get("login", "")

                if not full_name or full_name in seen_repos:
                    continue
                if owner_login.lower() in SKIP_ORGS:
                    continue

                seen_repos.add(full_name)

                # Get full repo details
                repo = self._get_repo(full_name)
                if not repo:
                    continue

                stars = repo.get("stargazers_count", 0)
                if stars < GITHUB_STARS_MIN:
                    continue

                # Skip forks of popular repos
                if repo.get("fork") and stars < 100:
                    continue

                # Get owner info
                owner = self._get_owner_info(owner_login)
                time.sleep(REQUEST_DELAY * 0.5)

                company = ""
                email = ""
                name = owner_login
                profile_url = f"https://github.com/{owner_login}"

                if owner:
                    company = (owner.get("company") or "").strip().lstrip("@")
                    email = owner.get("email") or ""
                    name = owner.get("name") or owner_login

                lead = Lead(
                    source="github_heavy_user" if stars > 200 else "github_org",
                    name=name,
                    company=company,
                    profile_url=profile_url,
                    company_url=repo.get("homepage") or f"https://github.com/{owner_login}",
                    email=email,
                    repo_name=full_name,
                    repo_stars=stars,
                    repo_description=(repo.get("description") or "")[:200],
                    tool_signal=tool_signal,
                    why_relevant=f"Repo '{full_name}' ({stars}★) uses {tool_signal}. {(repo.get('description') or '')[:100]}",
                )
                leads.append(score_lead(lead))

                if len(leads) >= self.limit:
                    break

            time.sleep(REQUEST_DELAY)

        return leads


# ── Hacker News source ────────────────────────────────────────────────────────

class HackerNewsSource:
    """
    Uses the free Algolia HN search API to find:
    1. People complaining about API costs (warm leads)
    2. "Who's Hiring" posts mentioning Claude Code / AI infra (companies buying)
    3. Ask HN threads about LLM cost optimization
    """

    ALGOLIA = "https://hn.algolia.com/api/v1"

    COST_QUERIES = [
        "anthropic bill expensive",
        "openai cost tokens",
        "claude api expensive",
        "agent token budget",
        "LLM API costs startup",
        "claude code expensive",
        "cursor API bill",
        "openai invoice surprise",
    ]

    HIRING_KEYWORDS = [
        "claude code", "cursor.sh", "anthropic api", "openai api",
        "autonomous agent", "coding agent", "llm engineer",
    ]

    def __init__(self, limit: int = MAX_PER_SOURCE):
        self.limit = limit
        self.session = requests.Session()

    def _search(self, query: str, tags: str = "comment", days_back: int = 90) -> list[dict]:
        cutoff = int(time.time()) - days_back * 86400
        params = {
            "query": query,
            "tags": tags,
            "numericFilters": f"created_at_i>{cutoff}",
            "hitsPerPage": 20,
        }
        try:
            r = self.session.get(f"{self.ALGOLIA}/search", params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("hits", [])
        except Exception as e:
            print(f"  [hn] search error: {e}")
            return []

    def _extract_company_from_comment(self, text: str) -> str:
        """Try to extract a company name from an HN comment."""
        # Pattern: "at [Company]", "work at [Company]", "I work for [Company]"
        patterns = [
            r"(?:at|for|@)\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)",
            r"([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\s+(?:engineer|CTO|founder|VP)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                candidate = m.group(1)
                if len(candidate) > 2 and candidate.lower() not in ("the", "our", "this", "that"):
                    return candidate
        return ""

    def _fetch_hiring_posts(self) -> list[Lead]:
        """Find 'Who's Hiring' posts and extract companies using AI tools."""
        leads: list[Lead] = []
        # Get recent Ask HN: Who's Hiring? posts
        r = self.session.get(
            f"{self.ALGOLIA}/search",
            params={"query": "Ask HN: Who is hiring", "tags": "story", "hitsPerPage": 5},
            timeout=10,
        )
        if r.status_code != 200:
            return leads

        for post in r.json().get("hits", []):
            post_id = post.get("objectID")
            if not post_id:
                continue
            # Get comments from this post
            try:
                cr = self.session.get(
                    f"{self.ALGOLIA}/items/{post_id}", timeout=10
                )
                cr.raise_for_status()
                post_data = cr.json()
            except Exception:
                continue

            for comment in (post_data.get("children") or []):
                text = (comment.get("text") or "").lower()
                author = comment.get("author", "")

                # Check if they mention AI coding tools
                matched_tools = [kw for kw in self.HIRING_KEYWORDS if kw in text]
                if not matched_tools:
                    continue

                company = self._extract_company_from_comment(comment.get("text", ""))
                tool_signal = "_".join(
                    kw.replace(" ", "_").replace(".", "_").replace("/", "_")
                    for kw in matched_tools[:2]
                )

                lead = Lead(
                    source="hn_hiring",
                    name=author,
                    company=company,
                    profile_url=f"https://news.ycombinator.com/user?id={author}",
                    hn_post_url=f"https://news.ycombinator.com/item?id={comment.get('objectID')}",
                    hn_post_title=post.get("title", "HN Who's Hiring"),
                    tool_signal=tool_signal,
                    why_relevant=f"HN hiring post mentioning: {', '.join(matched_tools)}",
                )
                leads.append(score_lead(lead))
                if len(leads) >= self.limit:
                    break

            time.sleep(REQUEST_DELAY * 0.5)

        return leads

    def fetch(self) -> list[Lead]:
        leads: list[Lead] = []
        seen_authors: set[str] = set()

        # 1. Cost complaint threads
        print("  [hn] searching cost complaint threads…")
        for query in self.COST_QUERIES:
            if len(leads) >= self.limit:
                break
            hits = self._search(query, tags="comment", days_back=180)
            time.sleep(REQUEST_DELAY * 0.5)
            for hit in hits:
                author = hit.get("author", "")
                if not author or author in seen_authors:
                    continue
                seen_authors.add(author)

                text = hit.get("comment_text") or hit.get("story_text") or ""
                company = self._extract_company_from_comment(text)

                # Detect tool signals
                tool_map = {
                    "claude": "anthropic_api", "anthropic": "anthropic_api",
                    "openai": "openai_api", "gpt-4": "openai_api",
                    "cursor": "cursor", "claude code": "claude_code",
                    "codex": "codex", "aider": "aider",
                    "langchain": "langchain",
                }
                tool_signal = ",".join({
                    sig for kw, sig in tool_map.items() if kw in text.lower()
                } or {"llm_api"})

                lead = Lead(
                    source="hn_cost_complaint",
                    name=author,
                    company=company,
                    profile_url=f"https://news.ycombinator.com/user?id={author}",
                    hn_post_url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    hn_post_title=hit.get("story_title") or query,
                    tool_signal=tool_signal,
                    why_relevant=f"HN comment about cost/tokens: '{text[:120]}…'",
                )
                leads.append(score_lead(lead))

        # 2. Who's Hiring posts
        print("  [hn] scanning Who's Hiring posts…")
        hiring_leads = self._fetch_hiring_posts()
        for l in hiring_leads:
            if l.name not in seen_authors:
                seen_authors.add(l.name)
                leads.append(l)

        return leads[:self.limit]


# ── Product Hunt source ────────────────────────────────────────────────────────

class ProductHuntSource:
    """
    Finds recently launched AI DevTools on Product Hunt.
    These founders are actively spending on LLM APIs.
    Requires a free PH OAuth token: api.producthunt.com/v2/oauth/token
    """

    GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

    QUERY = """
    query ($after: String, $order: PostsOrder) {
      posts(first: 20, after: $after, order: $order, topic: "artificial-intelligence") {
        edges {
          node {
            id
            name
            tagline
            description
            url
            votesCount
            createdAt
            makers {
              name
              username
              headline
              twitterUsername
              websiteUrl
            }
          }
          cursor
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    """

    def __init__(self, token: str, limit: int = MAX_PER_SOURCE):
        self.token = token
        self.limit = limit
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _is_devtool(self, tagline: str, description: str) -> bool:
        """Filter for developer tools / AI coding tools."""
        text = (tagline + " " + description).lower()
        dev_signals = [
            "developer", "code", "api", "llm", "agent", "copilot",
            "cursor", "claude", "openai", "autonomous", "codebase",
            "engineering", "devtool", "sdk", "cli",
        ]
        return sum(1 for s in dev_signals if s in text) >= 2

    def fetch(self) -> list[Lead]:
        if not self.token:
            print("[producthunt] PRODUCTHUNT_TOKEN not set — skipping")
            return []

        leads: list[Lead] = []
        cursor = None
        seen_makers: set[str] = set()

        while len(leads) < self.limit:
            variables: dict[str, Any] = {"order": "NEWEST"}
            if cursor:
                variables["after"] = cursor

            try:
                r = self.session.post(
                    self.GRAPHQL,
                    json={"query": self.QUERY, "variables": variables},
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"  [ph] error: {e}")
                break

            posts = data.get("data", {}).get("posts", {})
            edges = posts.get("edges", [])
            if not edges:
                break

            for edge in edges:
                node = edge.get("node", {})
                tagline = node.get("tagline", "")
                description = node.get("description") or ""

                if not self._is_devtool(tagline, description):
                    continue

                for maker in node.get("makers", []):
                    username = maker.get("username", "")
                    if username in seen_makers:
                        continue
                    seen_makers.add(username)

                    twitter = maker.get("twitterUsername") or ""
                    website = maker.get("websiteUrl") or ""

                    # Detect tool signals from product description
                    text = (tagline + " " + description).lower()
                    tool_signal_map = {
                        "claude": "anthropic_api", "anthropic": "anthropic_api",
                        "openai": "openai_api", "gpt": "openai_api",
                        "cursor": "cursor", "agent": "llm_agent",
                        "langchain": "langchain",
                    }
                    tool_signal = ",".join({
                        sig for kw, sig in tool_signal_map.items() if kw in text
                    } or {"ai_tool"})

                    lead = Lead(
                        source="producthunt",
                        name=maker.get("name") or username,
                        company=node.get("name", ""),
                        title=maker.get("headline") or "Founder",
                        profile_url=f"https://www.producthunt.com/@{username}",
                        company_url=node.get("url", website),
                        ph_product=node.get("name", ""),
                        tool_signal=tool_signal,
                        why_relevant=(
                            f"PH launch: {node.get('name')} — {tagline[:100]}. "
                            f"{node.get('votesCount', 0)} upvotes."
                        ),
                    )
                    leads.append(score_lead(lead))

                    if len(leads) >= self.limit:
                        break

            page_info = posts.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            time.sleep(REQUEST_DELAY)

        return leads


# ── Dedup & merge ─────────────────────────────────────────────────────────────

def dedup_leads(leads: list[Lead]) -> list[Lead]:
    """Remove duplicate leads by profile URL or email."""
    seen: set[str] = set()
    deduped: list[Lead] = []
    for lead in leads:
        key = lead.profile_url or lead.email or lead.name
        if key and key not in seen:
            seen.add(key)
            deduped.append(lead)
    return deduped


# ── CSV export ─────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "score", "source", "name", "company", "title",
    "profile_url", "company_url", "email",
    "tool_signal", "why_relevant",
    "repo_name", "repo_stars", "repo_description",
    "hn_post_title", "hn_post_url",
    "ph_product",
    "score_breakdown", "status", "notes", "found_at",
]

def export_csv(leads: list[Lead], path: Path) -> None:
    leads_sorted = sorted(leads, key=lambda l: l.score, reverse=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for lead in leads_sorted:
            row = asdict(lead)
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    print(f"\n✅  Exported {len(leads_sorted)} leads → {path}")


# ── Pretty print summary ──────────────────────────────────────────────────────

def print_summary(leads: list[Lead]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title=f"Top Leads ({len(leads)} total)", show_lines=True)
        table.add_column("Score", style="bold green", width=6)
        table.add_column("Name", width=20)
        table.add_column("Company", width=20)
        table.add_column("Source", width=18)
        table.add_column("Tool Signal", width=18)
        table.add_column("Why", width=40)

        for lead in sorted(leads, key=lambda l: l.score, reverse=True)[:20]:
            table.add_row(
                str(lead.score),
                lead.name[:20],
                (lead.company or "—")[:20],
                lead.source[:18],
                lead.tool_signal[:18],
                lead.why_relevant[:40],
            )
        console.print(table)
    except ImportError:
        # Fallback without rich
        print(f"\n{'Score':>5}  {'Name':<20}  {'Company':<20}  {'Source':<18}  {'Why'}")
        print("-" * 100)
        for lead in sorted(leads, key=lambda l: l.score, reverse=True)[:20]:
            print(
                f"{lead.score:>5}  {lead.name[:20]:<20}  "
                f"{(lead.company or '—')[:20]:<20}  "
                f"{lead.source[:18]:<18}  "
                f"{lead.why_relevant[:40]}"
            )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cutctx lead generation script")
    parser.add_argument(
        "--sources", nargs="+",
        choices=["github", "hn", "producthunt"],
        default=["github", "hn", "producthunt"],
        help="Which sources to run (default: all)",
    )
    parser.add_argument("--limit", type=int, default=MAX_PER_SOURCE,
                        help=f"Max leads per source (default: {MAX_PER_SOURCE})")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE,
                        help=f"Output CSV path (default: {OUTPUT_FILE})")
    parser.add_argument("--min-score", type=int, default=0,
                        help="Only export leads above this score")
    args = parser.parse_args()

    all_leads: list[Lead] = []

    if "github" in args.sources:
        if not GITHUB_TOKEN:
            print("⚠️  GITHUB_TOKEN not set. Get one at github.com/settings/tokens (no scopes needed for public repos).")
        else:
            print(f"[1/3] Fetching GitHub leads (limit={args.limit})…")
            gh = GitHubSource(GITHUB_TOKEN, limit=args.limit)
            leads = gh.fetch()
            print(f"  → {len(leads)} GitHub leads found")
            all_leads.extend(leads)

    if "hn" in args.sources:
        print(f"[2/3] Fetching Hacker News leads (limit={args.limit})…")
        hn = HackerNewsSource(limit=args.limit)
        leads = hn.fetch()
        print(f"  → {len(leads)} HN leads found")
        all_leads.extend(leads)

    if "producthunt" in args.sources:
        if not PRODUCTHUNT_TOKEN:
            print("⚠️  PRODUCTHUNT_TOKEN not set. Get one free at api.producthunt.com/v2/oauth/token")
        else:
            print(f"[3/3] Fetching Product Hunt leads (limit={args.limit})…")
            ph = ProductHuntSource(PRODUCTHUNT_TOKEN, limit=args.limit)
            leads = ph.fetch()
            print(f"  → {len(leads)} Product Hunt leads found")
            all_leads.extend(leads)

    if not all_leads:
        print("No leads found. Check your API tokens and network.")
        return

    # Dedup and filter
    all_leads = dedup_leads(all_leads)
    if args.min_score > 0:
        all_leads = [l for l in all_leads if l.score >= args.min_score]

    print(f"\nTotal unique leads: {len(all_leads)}")
    print_summary(all_leads)
    export_csv(all_leads, args.output)

    # Tier breakdown
    tiers = {
        "Hot (≥60)": [l for l in all_leads if l.score >= 60],
        "Warm (40-59)": [l for l in all_leads if 40 <= l.score < 60],
        "Cold (<40)": [l for l in all_leads if l.score < 40],
    }
    print("\nLead breakdown:")
    for tier, bucket in tiers.items():
        print(f"  {tier}: {len(bucket)}")

    print(f"\nNext step: open {args.output} and start with the Hot leads.")
    print("Import to HubSpot: Contacts → Import → From file → map 'name','company','email','profile_url'")


if __name__ == "__main__":
    main()
