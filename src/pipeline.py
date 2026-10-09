import logging
import json
import csv
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from config import config
from src.models import Candidate, ScreeningResult, BatchSummary, EligibilityStatus, GitHubEnrichmentStatus
from src.parser import PDFParser
from src.extractor import CandidateExtractor
from src.eligibility import EligibilityChecker
from src.scorer import Scorer
from src.github_client import github_client, GitHubData
from src.llm_service import llm_service

logger = logging.getLogger(__name__)


class ScreeningPipeline:
    def __init__(self, input_dir: str = None, output_dir: str = None, use_llm: bool = True, use_github: bool = True):
        self.input_dir = input_dir or config.input_dir
        self.output_dir = Path(output_dir or config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.parser = PDFParser(self.input_dir)
        self.extractor = CandidateExtractor()
        self.eligibility_checker = EligibilityChecker()
        self.scorer = Scorer()
        self.use_llm = use_llm and llm_service.enabled
        self.use_github = use_github

        if not self.use_llm:
            logger.info("LLM enhancement disabled")
        if not self.use_github:
            logger.info("GitHub enrichment disabled")

    def run(self) -> ScreeningResult:
        logger.info("Starting screening pipeline")

        candidates = self.parser.parse_all()
        logger.info(f"Discovered {len(candidates)} resume files")

        batch_summary = BatchSummary(
            total_discovered=len(candidates),
            duplicate_files=sum(1 for c in candidates if c.parsing_error == "Duplicate file detected"),
            successfully_parsed=sum(1 for c in candidates if not c.parsing_error),
            failed_resumes=sum(1 for c in candidates if c.parsing_error and c.parsing_error != "Duplicate file detected")
        )

        for candidate in candidates:
            if candidate.parsing_error:
                continue

            self.extractor.extract_all(candidate)
            self.eligibility_checker.evaluate(candidate)

        eligible_candidates = [c for c in candidates if c.eligible]
        rejected_candidates = [c for c in candidates if not c.eligible and c.eligibility_status == "rejected"]
        failed_candidates = [c for c in candidates if c.eligibility_status == "failed"]

        batch_summary.eligible_candidates = len(eligible_candidates)
        batch_summary.rejected_candidates = len(rejected_candidates)

        logger.info(f"Eligible: {len(eligible_candidates)}, Rejected: {len(rejected_candidates)}, Failed: {len(failed_candidates)}")

        for candidate in eligible_candidates:
            self._process_eligible_candidate(candidate)

        ranked = self._rank_candidates(eligible_candidates)
        all_candidates = ranked + rejected_candidates + failed_candidates

        result = ScreeningResult(candidates=all_candidates, batch_summary=batch_summary)
        self._save_results(result)

        logger.info("Screening pipeline completed")
        return result

    def _process_eligible_candidate(self, candidate: Candidate):
        self.scorer.calculate_deterministic_score(candidate)

        if self.use_llm:
            llm_service.enhance_candidate(candidate)
            self.scorer.calculate_deterministic_score(candidate)
            llm_service.score_with_llm(candidate)

        if self.use_github and candidate.github_username:
            self._enrich_github(candidate)
        elif self.use_github:
            candidate.github_enrichment_status = GitHubEnrichmentStatus.NO_PROFILE
            candidate.github_summary = "No GitHub profile found in resume"
        else:
            candidate.github_enrichment_status = GitHubEnrichmentStatus.NOT_ATTEMPTED
            candidate.github_summary = "GitHub enrichment skipped"

        self.scorer.generate_summary(candidate)

    def _enrich_github(self, candidate: Candidate):
        try:
            github_data = github_client.enrich(candidate.github_username)
            candidate.github_data = {
                "username": github_data.username,
                "public_repos": github_data.public_repos,
                "recent_activity": github_data.recent_activity,
                "recent_commits": github_data.recent_commits,
                "relevant_repos": github_data.relevant_repos,
                "repo_names": github_data.repo_names
            }

            if github_data.error:
                if "rate_limited" in github_data.error:
                    candidate.github_enrichment_status = GitHubEnrichmentStatus.RATE_LIMITED
                elif "not_found" in github_data.error:
                    candidate.github_enrichment_status = GitHubEnrichmentStatus.NO_PROFILE
                elif "private" in github_data.error or "forbidden" in github_data.error:
                    candidate.github_enrichment_status = GitHubEnrichmentStatus.PRIVATE
                else:
                    candidate.github_enrichment_status = GitHubEnrichmentStatus.ERROR
                candidate.github_enrichment_error = github_data.error
                candidate.github_summary = f"GitHub enrichment failed: {github_data.error}"
                candidate.score_breakdown.github = 0
                candidate.score_breakdown.github_activity = 0
                candidate.score_breakdown.github_repo_quality = 0
            else:
                candidate.github_enrichment_status = GitHubEnrichmentStatus.SUCCESS
                github_score, activity_score, repo_score, github_reason = github_client.score_github(github_data)
                candidate.score_breakdown.github = github_score
                candidate.score_breakdown.github_activity = activity_score
                candidate.score_breakdown.github_repo_quality = repo_score
                candidate.github_summary = github_reason
                # Recalculate totals after GitHub score is set
                candidate.score_breakdown.update_totals()
                candidate.total_score = candidate.score_breakdown.final_total

        except Exception as e:
            logger.error(f"GitHub enrichment error for {candidate.github_username}: {e}")
            candidate.github_enrichment_status = GitHubEnrichmentStatus.ERROR
            candidate.github_enrichment_error = str(e)
            candidate.github_summary = f"GitHub enrichment error: {e}"
            candidate.score_breakdown.github = 0

    def _rank_candidates(self, candidates: List[Candidate]) -> List[Candidate]:
        def sort_key(c: Candidate):
            # Sort by final total score descending, then by name ascending for deterministic tie-breaking
            return (-c.total_score, c.candidate_name.lower())

        ranked = sorted(candidates, key=sort_key)
        for i, candidate in enumerate(ranked, 1):
            candidate.rank = i
        return ranked

    def _save_results(self, result: ScreeningResult):
        output_file = self.output_dir / config.results_file

        json_data = {
            "generated_at": datetime.now().isoformat(),
            "batch_summary": result.batch_summary.model_dump(),
            "candidates": [c.model_dump() for c in result.candidates]
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, default=str)

        logger.info(f"Results saved to {output_file}")

        csv_file = self.output_dir / "results.csv"
        self._save_csv(result, csv_file)

    def _save_csv(self, result: ScreeningResult, csv_file: Path):
        fieldnames = [
            "rank", "candidate_name", "email", "source_filename", "eligible",
            "total_score", "ai_project_depth", "python_backend", "cloud_fullstack",
            "github", "github_activity", "github_repo_quality", "engineering_depth", "penalty",
            "matched_skills", "project_summary",
            "github_summary", "strengths", "concerns", "rejection_reasons",
            "github_enrichment_status", "parsing_error"
        ]

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for c in result.candidates:
                sb = c.score_breakdown
                writer.writerow({
                    "rank": c.rank or "",
                    "candidate_name": c.candidate_name,
                    "email": c.email or "",
                    "source_filename": c.source_filename,
                    "eligible": c.eligible,
                    "total_score": c.total_score if c.eligible else "",
                    "ai_project_depth": sb.ai_project_depth,
                    "python_backend": sb.python_backend,
                    "cloud_fullstack": sb.cloud_fullstack,
                    "github": sb.github,
                    "github_activity": sb.github_activity,
                    "github_repo_quality": sb.github_repo_quality,
                    "engineering_depth": sb.engineering_depth,
                    "penalty": sb.penalty,
                    "matched_skills": "; ".join(c.matched_skills),
                    "project_summary": c.project_summary,
                    "github_summary": c.github_summary,
                    "strengths": "; ".join(c.strengths),
                    "concerns": "; ".join(c.concerns),
                    "rejection_reasons": "; ".join(c.rejection_reasons),
                    "github_enrichment_status": c.github_enrichment_status,
                    "parsing_error": c.parsing_error or ""
                })

        logger.info(f"CSV results saved to {csv_file}")


def run_screening(input_dir: str, output_dir: str, use_llm: bool = True, use_github: bool = True) -> ScreeningResult:
    pipeline = ScreeningPipeline(input_dir, output_dir, use_llm, use_github)
    return pipeline.run()