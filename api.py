from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import json
import logging

from src.pipeline import run_screening, ScreeningPipeline
from config import config
from src.models import ScreeningResult

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TalentRank AI - Resume Screening API",
    description="AI-powered resume screening and ranking for SDE internships",
    version="1.0.0"
)

_latest_result: Optional[ScreeningResult] = None
_screening_status = {"status": "idle", "message": ""}


class ScreenRequest(BaseModel):
    input_dir: str = config.input_dir
    output_dir: str = config.output_dir
    use_llm: bool = True
    use_github: bool = True


class ScreenResponse(BaseModel):
    status: str
    message: str
    batch_summary: Optional[dict] = None


@app.get("/")
async def root():
    return {"service": "TalentRank AI", "version": "1.0.0", "endpoints": ["/screen", "/results", "/health"]}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "TalentRank AI"}


@app.post("/screen", response_model=ScreenResponse)
async def screen_resumes(request: ScreenRequest, background_tasks: BackgroundTasks):
    global _screening_status
    if _screening_status["status"] == "running":
        raise HTTPException(status_code=409, detail="Screening already in progress")

    _screening_status = {"status": "running", "message": "Starting screening..."}

    def run_in_background():
        global _latest_result, _screening_status
        try:
            _screening_status["message"] = "Processing resumes..."
            result = run_screening(
                input_dir=request.input_dir,
                output_dir=request.output_dir,
                use_llm=request.use_llm,
                use_github=request.use_github
            )
            _latest_result = result
            _screening_status = {
                "status": "completed",
                "message": f"Screening complete. {result.batch_summary.eligible_candidates} eligible, {result.batch_summary.rejected_candidates} rejected."
            }
        except Exception as e:
            logger.exception("Background screening failed")
            _screening_status = {"status": "failed", "message": str(e)}

    background_tasks.add_task(run_in_background)
    return ScreenResponse(status="started", message="Screening started in background")


@app.get("/screen/status")
async def screen_status():
    return _screening_status


@app.get("/results")
async def get_results():
    global _latest_result
    if _latest_result is None:
        output_file = Path(config.output_dir) / config.results_file
        if output_file.exists():
            with open(output_file) as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="No results available. Run screening first.")

    return {
        "generated_at": _latest_result.batch_summary.__dict__.get("generated_at", ""),
        "batch_summary": _latest_result.batch_summary.model_dump(),
        "candidates": [c.model_dump() for c in _latest_result.candidates]
    }


@app.get("/results/download")
async def download_results(format: str = "json"):
    output_file = Path(config.output_dir) / config.results_file
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="No results file found")

    if format == "json":
        return FileResponse(output_file, media_type="application/json", filename="results.json")
    elif format == "csv":
        csv_file = Path(config.output_dir) / "results.csv"
        if csv_file.exists():
            return FileResponse(csv_file, media_type="text/csv", filename="results.csv")
        raise HTTPException(status_code=404, detail="CSV file not found")
    else:
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")


@app.get("/candidates/eligible")
async def get_eligible_candidates(min_score: int = 0):
    global _latest_result
    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No results available")

    eligible = [c for c in _latest_result.candidates if c.eligible and c.total_score >= min_score]
    return {"count": len(eligible), "candidates": [c.model_dump() for c in eligible]}


@app.get("/candidates/rejected")
async def get_rejected_candidates():
    global _latest_result
    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No results available")

    rejected = [c for c in _latest_result.candidates if not c.eligible and c.eligibility_status == "rejected"]
    return {"count": len(rejected), "candidates": [c.model_dump() for c in rejected]}


@app.get("/candidates/{rank}")
async def get_candidate_by_rank(rank: int):
    global _latest_result
    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No results available")

    for c in _latest_result.candidates:
        if c.rank == rank:
            return c.model_dump()

    raise HTTPException(status_code=404, detail=f"Candidate with rank {rank} not found")