import logging
from typing import List, Tuple

from src.models import Candidate

logger = logging.getLogger(__name__)

PYTHON_INDICATORS = [
    "python", "fastapi", "django", "flask", "pydantic", "asyncio",
    "sqlalchemy", "pytest", "pandas", "numpy", "scikit-learn",
    "tensorflow", "pytorch", "aiohttp", "alembic", "uvicorn", "gunicorn", "celery", "redis-py",
    "pip", "conda", "poetry", "pipenv", "virtualenv", "jupyter", "ipython"
]

AI_INDICATORS = [
    "rag", "retrieval augmented", "embedding", "vector search", "vector database",
    "langchain", "langgraph", "llamaindex", "llama-index", "agent", "tool calling",
    "orchestration", "multi-agent", "workflow", "state management", "evaluation",
    "prompt engineering", "fine-tuning", "lora", "llm", "large language model",
    "openai", "anthropic", "gemini", "huggingface", "transformers", "vllm", "ollama",
    "pinecone", "weaviate", "chromadb", "faiss", "milvus", "qdrant",
    "semantic search", "similarity search", "knowledge base", "document retrieval",
    "agentic", "autonomous agent", "chain of thought", "reasoning", "planning"
]

SHALLOW_AI_INDICATORS = [
    "chatgpt wrapper", "simple api call", "basic prompt", "hello world",
    "tutorial", "course project", "assignment", "bootcamp", "learning exercise"
]


class EligibilityChecker:
    def __init__(self):
        self.python_keywords = set(kw.lower() for kw in PYTHON_INDICATORS)
        self.ai_keywords = set(kw.lower() for kw in AI_INDICATORS)
        self.shallow_keywords = set(kw.lower() for kw in SHALLOW_AI_INDICATORS)

    def check_python_evidence(self, candidate: Candidate) -> Tuple[bool, List[str]]:
        evidence = []
        text_lower = candidate.extracted_text.lower()
        skills_lower = [s.lower() for s in candidate.matched_skills]

        for kw in self.python_keywords:
            if kw in text_lower:
                idx = text_lower.index(kw)
                context = candidate.extracted_text[max(0, idx-80):idx+80].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in candidate.projects:
            techs = [t.lower() for t in project.get("technologies", [])]
            desc = project.get("description", "").lower()
            if any(pkw in techs or pkw in desc for pkw in self.python_keywords):
                proj_desc = project.get("description", "")[:200]
                if proj_desc and proj_desc not in evidence:
                    evidence.append(proj_desc)

        has_python = len(evidence) > 0
        return has_python, evidence[:5]

    def check_ai_evidence(self, candidate: Candidate) -> Tuple[bool, List[str]]:
        evidence = []
        text_lower = candidate.extracted_text.lower()
        skills_lower = [s.lower() for s in candidate.matched_skills]

        for kw in self.ai_keywords:
            if kw in text_lower:
                idx = text_lower.index(kw)
                context = candidate.extracted_text[max(0, idx-100):idx+100].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in candidate.projects:
            techs = [t.lower() for t in project.get("technologies", [])]
            desc = project.get("description", "").lower()
            title = project.get("title", "").lower()
            if any(akw in techs or akw in desc or akw in title for akw in self.ai_keywords):
                proj_info = f"{project.get('title', '')}: {project.get('description', '')[:200]}"
                if proj_info not in evidence:
                    evidence.append(proj_info)

        has_ai = len(evidence) > 0
        return has_ai, evidence[:5]

    def check_shallow_ai(self, candidate: Candidate) -> Tuple[bool, List[str]]:
        evidence = []
        text_lower = candidate.extracted_text.lower()

        for kw in self.shallow_keywords:
            if kw in text_lower:
                idx = text_lower.index(kw)
                context = candidate.extracted_text[max(0, idx-100):idx+100].strip()
                if context not in evidence:
                    evidence.append(context)

        for project in candidate.projects:
            desc = project.get("description", "").lower()
            title = project.get("title", "").lower()
            if any(skw in desc or skw in title for skw in self.shallow_keywords):
                proj_info = f"{project.get('title', '')}: {project.get('description', '')[:200]}"
                if proj_info not in evidence:
                    evidence.append(proj_info)

        is_shallow = len(evidence) > 0
        return is_shallow, evidence[:3]

    def evaluate(self, candidate: Candidate) -> Candidate:
        if candidate.parsing_error:
            candidate.eligible = False
            candidate.eligibility_status = "failed"
            candidate.rejection_reasons = [candidate.parsing_error]
            return candidate

        has_python, python_evidence = self.check_python_evidence(candidate)
        has_ai, ai_evidence = self.check_ai_evidence(candidate)
        is_shallow, shallow_evidence = self.check_shallow_ai(candidate)

        candidate.python_evidence = python_evidence
        candidate.ai_evidence = ai_evidence

        rejection_reasons = []
        if not has_python:
            rejection_reasons.append("No evidence of Python stack")
        if not has_ai:
            rejection_reasons.append("No meaningful AI/agentic project evidence")

        if has_python and has_ai:
            candidate.eligible = True
            candidate.eligibility_status = "eligible"
        else:
            candidate.eligible = False
            candidate.eligibility_status = "rejected"
            candidate.rejection_reasons = rejection_reasons

        if is_shallow:
            candidate.concerns.append("AI project appears to be shallow/tutorial-level")

        logger.info(f"Candidate {candidate.candidate_name}: eligible={candidate.eligible}, reasons={rejection_reasons}")
        return candidate