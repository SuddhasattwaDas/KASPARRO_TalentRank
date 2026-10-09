import logging
from typing import List, Dict, Any
from collections import Counter

from config import config
from src.models import Candidate, ScoreBreakdown

logger = logging.getLogger(__name__)

PYTHON_BACKEND_KEYWORDS = {
    "fastapi": 5, "django": 4, "flask": 3, "pydantic": 3, "asyncio": 4,
    "sqlalchemy": 3, "alembic": 2, "pytest": 3, "postgresql": 3, "redis": 3,
    "celery": 2, "rabbitmq": 2, "kafka": 2, "docker": 2, "kubernetes": 2,
    "uvicorn": 1, "gunicorn": 1, "graphql": 2, "grpc": 2, "rest": 1,
    "aiohttp": 2, "pandas": 1, "numpy": 1
}

CLOUD_FULLSTACK_KEYWORDS = {
    "docker": 3, "kubernetes": 3, "gcp": 3, "aws": 3, "azure": 2,
    "terraform": 2, "ci/cd": 2, "github actions": 2, "react": 2,
    "next.js": 2, "nextjs": 2, "typescript": 1, "graphql": 1,
    "deployment": 2, "production": 2
}

ENGINEERING_DEPTH_KEYWORDS = {
    "testing": 1, "pytest": 1, "unit test": 1, "integration test": 1,
    "architecture": 1, "design pattern": 1, "clean architecture": 1,
    "caching": 1, "redis": 1, "memcached": 1, "queue": 1,
    "concurrency": 1, "async": 1, "threading": 1, "multiprocessing": 1,
    "observability": 1, "logging": 1, "monitoring": 1, "metrics": 1,
    "tracing": 1, "error handling": 1, "retry": 1, "circuit breaker": 1,
    "performance": 1, "optimization": 1, "profiling": 1
}

AI_DEPTH_KEYWORDS = {
    "rag": 5, "retrieval augmented generation": 5, "embedding": 4,
    "vector search": 4, "vector database": 4, "langchain": 4, "langgraph": 5,
    "llamaindex": 4, "llama-index": 4, "agent": 5, "tool calling": 4,
    "orchestration": 4, "multi-agent": 5, "workflow": 3, "state management": 4,
    "evaluation": 4, "prompt engineering": 2, "fine-tuning": 4, "lora": 3,
    "llm": 2, "large language model": 2, "openai": 1, "anthropic": 1,
    "gemini": 1, "huggingface": 2, "transformers": 3, "vllm": 3, "ollama": 2,
    "pinecone": 2, "weaviate": 2, "chromadb": 2, "faiss": 2, "milvus": 2,
    "qdrant": 2, "semantic search": 3, "similarity search": 3,
    "knowledge base": 3, "document retrieval": 3, "agentic": 5,
    "autonomous agent": 5, "chain of thought": 3, "reasoning": 3, "planning": 3
}

SHALLOW_PENALTY_KEYWORDS = [
    "chatgpt wrapper", "simple api call", "basic prompt", "hello world",
    "tutorial", "course project", "assignment", "bootcamp", "learning exercise",
    "just calls api", "only prompt", "no retrieval", "no embedding", "no vector"
]


