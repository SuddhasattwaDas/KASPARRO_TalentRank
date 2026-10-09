import json
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config import config
from src.models import Candidate, ScoreBreakdown

logger = logging.getLogger(__name__)

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


@dataclass
class LLMResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LLMService:
    def __init__(self):
        self.client = None
        self.enabled = False
        self._init_client()

    def _init_client(self):
        if not GEMINI_AVAILABLE:
            logger.warning("google-genai not installed, LLM features disabled")
            return

        api_key = config.llm_api_key
        if not api_key:
            logger.info("No LLM API key provided, LLM features disabled")
            return

        try:
            self.client = genai.Client(api_key=api_key)
            self.enabled = True
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")

    def _create_extraction_prompt(self, text: str) -> str:
        return f"""Extract structured information from this resume. Return ONLY valid JSON.

Resume text:
{text[:8000]}

Return JSON with these fields:
- "candidate_name": string
- "email": string or null
- "phone": string or null
- "github_url": string or null
- "skills": array of strings (technical skills only)
- "projects": array of objects with "title", "description", "technologies" (array)
- "python_evidence": array of strings showing Python usage in projects/work
- "ai_evidence": array of strings showing AI/agentic/RAG/ML project work
- "summary": string (2-3 sentence professional summary)"""

    def _create_scoring_prompt(self, candidate: Candidate) -> str:
        return f"""Score this candidate for an SDE Intern role requiring Python + AI/agentic systems.

Candidate: {candidate.candidate_name}
Skills: {candidate.matched_skills}
Projects: {json.dumps(candidate.projects, indent=2)}
Python Evidence: {candidate.python_evidence}
AI Evidence: {candidate.ai_evidence}

Score each category (0-max) with evidence. Return ONLY valid JSON:

{{
  "ai_project_depth": {{"score": 0-40, "evidence": "..."}},
  "python_backend": {{"score": 0-30, "evidence": "..."}},
  "cloud_fullstack": {{"score": 0-15, "evidence": "..."}},
  "engineering_depth": {{"score": 0-5, "evidence": "..."}},
  "shallow_penalty": {{"apply": true/false, "points": 5-15, "reason": "..."}},
  "project_summary": "2-3 sentence summary of key AI/engineering work",
  "strengths": ["strength1", "strength2"],
  "concerns": ["concern1", "concern2"]
}}"""

    def extract_candidate_info(self, candidate: Candidate) -> LLMResponse:
        if not self.enabled:
            return LLMResponse(success=False, error="LLM not configured")

        try:
            prompt = self._create_extraction_prompt(candidate.extracted_text)
            response = self.client.models.generate_content(
                model=config.llm_model,
                contents=prompt,
                config={
                    "temperature": config.llm_temperature,
                    "max_output_tokens": config.llm_max_tokens,
                }
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()

            data = json.loads(text)
            return LLMResponse(success=True, data=data)

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            return LLMResponse(success=False, error=f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return LLMResponse(success=False, error=str(e))

    def score_candidate(self, candidate: Candidate) -> LLMResponse:
        if not self.enabled:
            return LLMResponse(success=False, error="LLM not configured")

        try:
            prompt = self._create_scoring_prompt(candidate)
            response = self.client.models.generate_content(
                model=config.llm_model,
                contents=prompt,
                config={
                    "temperature": config.llm_temperature,
                    "max_output_tokens": config.llm_max_tokens,
                }
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()

            data = json.loads(text)
            return LLMResponse(success=True, data=data)

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON for scoring: {e}")
            return LLMResponse(success=False, error=f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM scoring failed: {e}")
            return LLMResponse(success=False, error=str(e))

    def enhance_candidate(self, candidate: Candidate) -> Candidate:
        if not self.enabled:
            return candidate

        extraction = self.extract_candidate_info(candidate)
        if extraction.success and extraction.data:
            data = extraction.data
            if data.get("candidate_name") and data["candidate_name"] != "Unknown Candidate":
                candidate.candidate_name = data["candidate_name"]
            if data.get("email"):
                candidate.email = data["email"]
            if data.get("phone"):
                candidate.phone = data["phone"]
            if data.get("github_url"):
                candidate.github_url = data["github_url"]
            if data.get("skills"):
                candidate.matched_skills = list(set(candidate.matched_skills + data["skills"]))
            if data.get("projects"):
                candidate.projects = data["projects"]
            if data.get("python_evidence"):
                candidate.python_evidence = list(set(candidate.python_evidence + data["python_evidence"]))
            if data.get("ai_evidence"):
                candidate.ai_evidence = list(set(candidate.ai_evidence + data["ai_evidence"]))

        return candidate

    def score_with_llm(self, candidate: Candidate) -> Candidate:
        if not self.enabled:
            return candidate

        scoring = self.score_candidate(candidate)
        if scoring.success and scoring.data:
            data = scoring.data

            sb = candidate.score_breakdown
            if "ai_project_depth" in data:
                sb.ai_project_depth = max(0, min(40, data["ai_project_depth"].get("score", 0)))
            if "python_backend" in data:
                sb.python_backend = max(0, min(30, data["python_backend"].get("score", 0)))
            if "cloud_fullstack" in data:
                sb.cloud_fullstack = max(0, min(15, data["cloud_fullstack"].get("score", 0)))
            if "engineering_depth" in data:
                sb.engineering_depth = max(0, min(5, data["engineering_depth"].get("score", 0)))

            shallow = data.get("shallow_penalty", {})
            if shallow.get("apply"):
                penalty = min(config.shallow_penalty_max, max(config.shallow_penalty_min, shallow.get("points", 0)))
                sb.penalty = penalty
                candidate.total_score = max(0, sb.total - penalty)
                candidate.concerns.append(f"Shallow project penalty: {shallow.get('reason', 'Thin AI wrapper')}")

            if data.get("project_summary"):
                candidate.project_summary = data["project_summary"]
            if data.get("strengths"):
                candidate.strengths.extend(data["strengths"])
            if data.get("concerns"):
                candidate.concerns.extend(data["concerns"])

        return candidate


llm_service = LLMService()