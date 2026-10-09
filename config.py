import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    input_dir: str = "./resumes/resume_data/resumes"
    output_dir: str = "./output"
    results_file: str = "results.json"

    github_token: Optional[str] = None
    github_timeout: int = 10
    github_max_retries: int = 2

    llm_api_key: Optional[str] = None
    llm_model: str = "gemini-3-flash-preview"
    llm_provider: str = "gemini"
    llm_timeout: int = 30
    llm_max_retries: int = 2
    llm_temperature: float = 0.1
    llm_max_tokens: int = 8192

    scoring_weights: dict = None
    shallow_penalty_min: int = 5
    shallow_penalty_max: int = 15
    tie_breaker_fields: list = None

    def __post_init__(self):
        if self.scoring_weights is None:
            self.scoring_weights = {
                "ai_project_depth": 40,
                "python_backend": 30,
                "cloud_fullstack": 15,
                "github": 10,
                "engineering_depth": 5,
            }
        if self.tie_breaker_fields is None:
            self.tie_breaker_fields = [
                "ai_project_depth",
                "python_backend",
                "cloud_fullstack",
                "github",
                "engineering_depth",
            ]

        self.github_token = self.github_token or os.getenv("GITHUB_TOKEN")
        self.llm_api_key = self.llm_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")

    @property
    def total_max_score(self) -> int:
        return sum(self.scoring_weights.values())


config = Config()