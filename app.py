import streamlit as st
import json
import subprocess
import sys
import zipfile
import tempfile
import shutil
from pathlib import Path

from config import config

st.set_page_config(
    page_title="TalentRank AI",
    layout="wide",
    initial_sidebar_state="collapsed"
)


@st.cache_data
def load_results(results_path: str = None):
    if results_path is None:
        results_path = Path(config.output_dir) / config.results_file
    else:
        results_path = Path(results_path)

    if not results_path.exists():
        return None

    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_screening_cli(input_dir: str, output_dir: str, use_llm: bool, use_github: bool):
    cmd = [
        sys.executable, "main.py",
        "--input", input_dir,
        "--output", output_dir
    ]
    if not use_llm:
        cmd.append("--no-llm")
    if not use_github:
        cmd.append("--no-github")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    return result.returncode, result.stdout, result.stderr


def extract_zip(uploaded_file, extract_to: Path):
    """Extract uploaded zip file to destination directory."""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(uploaded_file, 'r') as zf:
        zf.extractall(extract_to)
    # Find PDFs recursively
    pdfs = list(extract_to.rglob("*.pdf")) + list(extract_to.rglob("*.PDF"))
    return pdfs


def main():
    st.title("TalentRank AI - Resume Screening")

    if "results" not in st.session_state:
        st.session_state.results = None
    if "screening_done" not in st.session_state:
        st.session_state.screening_done = False
    if "input_dir" not in st.session_state:
        st.session_state.input_dir = config.input_dir

    with st.sidebar:
        st.header("Configuration")
        
        # Zip file upload
        st.subheader("Upload Resumes")
        uploaded = st.file_uploader("Drop ZIP or PDF files", type=["zip", "pdf"], accept_multiple_files=True)
        
        if uploaded:
            pdf_count = 0
            for f in uploaded:
                if f.name.endswith(".zip"):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmpdir = Path(tmpdir)
                        pdfs = extract_zip(f, tmpdir)
                        # Copy to input directory
                        input_path = Path(st.session_state.input_dir)
                        input_path.mkdir(parents=True, exist_ok=True)
                        for pdf in pdfs:
                            dest = input_path / pdf.name
                            shutil.copy2(pdf, dest)
                            pdf_count += 1
                    st.success(f"Extracted {pdf_count} PDFs from {f.name}")
                elif f.name.endswith(".pdf"):
                    input_path = Path(st.session_state.input_dir)
                    input_path.mkdir(parents=True, exist_ok=True)
                    dest = input_path / f.name
                    with open(dest, "wb") as out:
                        out.write(f.read())
                    pdf_count += 1
            if pdf_count:
                st.success(f"Added {pdf_count} PDF(s) to input directory")

        st.divider()
        
        input_dir = st.text_input("Input Directory", value=st.session_state.input_dir)
        st.session_state.input_dir = input_dir
        output_dir = st.text_input("Output Directory", value=config.output_dir)
        use_llm = st.checkbox("Enable LLM", value=bool(config.llm_api_key))
        use_github = st.checkbox("Enable GitHub", value=True)

        if st.button("Run Screening", type="primary"):
            with st.spinner("Processing..."):
                returncode, stdout, stderr = run_screening_cli(input_dir, output_dir, use_llm, use_github)
            if returncode == 0:
                st.session_state.results = load_results()
                st.session_state.screening_done = True
                st.success("Done")
                st.rerun()
            else:
                st.error(stderr)

    if not st.session_state.screening_done or st.session_state.results is None:
        st.info("Upload resumes, configure settings, and click Run Screening.")
        return

    results = st.session_state.results
    batch = results.get("batch_summary", {})
    candidates = results.get("candidates", [])

    eligible = [c for c in candidates if c.get("eligible")]
    rejected = [c for c in candidates if not c.get("eligible") and c.get("eligibility_status") == "rejected"]
    failed = [c for c in candidates if c.get("eligibility_status") == "failed"]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total", batch.get("total_discovered", 0))
    col2.metric("Parsed", batch.get("successfully_parsed", 0))
    col3.metric("Eligible", batch.get("eligible_candidates", 0))
    col4.metric("Rejected", batch.get("rejected_candidates", 0))
    col5.metric("Failed", batch.get("failed_resumes", 0))

    tab1, tab2, tab3 = st.tabs(["Eligible", "Rejected", "Failed"])

    with tab1:
        if not eligible:
            st.write("No eligible candidates.")
        else:
            min_score = st.slider("Min Score", 0, 100, 0)
            skill_filter = st.text_input("Filter Skill")

            filtered = eligible
            if min_score > 0:
                filtered = [c for c in filtered if c.get("total_score", 0) >= min_score]
            if skill_filter:
                filtered = [c for c in filtered if any(skill_filter.lower() in s.lower() for s in c.get("matched_skills", []))]

            st.write(f"Showing {len(filtered)} of {len(eligible)} candidates")

            for c in filtered:
                with st.container():
                    cols = st.columns([1, 3, 1, 2, 1])
                    cols[0].write(f"#{c.get('rank')}")
                    cols[1].write(f"**{c.get('candidate_name', 'Unknown')}**")
                    if c.get("matched_skills"):
                        cols[1].caption(", ".join(c["matched_skills"][:6]))
                    cols[2].write(f"{c.get('total_score', 0)}/100")
                    cols[3].write(c.get("github_enrichment_status", "unknown"))
                    if cols[4].button("View", key=f"view_{c.get('source_filename')}"):
                        st.session_state.selected = c
                        st.rerun()

    with tab2:
        for c in rejected:
            with st.expander(f"{c.get('candidate_name', 'Unknown')} ({c.get('source_filename', '')})"):
                for r in c.get("rejection_reasons", []):
                    st.write("- " + r)

    with tab3:
        for c in failed:
            with st.expander(c.get("source_filename", "Unknown")):
                st.write(c.get("parsing_error", "Unknown error"))

    if "selected" in st.session_state:
        c = st.session_state.selected
        st.divider()
        if st.button("Back"):
            del st.session_state.selected
            st.rerun()

        st.subheader(f"#{c.get('rank')} - {c.get('candidate_name', 'Unknown')}")

        if not c.get("eligible"):
            st.error("Rejected")
            for r in c.get("rejection_reasons", []):
                st.write("- " + r)
        else:
            sb = c.get("score_breakdown", {})
            cats = sb.get("ai_project_depth", 0) + sb.get("python_backend", 0) + sb.get("cloud_fullstack", 0) + sb.get("github", 0) + sb.get("engineering_depth", 0)
            penalty = sb.get("penalty", 0)
            final = sb.get("final_total", c.get('total_score', 0))
            st.write(f"Score: {final}/100  (Categories: {cats}, Penalty: -{penalty})")

            mcols = st.columns(5)
            metrics = [
                ("AI Depth", sb.get("ai_project_depth", 0), 40),
                ("Python", sb.get("python_backend", 0), 30),
                ("Cloud/FS", sb.get("cloud_fullstack", 0), 15),
                ("GitHub", sb.get("github", 0), 10),
                ("Eng Depth", sb.get("engineering_depth", 0), 5)
            ]
            for i, (label, val, mx) in enumerate(metrics):
                mcols[i].metric(label, f"{val}/{mx}")
            if penalty:
                st.caption(f"Penalty applied: -{penalty}")

            st.write("**Summary:**")
            st.write(c.get("project_summary", ""))

            st.write("**GitHub:**")
            st.write(c.get("github_summary", ""))

            st.write("**Strengths:**")
            for s in c.get("strengths", []):
                st.write("- " + s)

            st.write("**Concerns:**")
            for c_ in c.get("concerns", []):
                st.write("- " + c_)

    col1, col2 = st.columns(2)
    with col1:
        rf = Path(config.output_dir) / config.results_file
        if rf.exists():
            with open(rf, "rb") as f:
                st.download_button("Download JSON", f, "results.json")
    with col2:
        cf = Path(config.output_dir) / "results.csv"
        if cf.exists():
            with open(cf, "rb") as f:
                st.download_button("Download CSV", f, "results.csv")


if __name__ == "__main__":
    main()