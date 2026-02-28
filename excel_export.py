"""
Excel export and review module for NEET Test Generator.
Handles generation of type-specific Excel files (MCQ, AR, MTC)
and reading/updating Excel files for the review workflow.
"""

import io
import re
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


# ============================================================
# UTILITIES
# ============================================================

def _strip_latex(text: str) -> str:
    """Remove $ delimiters from LaTeX for Excel: $H_2O$ -> H_2O"""
    if not text:
        return ""
    return re.sub(r'\$([^$]+)\$', r'\1', str(text))


def _clean(text: str) -> str:
    """Clean text for Excel: strip LaTeX delimiters, normalize whitespace."""
    text = _strip_latex(str(text) if text else "")
    text = text.replace('\\n\\n', '\n').replace('\\n', '\n')
    return text.strip()


def _explanation_text(explanation) -> str:
    """Convert explanation dict or string to single text block."""
    if isinstance(explanation, dict):
        parts = []
        for k, v in explanation.items():
            if v:
                parts.append(f"{k.upper()}: {_clean(v)}")
        return "\n".join(parts)
    return _clean(str(explanation)) if explanation else ""


# ============================================================
# STYLING
# ============================================================

_HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
_HEADER_FILL = PatternFill(start_color='4F46E5', end_color='4F46E5', fill_type='solid')
_HEADER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
_CELL_ALIGN = Alignment(vertical='top', wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)


def _style_headers(ws, num_cols: int):
    """Apply header styling to row 1."""
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN
        cell.border = _THIN_BORDER


def _auto_width(ws):
    """Set reasonable column widths."""
    for col in ws.columns:
        letter = col[0].column_letter
        max_len = 0
        for cell in col:
            if cell.value:
                lines = str(cell.value).split('\n')
                max_len = max(max_len, max(len(line) for line in lines))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 60)


def _add_meta_row(ws, row: int, col_start: int, metadata: dict, is_first: bool):
    """Add Time to Run, token, and cost columns. Only populate on first data row."""
    if not is_first:
        return
    token_usage = metadata.get("token_usage", {})
    gen = token_usage.get("generation", {}) or {}
    cost = token_usage.get("cost", {}) or {}

    ws.cell(row=row, column=col_start).value = metadata.get("generation_time", "")
    ws.cell(row=row, column=col_start + 1).value = gen.get("input_tokens", "")
    ws.cell(row=row, column=col_start + 2).value = gen.get("output_tokens", "")
    ws.cell(row=row, column=col_start + 3).value = gen.get("total_tokens", "")
    ws.cell(row=row, column=col_start + 4).value = cost.get("input_cost", "")
    ws.cell(row=row, column=col_start + 5).value = cost.get("output_cost", "")
    ws.cell(row=row, column=col_start + 6).value = cost.get("total_cost", "")


# ============================================================
# AR PARSING
# ============================================================

def _parse_ar(question_text: str):
    """Extract Assertion and Reason from AR question_text."""
    text = str(question_text) if question_text else ""
    # Try "Assertion (A):" / "Reason (R):" pattern
    m = re.search(r'Assertion\s*\(?A\)?\s*:\s*(.*?)\s*Reason\s*\(?R\)?\s*:', text, re.DOTALL | re.IGNORECASE)
    assertion = m.group(1).strip() if m else text
    r = re.search(r'Reason\s*\(?R\)?\s*:\s*(.*)', text, re.DOTALL | re.IGNORECASE)
    reason = r.group(1).strip() if r else ""
    return _clean(assertion), _clean(reason)


# ============================================================
# MTC PARSING
# ============================================================

def _parse_mtc(question_text: str):
    """Extract List I items and List II items from MTC question_text."""
    text = str(question_text) if question_text else ""
    list_i_items = []
    list_ii_items = []

    # Try pipe-table format: "A. xxx | I. yyy"
    pairs = re.findall(r'([A-D])\.\s*(.*?)\s*\|\s*(IV|III|II|I)\.\s*(.*?)(?=\s+[A-D]\.\s|\s*Choose|\s*$)', text)
    if pairs:
        for letter, l1, roman, l2 in pairs:
            list_i_items.append(f"{letter}. {_clean(l1)}")
            list_ii_items.append(f"{roman}. {_clean(l2)}")
        return "\n".join(list_i_items), "\n".join(list_ii_items)

    # Fallback: return full text as List I
    return _clean(text), ""


# ============================================================
# SHEET BUILDERS
# ============================================================

MCQ_HEADERS = [
    "Question Number", "Question", "Option A", "Option B", "Option C", "Option D",
    "Correct Answer", "Explanation", "Accuracy", "Comment",
    "Time to Run", "Input Tokens", "Output Tokens", "Total Tokens",
    "Input Cost (Rs)", "Output Cost (Rs)", "Total Cost (Rs)"
]

AR_HEADERS = [
    "Question Number", "Assertion (A)", "Reason (R)", "Correct Answer",
    "Explanation", "Accuracy", "Comment",
    "Time to Run", "Input Tokens", "Output Tokens", "Total Tokens",
    "Input Cost (Rs)", "Output Cost (Rs)", "Total Cost (Rs)"
]

