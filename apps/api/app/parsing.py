"""Turn an uploaded or pasted document into numbered lines.

Line numbers are what later steps cite as evidence, so a "line" should be one
thing a person would point at: a heading, a bullet, a sentence-sized statement.
"""

import io
import re
import unicodedata
from pathlib import PurePath

import pdfplumber
from pydantic import BaseModel

from app.pdf_layout import page_lines

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")
MAX_PDF_PAGES = 15
MAX_LINES = 1500
MAX_LINE_CHARS = 400
MAX_HEADING_CHARS = 40
PDF_MAGIC = b"%PDF-"

BULLET_RE = re.compile(r"^\s*(?:[•●▪‣◦∙·*\-–]|\d{1,2}[.)])\s+")
SENTENCE_END_RE = re.compile(r"(?<=[.!?;])\s+")
# Only known names count as headings. Guessing from capitals would turn skills such
# as "AWS" or "SQL" into headings, which is worse than missing an unusual one.
KNOWN_HEADINGS = frozenset(
    {
        "about",
        "about the role",
        "about us",
        "achievements",
        "awards",
        "benefits",
        "certifications",
        "contact",
        "core competencies",
        "education",
        "employment",
        "employment history",
        "experience",
        "interests",
        "internships",
        "key achievements",
        "key skills",
        "languages",
        "leadership",
        "nice to have",
        "objective",
        "preferred qualifications",
        "professional experience",
        "professional summary",
        "profile",
        "projects",
        "publications",
        "qualifications",
        "requirements",
        "responsibilities",
        "skills",
        "summary",
        "technical expertise",
        "technical skills",
        "tools",
        "volunteering",
        "what we're looking for",
        "what you'll do",
        "who you are",
        "work experience",
        "work history",
    }
)


class ParsingError(ValueError):
    """The document can't be read; the message is safe to show the user."""


class Line(BaseModel):
    number: int
    section: str | None = None
    text: str


def lines_from_file(filename: str, data: bytes) -> list[Line]:
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".pdf":
        return build_lines(_read_pdf(data))
    if suffix in (".txt", ".md"):
        if b"\x00" in data[:1024]:
            raise ParsingError("The file looks like a binary file, not text.")
        return lines_from_text(data.decode("utf-8-sig", errors="replace"))
    allowed = ", ".join(SUPPORTED_EXTENSIONS)
    raise ParsingError(f"Unsupported file type. Allowed: {allowed}.")


def lines_from_text(text: str) -> list[Line]:
    return build_lines(text.splitlines())


def build_lines(raw_lines: list[str]) -> list[Line]:
    """Clean, re-join wrapped lines, split very long ones, number them and tag sections."""
    cleaned = [line for line in (_clean(raw) for raw in raw_lines) if line]
    texts = [part for line in _join_wrapped(cleaned) for part in _split_long(line)]
    if not texts:
        raise ParsingError("No text found. Scanned or image-only PDFs aren't supported.")
    if len(texts) > MAX_LINES:
        raise ParsingError(f"The document is too long (more than {MAX_LINES} lines).")
    return _number(texts)


def _read_pdf(data: bytes) -> list[str]:
    if PDF_MAGIC not in data[:1024]:
        raise ParsingError("The file is not a valid PDF.")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ParsingError(f"The PDF has more than {MAX_PDF_PAGES} pages.")
            return [line for page in pdf.pages for line in page_lines(page)]
    except ParsingError:
        raise
    except Exception as exc:  # pdfminer raises many types on malformed or encrypted files
        raise ParsingError("Could not read the PDF. It may be corrupt or encrypted.") from exc


def _clean(line: str) -> str:
    # NFKC folds ligatures ("ﬁ" -> "fi"); control characters (Postgres rejects NUL) go.
    line = unicodedata.normalize("NFKC", line)
    line = "".join(c if c.isprintable() else " " for c in line)
    return " ".join(line.split())


def _join_wrapped(lines: list[str]) -> list[str]:
    """Join a line onto the previous one when it is clearly the rest of a sentence."""
    joined: list[str] = []
    for line in lines:
        continues = (
            joined
            and line[0].islower()
            and not joined[-1].endswith((".", ":", ";", "!", "?"))
            and not _is_heading(joined[-1])
        )
        if continues:
            joined[-1] = f"{joined[-1]} {line}"
        else:
            joined.append(line)
    return joined


def _split_long(line: str) -> list[str]:
    """Split a paragraph into groups of sentences no longer than MAX_LINE_CHARS."""
    if len(line) <= MAX_LINE_CHARS:
        return [line]
    parts: list[str] = []
    for sentence in SENTENCE_END_RE.split(line):
        if parts and len(parts[-1]) + len(sentence) + 1 <= MAX_LINE_CHARS:
            parts[-1] = f"{parts[-1]} {sentence}"
        else:
            parts.extend(
                sentence[i : i + MAX_LINE_CHARS] for i in range(0, len(sentence), MAX_LINE_CHARS)
            )
    return parts


def _is_heading(line: str) -> bool:
    if len(line) > MAX_HEADING_CHARS or BULLET_RE.match(line):
        return False
    return line.rstrip(":").lstrip("# ").lower() in KNOWN_HEADINGS


def _number(texts: list[str]) -> list[Line]:
    section: str | None = None
    lines: list[Line] = []
    for number, text in enumerate(texts, start=1):
        if _is_heading(text):
            section = text.rstrip(":").lstrip("# ")
        lines.append(Line(number=number, section=section, text=text))
    return lines
