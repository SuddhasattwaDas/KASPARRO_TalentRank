import logging
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache

import requests

from config import config

logger = logging.getLogger(__name__)


@dataclass
class GitHubData:
    username: str
    public_repos: int = 0
    recent_activity: bool = False
    recent_commits: int = 0
    relevant_repos: int = 0
    repo_names: list = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.repo_names is None:
            self.repo_names = []


class GitHubClient:
    BASE_URL = "https://api.github.com"
    PYTHON_AI_KEYWORDS = [
        "python", "fastapi", "django", "flask", "langchain", "langgraph",
        "llamaindex", "rag", "embedding", "vector", "agent", "llm",
        "openai", "anthropic", "transformers", "pytorch", "tensorflow",
        "pinecone", "weaviate", "chromadb", "faiss", "ml", "ai"
    ]

    def __init__(self):
        self.token = config.github_token
        self.timeout = config.github_timeout
        self.session = requests.Session()
        if self.token:
            # Fine-grained PATs (github_pat_) use Bearer, classic PATs use token
            auth_scheme = "Bearer" if self.token.startswith("github_pat_") else "token"
            self.session.headers.update({"Authorization": f"{auth_scheme} {self.token}"})
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        self._cache = {}

    def _make_request(self, url: str, params: dict = None) -> Optional[Dict]:
        cache_key = f"{url}:{str(params)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        for attempt in range(config.github_max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)

                if response.status_code == 403:
                    if "rate limit" in response.text.lower():
                        logger.warning("GitHub API rate limited")
                        if attempt < config.github_max_retries:
                            time.sleep(2 ** attempt)
                            continue
                        return {"error": "rate_limited"}
                    elif "forbidden" in response.text.lower():
                        return {"error": "private_or_forbidden"}

                if response.status_code == 404:
                    return {"error": "not_found"}

                response.raise_for_status()
                data = response.json()
                self._cache[cache_key] = data
                return data

            except requests.Timeout:
                logger.warning(f"GitHub request timeout (attempt {attempt + 1})")
                if attempt < config.github_max_retries:
                    time.sleep(1)
                    continue
                return {"error": "timeout"}
            except requests.RequestException as e:
                logger.error(f"GitHub request failed: {e}")
                if attempt < config.github_max_retries:
                    time.sleep(1)
                    continue
                return {"error": str(e)}

        return {"error": "max_retries_exceeded"}

    def get_user(self, username: str) -> Optional[Dict]:
        return self._make_request(f"{self.BASE_URL}/users/{username}")

    def get_user_repos(self, username: str, per_page: int = 30) -> Optional[list]:
        return self._make_request(f"{self.BASE_URL}/users/{username}/repos", {
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "type": "public"
        })

    def get_user_events(self, username: str, per_page: int = 30) -> Optional[list]:
        return self._make_request(f"{self.BASE_URL}/users/{username}/events/public", {
            "per_page": per_page
        })

    def _is_relevant_repo(self, repo: Dict) -> bool:
        name = (repo.get("name") or "").lower()
        description = (repo.get("description") or "").lower()
        language = (repo.get("language") or "").lower()
        topics = [t.lower() for t in (repo.get("topics") or [])]

        search_text = f"{name} {description} {language} {' '.join(topics)}"
        return any(kw in search_text for kw in self.PYTHON_AI_KEYWORDS)

    def _has_recent_activity(self, events: list, days: int = 90) -> bool:
        if not events:
            return False
        import datetime
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        for event in events[:10]:
            created_at = event.get("created_at")
            if created_at:
                try:
                    event_time = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if event_time > cutoff:
                        return True
                except Exception:
                    continue
        return False

    def enrich(self, username: str) -> GitHubData:
        if not username:
            return GitHubData(username="", error="No username provided")

        user_data = self.get_user(username)
        if not user_data:
            return GitHubData(username=username, error="Failed to fetch user")

        if user_data.get("error"):
            return GitHubData(username=username, error=user_data["error"])

        repos = self.get_user_repos(username) or []
        events = self.get_user_events(username) or []

        relevant_repos = [r for r in repos if self._is_relevant_repo(r)]
        recent_activity = self._has_recent_activity(events)

        commit_count = 0
        for event in events[:20]:
            if event.get("type") == "PushEvent":
                commit_count += len(event.get("payload", {}).get("commits", []))

        repo_names = [r.get("name") for r in relevant_repos[:10]]

        return GitHubData(
            username=username,
            public_repos=user_data.get("public_repos", 0),
            recent_activity=recent_activity,
            recent_commits=commit_count,
            relevant_repos=len(relevant_repos),
            repo_names=repo_names
        )

    def score_github(self, github_data: GitHubData) -> tuple[int, int, int, str]:
        if github_data.error:
            return 0, 0, 0, f"GitHub enrichment failed: {github_data.error}"

        activity_score = 0
        repo_score = 0
        reasons = []

        if github_data.recent_activity:
            activity_score = 5
            reasons.append("Recent public activity detected")
        else:
            reasons.append("No recent public activity")

        if github_data.relevant_repos >= 3:
            repo_score = 5
            reasons.append(f"{github_data.relevant_repos} relevant Python/AI repositories")
        elif github_data.relevant_repos > 0:
            repo_score = 3
            reasons.append(f"{github_data.relevant_repos} relevant Python/AI repositories")
        elif github_data.public_repos >= 10:
            repo_score = 2
            reasons.append(f"{github_data.public_repos} public repositories")
        elif github_data.public_repos > 0:
            repo_score = 1
            reasons.append(f"{github_data.public_repos} public repositories")
        else:
            reasons.append("No public repositories found")

        total_score = min(activity_score + repo_score, 10)
        return total_score, activity_score, repo_score, "; ".join(reasons)


github_client = GitHubClient()