MTC_HEADERS = [
    "Question Number", "List I", "List II", "Correct Answer",
    "Explanation", "Accuracy", "Comment",
    "Time to Run", "Input Tokens", "Output Tokens", "Total Tokens",
    "Input Cost (Rs)", "Output Cost (Rs)", "Total Cost (Rs)"
]


def _build_mcq_sheet(ws, questions: list, metadata: dict):
    for col, h in enumerate(MCQ_HEADERS, 1):
        ws.cell(row=1, column=col, value=h)
    _style_headers(ws, len(MCQ_HEADERS))

    for idx, q in enumerate(questions):
        row = idx + 2
        opts = q.get("options", {})
        ws.cell(row=row, column=1).value = q.get("question_id", idx + 1)
        ws.cell(row=row, column=2).value = _clean(q.get("question_text", ""))
        ws.cell(row=row, column=3).value = _clean(opts.get("a", ""))
        ws.cell(row=row, column=4).value = _clean(opts.get("b", ""))
        ws.cell(row=row, column=5).value = _clean(opts.get("c", ""))
        ws.cell(row=row, column=6).value = _clean(opts.get("d", ""))
        ws.cell(row=row, column=7).value = (q.get("correct_answer") or "").upper()
        ws.cell(row=row, column=8).value = _explanation_text(q.get("explanation"))
        # 9=Accuracy, 10=Comment left blank
        _add_meta_row(ws, row, 11, metadata, is_first=(idx == 0))

        for c in range(1, len(MCQ_HEADERS) + 1):
            ws.cell(row=row, column=c).alignment = _CELL_ALIGN

    _auto_width(ws)


def _build_ar_sheet(ws, questions: list, metadata: dict):
    for col, h in enumerate(AR_HEADERS, 1):
        ws.cell(row=1, column=col, value=h)
    _style_headers(ws, len(AR_HEADERS))

    for idx, q in enumerate(questions):
        row = idx + 2
        assertion, reason = _parse_ar(q.get("question_text", ""))
        ws.cell(row=row, column=1).value = q.get("question_id", idx + 1)
        ws.cell(row=row, column=2).value = assertion
        ws.cell(row=row, column=3).value = reason
        ws.cell(row=row, column=4).value = (q.get("correct_answer") or "").upper()
        ws.cell(row=row, column=5).value = _explanation_text(q.get("explanation"))
        # 6=Accuracy, 7=Comment left blank
        _add_meta_row(ws, row, 8, metadata, is_first=(idx == 0))

        for c in range(1, len(AR_HEADERS) + 1):
            ws.cell(row=row, column=c).alignment = _CELL_ALIGN

    _auto_width(ws)


def _build_mtc_sheet(ws, questions: list, metadata: dict):
    for col, h in enumerate(MTC_HEADERS, 1):
        ws.cell(row=1, column=col, value=h)
    _style_headers(ws, len(MTC_HEADERS))

    for idx, q in enumerate(questions):
        row = idx + 2
        list_i, list_ii = _parse_mtc(q.get("question_text", ""))
        ws.cell(row=row, column=1).value = q.get("question_id", idx + 1)
        ws.cell(row=row, column=2).value = list_i
        ws.cell(row=row, column=3).value = list_ii
        ws.cell(row=row, column=4).value = (q.get("correct_answer") or "").upper()
        ws.cell(row=row, column=5).value = _explanation_text(q.get("explanation"))
        # 6=Accuracy, 7=Comment left blank
        _add_meta_row(ws, row, 8, metadata, is_first=(idx == 0))

        for c in range(1, len(MTC_HEADERS) + 1):
            ws.cell(row=row, column=c).alignment = _CELL_ALIGN

    _auto_width(ws)


# ============================================================
# PUBLIC API — GENERATE
# ============================================================

def generate_excel_for_result(result: dict) -> bytes:
    """Generate an Excel file from a generation result dict. Returns bytes."""
    metadata = result.get("test_metadata", {})
    questions = result.get("questions", [])
    question_type = metadata.get("question_type", "mcq")

    wb = Workbook()
    ws = wb.active

    if question_type == "combination":
        mcq_qs = [q for q in questions if q.get("question_type", "").upper() == "MCQ"]
        ar_qs = [q for q in questions if q.get("question_type", "").upper() in ("ASSERTION_REASON", "ASSERTION-REASON", "AR")]
        mtc_qs = [q for q in questions if q.get("question_type", "").upper() in ("MATCH_THE_COLUMN", "MTC")]

        sheets_created = False
        if mcq_qs:
            ws.title = "MCQ"
            _build_mcq_sheet(ws, mcq_qs, metadata)
            sheets_created = True
        if ar_qs:
            ar_ws = wb.create_sheet("Assertion-Reason") if sheets_created else ws
            if not sheets_created:
                ar_ws.title = "Assertion-Reason"
                sheets_created = True
            _build_ar_sheet(ar_ws, ar_qs, metadata)
        if mtc_qs:
            mtc_ws = wb.create_sheet("Match the Column") if sheets_created else ws
            if not sheets_created:
                mtc_ws.title = "Match the Column"
                sheets_created = True
            _build_mtc_sheet(mtc_ws, mtc_qs, metadata)

        if not sheets_created:
            ws.title = "MCQ"
            _build_mcq_sheet(ws, questions, metadata)
    elif question_type in ("assertion_reason",):
        ws.title = "Assertion-Reason"
        _build_ar_sheet(ws, questions, metadata)
    elif question_type in ("match_the_column",):
        ws.title = "Match the Column"
        _build_mtc_sheet(ws, questions, metadata)
    else:
        ws.title = "MCQ"
        _build_mcq_sheet(ws, questions, metadata)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================