class Scorer:
    def __init__(self):
        self.weights = config.scoring_weights

    def _count_keyword_matches(self, text: str, keywords: Dict[str, int], projects: List[Dict]) -> tuple[int, List[str]]:
        text_lower = text.lower()
        score = 0
        evidence = []

        for kw, weight in keywords.items():
            if kw in text_lower:
                score += weight
                idx = text_lower.index(kw)
                context = text[max(0, idx-100):idx+100].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in projects:
            desc = project.get("description", "").lower()
            title = project.get("title", "").lower()
            techs = [t.lower() for t in project.get("technologies", [])]
            proj_text = f"{title} {desc} {' '.join(techs)}"

            for kw, weight in keywords.items():
                if kw in proj_text:
                    score += weight
                    proj_info = f"{project.get('title', '')}: {project.get('description', '')[:150]}"
                    if proj_info not in evidence:
                        evidence.append(proj_info)

        return min(score, sum(keywords.values())), evidence[:5]

    def score_ai_project_depth(self, candidate: Candidate) -> tuple[int, List[str]]:
        score, evidence = self._count_keyword_matches(
            candidate.extracted_text, AI_DEPTH_KEYWORDS, candidate.projects
        )
        max_score = self.weights["ai_project_depth"]
        return min(score, max_score), evidence

    def score_python_backend(self, candidate: Candidate) -> tuple[int, List[str]]:
        score, evidence = self._count_keyword_matches(
            candidate.extracted_text, PYTHON_BACKEND_KEYWORDS, candidate.projects
        )
        max_score = self.weights["python_backend"]
        return min(score, max_score), evidence

    def score_cloud_fullstack(self, candidate: Candidate) -> tuple[int, List[str]]:
        score, evidence = self._count_keyword_matches(
            candidate.extracted_text, CLOUD_FULLSTACK_KEYWORDS, candidate.projects
        )
        max_score = self.weights["cloud_fullstack"]
        return min(score, max_score), evidence

    def score_engineering_depth(self, candidate: Candidate) -> tuple[int, List[str]]:
        score, evidence = self._count_keyword_matches(
            candidate.extracted_text, ENGINEERING_DEPTH_KEYWORDS, candidate.projects
        )
        max_score = self.weights["engineering_depth"]
        return min(score, max_score), evidence

    def check_shallow_penalty(self, candidate: Candidate) -> tuple[bool, int, str]:
        text_lower = candidate.extracted_text.lower()

        for kw in SHALLOW_PENALTY_KEYWORDS:
            if kw in text_lower:
                idx = text_lower.index(kw)
                context = candidate.extracted_text[max(0, idx-150):idx+150].strip()
                return True, config.shallow_penalty_max, f"Shallow AI indicator: '{kw}' - {context[:100]}"

        for project in candidate.projects:
            desc = project.get("description", "").lower()
            title = project.get("title", "").lower()
            for kw in SHALLOW_PENALTY_KEYWORDS:
                if kw in desc or kw in title:
                    return True, config.shallow_penalty_max, f"Shallow project: {project.get('title', '')}"

        ai_evidence_count = len(candidate.ai_evidence)
        python_evidence_count = len(candidate.python_evidence)
        project_count = len([p for p in candidate.projects if p.get("description")])

        if ai_evidence_count <= 1 and python_evidence_count <= 1 and project_count <= 1:
            return True, config.shallow_penalty_min, "Limited project evidence - possible thin wrapper"

        return False, 0, ""

    def calculate_deterministic_score(self, candidate: Candidate) -> Candidate:
        sb = candidate.score_breakdown

        ai_score, ai_evidence = self.score_ai_project_depth(candidate)
        sb.ai_project_depth = ai_score
        candidate.strengths.extend([f"AI: {e[:80]}" for e in ai_evidence[:2]])

        python_score, python_evidence = self.score_python_backend(candidate)
        sb.python_backend = python_score
        candidate.strengths.extend([f"Python: {e[:80]}" for e in python_evidence[:2]])

        cloud_score, cloud_evidence = self.score_cloud_fullstack(candidate)
        sb.cloud_fullstack = cloud_score
        if cloud_evidence:
            candidate.strengths.extend([f"Cloud/FS: {e[:80]}" for e in cloud_evidence[:1]])

        eng_score, eng_evidence = self.score_engineering_depth(candidate)
        sb.engineering_depth = eng_score

        is_shallow, penalty, reason = self.check_shallow_penalty(candidate)
        if is_shallow:
            candidate.concerns.append(reason)
            sb.penalty = penalty
            sb.update_totals()
            candidate.total_score = sb.final_total
        else:
            sb.update_totals()
            candidate.total_score = sb.total

        candidate.total_score = min(candidate.total_score, config.total_max_score)
        return candidate

    def generate_summary(self, candidate: Candidate) -> Candidate:
        parts = []
        sb = candidate.score_breakdown

        if candidate.projects:
            top_projects = sorted(
                candidate.projects,
                key=lambda p: len(p.get("description", "")),
                reverse=True
            )[:2]
            for p in top_projects:
                title = p.get("title", "Project")
                desc = p.get("description", "").strip()
                # Truncate at sentence boundary if possible
                if len(desc) > 200:
                    # Find last period before 200 chars
                    cutoff = desc[:200].rfind('.')
                    if cutoff > 50:
                        desc = desc[:cutoff + 1]
                    else:
                        desc = desc[:200] + "..."
                techs = p.get("technologies", [])
                if techs:
                    parts.append(f"{title} ({', '.join(techs[:4])}): {desc}")
                else:
                    parts.append(f"{title}: {desc}")

        if candidate.ai_evidence:
            ai_desc = candidate.ai_evidence[0].strip()
            if len(ai_desc) > 200:
                cutoff = ai_desc[:200].rfind('.')
                if cutoff > 50:
                    ai_desc = ai_desc[:cutoff + 1]
                else:
                    ai_desc = ai_desc[:200] + "..."
            parts.append(f"AI work: {ai_desc}")

        candidate.project_summary = " | ".join(parts) if parts else "No detailed project information extracted"

        # Deduplicate strengths while preserving order
        seen = set()
        unique_strengths = []
        for s in candidate.strengths:
            s_clean = s.strip()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                unique_strengths.append(s_clean)
        candidate.strengths = unique_strengths[:5]  # Cap at 5

        if not candidate.strengths:
            if sb.ai_project_depth > 20:
                candidate.strengths.append("Strong AI/agentic project depth")
            if sb.python_backend > 15:
                candidate.strengths.append("Solid Python backend experience")
            if sb.cloud_fullstack > 8:
                candidate.strengths.append("Cloud/deployment experience")

        # Deduplicate concerns
        seen = set()
        unique_concerns = []
        for c in candidate.concerns:
            c_clean = c.strip()
            if c_clean and c_clean not in seen:
                seen.add(c_clean)
                unique_concerns.append(c_clean)
        candidate.concerns = unique_concerns[:5]

        if not candidate.concerns:
            if sb.ai_project_depth < 15:
                candidate.concerns.append("Limited AI project depth")
            if sb.python_backend < 10:
                candidate.concerns.append("Limited Python backend evidence")
            if sb.github == 0:
                candidate.concerns.append("No GitHub activity signal")

        return candidate


scorer = Scorer()