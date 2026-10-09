import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Set
import fitz

from src.models import Candidate

logger = logging.getLogger(__name__)


class PDFParser:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.seen_hashes: Set[str] = set()

    def _compute_file_hash(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def discover_files(self) -> List[Path]:
        pdf_files = list(self.input_dir.glob("*.pdf"))
        pdf_files.extend(self.input_dir.glob("*.PDF"))
        # Deduplicate case-insensitively (Windows glob returns both)
        seen = set()
        unique_files = []
        for f in pdf_files:
            key = str(f).lower()
            if key not in seen:
                seen.add(key)
                unique_files.append(f)
        return sorted(unique_files)

    def is_duplicate(self, file_path: Path) -> bool:
        file_hash = self._compute_file_hash(file_path)
        if file_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(file_hash)
        return False

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            doc = fitz.open(file_path)
            if doc.is_encrypted:
                logger.warning(f"Encrypted PDF skipped: {file_path.name}")
                return None

            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

            doc.close()
            full_text = "\n".join(text_parts).strip()

            if not full_text:
                logger.warning(f"Empty text extracted from: {file_path.name}")
                return None

            return full_text

        except Exception as e:
            logger.error(f"Failed to parse {file_path.name}: {e}")
            return None

    def parse_all(self) -> List[Candidate]:
        candidates = []
        files = self.discover_files()

        for file_path in files:
            candidate = Candidate(source_filename=file_path.name)

            if self.is_duplicate(file_path):
                candidate.parsing_error = "Duplicate file detected"
                candidate.eligibility_status = "failed"
                candidates.append(candidate)
                continue

            text = self.extract_text(file_path)
            if text is None:
                candidate.parsing_error = "Failed to extract text (encrypted, empty, or corrupt)"
                candidate.eligibility_status = "failed"
                candidates.append(candidate)
                continue

            candidate.extracted_text = text
            candidate.eligibility_status = "rejected"
            candidates.append(candidate)

        return candidates