"""Read a PDF page in human order, including two-column resumes.

Extracting row by row across a two-column page mixes the columns ("Python
Experience Docker Acme Corp"). We look for a vertical gutter; where there is
one, each block of rows is read left column first, then right.
"""

from pdfplumber.page import Page

Word = dict  # pdfplumber word: {"text", "x0", "x1", "top", ...}

ROW_TOLERANCE = 3.0  # words whose tops differ by less than this share a row
GUTTER_HALF_WIDTH = 6.0
MAX_ROWS_CROSSING_GUTTER = 0.15  # headers such as the name may span both columns
ALWAYS_ALLOWED_CROSSING_ROWS = 2  # so a name and contact line don't defeat a short page
MIN_ROWS_PER_COLUMN = 0.3  # rules out right-aligned dates being read as a column


def page_lines(page: Page) -> list[str]:
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    return lines_from_words(words, float(page.width))


def lines_from_words(words: list[Word], page_width: float) -> list[str]:
    rows = _rows(words)
    gutter = _find_gutter(rows, page_width)
    if gutter is None:
        return [_join(row) for row in rows]
    return _read_columns(rows, gutter)


def _rows(words: list[Word]) -> list[list[Word]]:
    rows: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(word["top"] - rows[-1][0]["top"]) <= ROW_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: w["x0"]) for row in rows]


def _join(words: list[Word]) -> str:
    return " ".join(w["text"] for w in words)


def _crosses(row: list[Word], x: float) -> bool:
    return any(w["x0"] < x + GUTTER_HALF_WIDTH and w["x1"] > x - GUTTER_HALF_WIDTH for w in row)


def _find_gutter(rows: list[list[Word]], page_width: float) -> float | None:
    """The middle of the widest clear vertical band that has text on both sides."""
    if len(rows) < 4:
        return None
    candidates = [x for x in range(int(page_width * 0.2), int(page_width * 0.8), 4)]
    runs: list[list[int]] = [[]]
    for x in candidates:
        if _is_gutter(rows, x):
            runs[-1].append(x)
        elif runs[-1]:
            runs.append([])
    widest = max(runs, key=len)
    return float(widest[len(widest) // 2]) if widest else None


def _is_gutter(rows: list[list[Word]], x: float) -> bool:
    total = len(rows)
    crossing = sum(_crosses(row, x) for row in rows)
    left = sum(any(w["x1"] <= x for w in row) for row in rows)
    right = sum(any(w["x0"] >= x for w in row) for row in rows)
    return (
        crossing <= max(ALWAYS_ALLOWED_CROSSING_ROWS, total * MAX_ROWS_CROSSING_GUTTER)
        and left >= total * MIN_ROWS_PER_COLUMN
        and right >= total * MIN_ROWS_PER_COLUMN
    )


def _read_columns(rows: list[list[Word]], gutter: float) -> list[str]:
    lines: list[str] = []
    left: list[str] = []
    right: list[str] = []

    def flush() -> None:
        lines.extend(left + right)
        left.clear()
        right.clear()

    for row in rows:
        if _crosses(row, gutter):  # a full-width row ends the current two-column block
            flush()
            lines.append(_join(row))
            continue
        left_words = [w for w in row if w["x1"] <= gutter]
        right_words = [w for w in row if w["x0"] >= gutter]
        if left_words:
            left.append(_join(left_words))
        if right_words:
            right.append(_join(right_words))
    flush()
    return lines
