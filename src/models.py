from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    FAILED = "failed"


class GitHubEnrichmentStatus(str, Enum):
    SUCCESS = "success"
    NO_PROFILE = "no_profile"
    PRIVATE = "private"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    NOT_ATTEMPTED = "not_attempted"


class ScoreBreakdown(BaseModel):
    ai_project_depth: int = Field(ge=0, le=40, default=0)
    python_backend: int = Field(ge=0, le=30, default=0)
    cloud_fullstack: int = Field(ge=0, le=15, default=0)
    github: int = Field(ge=0, le=10, default=0)
    engineering_depth: int = Field(ge=0, le=5, default=0)
    penalty: int = Field(ge=0, le=15, default=0)
    github_activity: int = Field(ge=0, le=5, default=0)
    github_repo_quality: int = Field(ge=0, le=5, default=0)
    total: int = Field(default=0)
    final_total: int = Field(default=0)

    def update_totals(self):
        self.total = (
            self.ai_project_depth
            + self.python_backend
            + self.cloud_fullstack
            + self.github
            + self.engineering_depth
        )
        self.final_total = max(0, self.total - self.penalty)


class Candidate(BaseModel):
    candidate_name: str = ""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source_filename: str = ""
    extracted_text: str = ""
    matched_skills: List[str] = Field(default_factory=list)
    python_evidence: List[str] = Field(default_factory=list)
    ai_evidence: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    github_url: Optional[str] = None
    github_username: Optional[str] = None

    eligible: bool = False
    rejection_reasons: List[str] = Field(default_factory=list)
    eligibility_status: EligibilityStatus = EligibilityStatus.REJECTED

    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    total_score: int = 0
    rank: Optional[int] = None

    project_summary: str = ""
    github_summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)

    github_enrichment_status: GitHubEnrichmentStatus = GitHubEnrichmentStatus.NOT_ATTEMPTED
    github_enrichment_error: Optional[str] = None
    github_data: Dict[str, Any] = Field(default_factory=dict)

    parsing_error: Optional[str] = None

    class Config:
        use_enum_values = True


class BatchSummary(BaseModel):
    total_discovered: int = 0
    duplicate_files: int = 0
    successfully_parsed: int = 0
    eligible_candidates: int = 0
    rejected_candidates: int = 0
    failed_resumes: int = 0


class ScreeningResult(BaseModel):
    candidates: List[Candidate] = Field(default_factory=list)
    batch_summary: BatchSummary = Field(default_factory=BatchSummary)