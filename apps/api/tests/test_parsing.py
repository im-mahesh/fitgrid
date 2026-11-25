import pytest

from app import parsing
from app.parsing import ParsingError, lines_from_file, lines_from_text
from pdf_helper import column, make_pdf


def texts(lines: list[parsing.Line]) -> list[str]:
    return [line.text for line in lines]


def test_lines_are_cleaned_and_numbered_from_one() -> None:
    lines = lines_from_text("  Jane   Doe \n\n• Built\x00 eﬃcient   APIs\n")

    assert texts(lines) == ["Jane Doe", "• Built efficient APIs"]
    assert [line.number for line in lines] == [1, 2]


def test_headings_tag_the_lines_beneath_them() -> None:
    lines = lines_from_text(
        "Jane Doe\nSKILLS\nPython, Docker\nWork Experience:\n- Acme: built pipelines"
    )

    assert [(line.section, line.text) for line in lines] == [
        (None, "Jane Doe"),
        ("SKILLS", "SKILLS"),
        ("SKILLS", "Python, Docker"),
        ("Work Experience", "Work Experience:"),
        ("Work Experience", "- Acme: built pipelines"),
    ]


def test_all_capital_skills_are_not_mistaken_for_headings() -> None:
    lines = lines_from_text("SKILLS\nAWS\nSQL\nREST API\nLanguages\nEnglish")

    assert [line.section for line in lines] == ["SKILLS"] * 4 + ["Languages"] * 2


def test_a_wrapped_sentence_becomes_one_line() -> None:
    lines = lines_from_text(
        "- Led the migration of the billing\nservice to Kubernetes.\n- Next bullet"
    )

    assert texts(lines) == [
        "- Led the migration of the billing service to Kubernetes.",
        "- Next bullet",
    ]


def test_a_finished_sentence_or_heading_is_not_joined_to_the_next_line() -> None:
    assert texts(lines_from_text("Shipped it.\niOS developer")) == ["Shipped it.", "iOS developer"]
    assert texts(lines_from_text("Skills\npython")) == ["Skills", "python"]


def test_long_paragraphs_are_split_at_sentence_boundaries() -> None:
    sentence = "We need someone who enjoys building reliable data systems at scale. "

    lines = lines_from_text(sentence * 20)

    assert len(lines) > 1
    assert all(len(line.text) <= parsing.MAX_LINE_CHARS for line in lines)
    assert all(line.text.endswith(".") for line in lines)


def test_one_enormous_sentence_is_still_cut_to_size() -> None:
    lines = lines_from_text("x" * 1000)

    assert [len(line.text) for line in lines] == [400, 400, 200]


@pytest.mark.parametrize("blank", ["", "  \n\t\n", "\x00\x00"])
def test_a_document_without_text_is_rejected(blank: str) -> None:
    with pytest.raises(ParsingError, match="No text found"):
        lines_from_text(blank)


def test_too_many_lines_is_rejected() -> None:
    with pytest.raises(ParsingError, match="too long"):
        lines_from_text("Line.\n" * (parsing.MAX_LINES + 1))


def test_unsupported_and_disguised_files_are_rejected() -> None:
    with pytest.raises(ParsingError, match="Unsupported file type"):
        lines_from_file("cv.docx", b"PK")
    with pytest.raises(ParsingError, match="binary"):
        lines_from_file("cv.txt", b"\x89PNG\x00\x00")
    with pytest.raises(ParsingError, match="not a valid PDF"):
        lines_from_file("cv.pdf", b"<html></html>")
    with pytest.raises(ParsingError, match="Could not read the PDF"):
        lines_from_file("cv.pdf", b"%PDF-1.4\nrubbish")


def test_single_column_pdf_reads_top_to_bottom_across_pages() -> None:
    pdf = make_pdf([column(60, ["Jane Doe", "Python developer"]), column(60, ["Second page"])])

    assert texts(lines_from_file("cv.pdf", pdf)) == ["Jane Doe", "Python developer", "Second page"]


def test_two_column_pdf_is_read_one_column_at_a_time() -> None:
    header = [(150, 60, "Jane Doe - Senior Platform Engineer, Bengaluru, India")]
    left = column(50, ["SKILLS", "Python", "Docker", "Kubernetes", "Postgres"])
    right = column(330, ["EXPERIENCE", "Acme Corp", "Built pipelines.", "Beta Ltd", "Led a team."])

    lines = lines_from_file("cv.pdf", make_pdf([header + left + right]))

    assert texts(lines) == [
        "Jane Doe - Senior Platform Engineer, Bengaluru, India",
        "SKILLS",
        "Python",
        "Docker",
        "Kubernetes",
        "Postgres",
        "EXPERIENCE",
        "Acme Corp",
        "Built pipelines.",
        "Beta Ltd",
        "Led a team.",
    ]


def test_right_aligned_dates_are_not_mistaken_for_a_second_column() -> None:
    long_bullet = "- Designed and operated the ingestion platform used by forty product teams."
    page = column(
        50,
        ["Acme Corp", long_bullet, long_bullet, long_bullet, "Beta Ltd", long_bullet, long_bullet],
    )
    page += [(500, 100, "2021-2024"), (500, 164, "2018-2021")]

    lines = texts(lines_from_file("cv.pdf", make_pdf([page])))

    assert lines[0] == "Acme Corp 2021-2024"
    assert "Beta Ltd 2018-2021" in lines


def test_pdf_with_no_text_and_pdf_with_too_many_pages_are_rejected() -> None:
    with pytest.raises(ParsingError, match="No text found"):
        lines_from_file("scan.pdf", make_pdf([[]]))
    too_long = make_pdf([column(60, ["page"])] * (parsing.MAX_PDF_PAGES + 1))
    with pytest.raises(ParsingError, match="more than 15 pages"):
        lines_from_file("long.pdf", too_long)
