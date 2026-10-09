#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

from src.pipeline import run_screening
from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AI Resume Screening & Ranking System")
    parser.add_argument("--input", "-i", default=config.input_dir, help="Input directory containing PDF resumes")
    parser.add_argument("--output", "-o", default=config.output_dir, help="Output directory for results")
    parser.add_argument("--format", "-f", choices=["json", "csv", "both"], default="both", help="Output format")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM enhancement")
    parser.add_argument("--no-github", action="store_true", help="Disable GitHub enrichment")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input directory does not exist: {args.input}")
        sys.exit(1)

    if not input_path.is_dir():
        logger.error(f"Input path is not a directory: {args.input}")
        sys.exit(1)

    pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {args.input}")

    logger.info(f"Starting screening with {len(pdf_files)} resume(s)")
    logger.info(f"LLM: {'enabled' if not args.no_llm else 'disabled'}, GitHub: {'enabled' if not args.no_github else 'disabled'}")

    try:
        result = run_screening(
            input_dir=args.input,
            output_dir=args.output,
            use_llm=not args.no_llm,
            use_github=not args.no_github
        )

        print("\n" + "=" * 60)
        print("SCREENING COMPLETE")
        print("=" * 60)
        print(f"Total resumes discovered: {result.batch_summary.total_discovered}")
        print(f"Duplicate files: {result.batch_summary.duplicate_files}")
        print(f"Successfully parsed: {result.batch_summary.successfully_parsed}")
        print(f"Eligible candidates: {result.batch_summary.eligible_candidates}")
        print(f"Rejected candidates: {result.batch_summary.rejected_candidates}")
        print(f"Failed/unreadable: {result.batch_summary.failed_resumes}")
        print(f"\nResults saved to: {Path(args.output) / config.results_file}")

        eligible = [c for c in result.candidates if c.eligible]
        if eligible:
            print(f"\nTop {min(5, len(eligible))} Candidates:")
            for c in eligible[:5]:
                name = c.candidate_name.replace('\u200b', '').replace('\ufeff', '')
                summary = c.project_summary.replace('\u200b', '').replace('\ufeff', '')
                print(f"  #{c.rank}: {name} - Score: {c.total_score}/100")
                if summary:
                    print(f"      {summary[:100]}...")

        sys.exit(0)

    except Exception as e:
        logger.exception("Screening failed")
        sys.exit(1)


if __name__ == "__main__":
    main()