# PUBLIC API — REVIEW
# ============================================================

def read_excel_for_review(excel_bytes: bytes) -> tuple:
    """Read an exported Excel file for review.
    Returns (list_of_question_dicts, question_type_str).
    Handles multi-sheet (combination) workbooks.
    """
    wb = load_workbook(io.BytesIO(excel_bytes))
    all_questions = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        headers = [cell.value for cell in ws[1] if cell.value]
        if not headers:
            continue

        # Detect type from headers
        if "Assertion (A)" in headers:
            qtype = "ASSERTION_REASON"
        elif "List I" in headers:
            qtype = "MATCH_THE_COLUMN"
        else:
            qtype = "MCQ"

        header_map = {h: i for i, h in enumerate(headers)}

        for row in ws.iter_rows(min_row=2, max_col=len(headers)):
            vals = [cell.value for cell in row]
            if not vals[0]:  # skip empty rows
                continue

            q = {"_type": qtype, "_sheet": sheet_name, "_row": row[0].row}

            if qtype == "MCQ":
                q["question_text"] = vals[header_map.get("Question", 1)] or ""
                q["options"] = {
                    "a": vals[header_map.get("Option A", 2)] or "",
                    "b": vals[header_map.get("Option B", 3)] or "",
                    "c": vals[header_map.get("Option C", 4)] or "",
                    "d": vals[header_map.get("Option D", 5)] or "",
                }
                q["correct_answer"] = vals[header_map.get("Correct Answer", 6)] or ""
                q["explanation"] = vals[header_map.get("Explanation", 7)] or ""
                q["accuracy"] = vals[header_map.get("Accuracy", 8)] or ""
                q["comment"] = vals[header_map.get("Comment", 9)] or ""
            elif qtype == "ASSERTION_REASON":
                q["assertion"] = vals[header_map.get("Assertion (A)", 1)] or ""
                q["reason"] = vals[header_map.get("Reason (R)", 2)] or ""
                q["correct_answer"] = vals[header_map.get("Correct Answer", 3)] or ""
                q["explanation"] = vals[header_map.get("Explanation", 4)] or ""
                q["accuracy"] = vals[header_map.get("Accuracy", 5)] or ""
                q["comment"] = vals[header_map.get("Comment", 6)] or ""
            elif qtype == "MATCH_THE_COLUMN":
                q["list_i"] = vals[header_map.get("List I", 1)] or ""
                q["list_ii"] = vals[header_map.get("List II", 2)] or ""
                q["correct_answer"] = vals[header_map.get("Correct Answer", 3)] or ""
                q["explanation"] = vals[header_map.get("Explanation", 4)] or ""
                q["accuracy"] = vals[header_map.get("Accuracy", 5)] or ""
                q["comment"] = vals[header_map.get("Comment", 6)] or ""

            all_questions.append(q)

    # Determine overall type
    types = {q["_type"] for q in all_questions}
    if len(types) == 1:
        overall_type = types.pop()
    else:
        overall_type = "COMBINATION"

    return all_questions, overall_type


def update_excel_with_comments(excel_bytes: bytes, comments: dict, accuracies: dict = None) -> bytes:
    """Write comments (and optionally accuracy) back into the Excel file.
    comments = {question_index: comment_text}
    accuracies = {question_index: accuracy_text} (optional)
    """
    wb = load_workbook(io.BytesIO(excel_bytes))

    # Build a mapping: question_index -> (sheet, excel_row)
    q_idx = 0
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        headers = [cell.value for cell in ws[1] if cell.value]
        if not headers:
            continue

        comment_col = None
        accuracy_col = None
        for i, h in enumerate(headers):
            if h == "Comment":
                comment_col = i + 1
            if h == "Accuracy":
                accuracy_col = i + 1

        for row_num in range(2, ws.max_row + 1):
            if ws.cell(row=row_num, column=1).value is None:
                continue
            if comment_col and q_idx in comments:
                ws.cell(row=row_num, column=comment_col).value = comments[q_idx]
            if accuracy_col and accuracies and q_idx in accuracies:
                ws.cell(row=row_num, column=accuracy_col).value = accuracies[q_idx]
            q_idx += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
