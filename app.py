"""
Streamlit UI for Testing NEET Question Generator
Multi-PDF support, Excel export, and Review & Comment workflow.
"""

import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging to show in terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

import re
import time
import streamlit as st
import json

from test_generator import generate_neet_test_from_pdf
from excel_export import generate_excel_for_result, read_excel_for_review, update_excel_with_comments, latex_to_unicode

# Page config
st.set_page_config(
    page_title="NEET Test Generator",
    page_icon="📝",
    layout="wide"
)

# ============================================================
# CUSTOM CSS THEME
# ============================================================
st.markdown("""
<style>
/* ---------- Import Google Fonts ---------- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---------- Global ---------- */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ---------- Hide default Streamlit header/footer ---------- */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown label,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] label {
    color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F1F5F9 !important;
}
section[data-testid="stSidebar"] .stDivider {
    border-color: #334155 !important;
}

/* ---------- Hero Banner ---------- */
.hero-banner {
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #9333EA 100%);
    padding: 2.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    text-align: center;
    box-shadow: 0 10px 40px rgba(79, 70, 229, 0.3);
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.08) 0%, transparent 50%);
    pointer-events: none;
}
.hero-title {
    font-size: 2rem;
    font-weight: 800;
    color: #FFFFFF;
    margin: 0 0 0.25rem 0;
    letter-spacing: -0.5px;
}
.hero-subtitle {
    font-size: 1rem;
    color: rgba(255,255,255,0.8);
    margin: 0;
    font-weight: 400;
}

/* ---------- Stat Cards ---------- */
.stat-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: transform 0.2s, box-shadow 0.2s;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.stat-label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748B;
    margin-bottom: 0.25rem;
}
.stat-value {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1E293B;
}

/* ---------- Question Card ---------- */
.question-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s;
}
.question-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}

/* ---------- Question Header ---------- */
.q-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 1rem;
}
.q-number {
    background: linear-gradient(135deg, #4F46E5, #7C3AED);
    color: #FFFFFF;
    font-weight: 700;
    font-size: 0.8rem;
    padding: 0.3rem 0.85rem;
    border-radius: 20px;
    letter-spacing: 0.3px;
}
.q-type-badge {
    background: #F1F5F9;
    color: #475569;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.25rem 0.7rem;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

/* ---------- Options ---------- */
.option-row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.7rem 1rem;
    border-radius: 10px;
    margin: 0.35rem 0;
    transition: background 0.15s;
    border: 1px solid transparent;
}
.option-row-default {
    background: #F8FAFC;
    border-color: #E2E8F0;
}
.option-row-default:hover {
    background: #F1F5F9;
    border-color: #CBD5E1;
}
.option-row-correct {
    background: #ECFDF5;
    border-color: #6EE7B7;
}
.option-letter {
    font-weight: 700;
    font-size: 0.85rem;
    min-width: 1.8rem;
    height: 1.8rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    flex-shrink: 0;
}
.option-letter-default {
    background: #E2E8F0;
    color: #475569;
}
.option-text {
    font-size: 0.95rem;
    color: #334155;
    line-height: 1.5;
    padding-top: 0.15rem;
}

/* ---------- Empty State ---------- */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: #94A3B8;
}
.empty-state-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
    opacity: 0.5;
}
.empty-state-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #64748B;
    margin-bottom: 0.5rem;
}
.empty-state-text {
    font-size: 0.95rem;
    color: #94A3B8;
}

/* ---------- Sidebar Section Label ---------- */
.sidebar-section {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #94A3B8 !important;
    margin-bottom: 0.5rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid #334155;
}

/* ---------- Buttons ---------- */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4) !important;
}
.stButton > button[kind="secondary"] {
    border-radius: 10px !important;
    font-weight: 600 !important;
    border-color: #CBD5E1 !important;
}

/* ---------- Expander ---------- */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

/* ---------- Info Banner ---------- */
.info-banner {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #1E40AF;
}

/* ---------- Batch Badge ---------- */
.batch-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: #F1F5F9;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.25rem 0.65rem;
    border-radius: 6px;
    border: 1px solid #E2E8F0;
}

/* ---------- PDF Config Card ---------- */
.pdf-config-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}
.pdf-config-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #1E293B;
    margin-bottom: 0.25rem;
}
.pdf-config-meta {
    font-size: 0.75rem;
    color: #64748B;
}

/* ---------- Review Card ---------- */
.review-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.review-answer {
    background: #ECFDF5;
    border: 1px solid #6EE7B7;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    color: #065F46;
    display: inline-block;
    margin: 0.5rem 0;
}

/* ---------- Tab Styling ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.95rem;
    padding: 0.5rem 1.5rem;
    border-radius: 8px 8px 0 0;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HERO BANNER
# ============================================================
st.markdown("""
<div class="hero-banner">
    <div class="hero-title">NEET Test Generator</div>
    <div class="hero-subtitle">Generate high-quality practice questions from textbook PDFs</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
if "pdf_configs" not in st.session_state:
    st.session_state.pdf_configs = {}  # {filename: {pdf_bytes, page_count, difficulty, question_type, question_count}}
if "pdf_order" not in st.session_state:
    st.session_state.pdf_order = []
if "results" not in st.session_state:
    st.session_state.results = {}  # {filename: {result, generation_time, excel_bytes, excel_filename}}
if "review_data" not in st.session_state:
    st.session_state.review_data = None  # {filename, questions, question_type, excel_bytes}

# Load API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
model = "gpt-5-mini"
max_completion_tokens = 80000


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count pages in a PDF."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception:
        return 0


def _make_excel_filename(metadata: dict, page_count: int) -> str:
    """Generate filename: {pages}page_{difficulty}_{type}_{count}questions.xlsx"""
    pages = page_count or metadata.get("page_count", 0)
    difficulty = metadata.get("difficulty", "medium")
    qtype = metadata.get("question_type", "mcq")
    total = metadata.get("total_questions", 0)

    type_names = {
        "mcq": "mcq",
        "assertion_reason": "ar",
        "match_the_column": "mtc",
        "combination": "mixed",
    }
    type_str = type_names.get(qtype, qtype)
    return f"{pages}page_{difficulty}_{type_str}_{total}questions.xlsx"


def render_match_the_column(text: str):
    """Dedicated renderer for Match the Column questions. Handles all formats."""
    text = latex_to_unicode(text)
    text = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')

    prefix = ""
    table_rows = []

    # FORMAT 1: LaTeX tabular
    if '\\begin{tabular}' in text or 'begin{tabular}' in text:
        normalized = text.replace('\\\\', '\\')
        prefix_match = re.match(r'^(.*?)\\begin\{tabular\}', normalized, re.DOTALL)
        if prefix_match:
            prefix = prefix_match.group(1).strip()

        tabular_match = re.search(r'\\begin\{tabular\}.*?\\end\{tabular\}', normalized, re.DOTALL)
        if tabular_match:
            table_raw = tabular_match.group(0)
            table_raw = re.sub(r'\\begin\{tabular\}\{[^}]*\}', '', table_raw)
            table_raw = table_raw.replace('\\end{tabular}', '').replace('\\hline', '')
            rows = [r.strip() for r in re.split(r'\\(?:\s|$)', table_raw) if r.strip()]
            for row in rows:
                cells = [c.strip() for c in row.split('&')]
                if len(cells) >= 2:
                    table_rows.append(cells)

    # FORMAT 2: Markdown pipe table
    elif '|' in text:
        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            if '|' in stripped and not stripped.startswith('---'):
                cells = [c.strip() for c in stripped.split('|') if c.strip()]
                if len(cells) >= 2:
                    if cells[0].lower().startswith('column') or any(c.startswith(('1.', '2.', '3.', '4.', '5.', 'A.', 'B.', 'C.', 'D.', 'E.')) for c in cells):
                        table_rows.append(cells)
                    elif not table_rows:
                        prefix += stripped + " "
                elif not table_rows:
                    prefix += stripped + " "
            elif not table_rows:
                prefix += stripped + " "

    # FORMAT 3: Plain text with numbered items
    if not table_rows:
        lines = text.split('\n')
        col1_items = {}
        col2_items = {}
        remaining_prefix = []

        for line in lines:
            stripped = line.strip()
            num_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
            letter_match = re.match(r'^([a-e])\.\s+(.+)', stripped)

            if num_match:
                col1_items[num_match.group(1)] = num_match.group(2).strip()
            elif letter_match:
                col2_items[letter_match.group(1)] = letter_match.group(2).strip()
            elif 'Column I' in stripped or 'Column II' in stripped:
                continue
            else:
                remaining_prefix.append(stripped)

        if col1_items and col2_items:
            if not prefix:
                prefix = ' '.join(remaining_prefix).strip()
            table_rows.append(['Column I', 'Column II'])
            for num in sorted(col1_items.keys()):
                letter = chr(96 + int(num))
                col2_val = col2_items.get(letter, '')
                table_rows.append([f"{num}. {col1_items[num]}", f"{letter}. {col2_val}"])

    if prefix:
        prefix = prefix.strip().rstrip(':').strip()
        st.markdown(f"**{prefix}:**")

    if table_rows:
        md_lines = []
        for i, cells in enumerate(table_rows):
            md_line = '| ' + ' | '.join(cells) + ' |'
            md_lines.append(md_line)
            if i == 0:
                md_lines.append('|' + '|'.join(['---'] * len(cells)) + '|')
        st.markdown('\n'.join(md_lines))
    else:
        st.markdown(f"**{text}**")


def render_latex_text(text: str):
    """Render text that may contain LaTeX."""
    text = latex_to_unicode(text)
    if '\\begin{tabular}' in text or 'begin{tabular}' in text:
        normalized = text.replace('\\\\', '\\')
        prefix_match = re.match(r'^(.*?)\\begin\{tabular\}', normalized, re.DOTALL)
        if prefix_match:
            prefix = prefix_match.group(1).strip().rstrip('\\n').strip()
            if prefix:
                st.markdown(f"**{prefix}**")

        tabular_match = re.search(r'\\begin\{tabular\}.*?\\end\{tabular\}', normalized, re.DOTALL)
        if tabular_match:
            table_raw = tabular_match.group(0)
            table_raw = re.sub(r'\\begin\{tabular\}\{[^}]*\}', '', table_raw)
            table_raw = table_raw.replace('\\end{tabular}', '')
            table_raw = table_raw.replace('\\hline', '')
            rows = [r.strip() for r in re.split(r'\\(?:\s|$)', table_raw) if r.strip()]

            if rows:
                md_lines = []
                for i, row in enumerate(rows):
                    cells = [c.strip() for c in row.split('&')]
                    md_line = '| ' + ' | '.join(cells) + ' |'
                    md_lines.append(md_line)
                    if i == 0:
                        md_lines.append('|' + '|'.join(['---'] * len(cells)) + '|')
                st.markdown('\n'.join(md_lines))
        return

    if '$' in text:
        formatted = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        formatted = re.sub(r'\s*(Statement\s+(?:I{1,3}|IV|[1-4])\s*:)', r'  \n\1', formatted).strip()
        st.markdown(formatted)
    else:
        formatted = text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
        formatted = re.sub(r'\s*(Statement\s+(?:I{1,3}|IV|[1-4])\s*:)', r'  \n\1', formatted).strip()
        if '\n' in formatted:
            bolded = '\n\n'.join(f"**{line.strip()}**" if line.strip() else '' for line in formatted.split('\n'))
            st.markdown(bolded)
        else:
            st.markdown(f"**{formatted}**")


def render_test_view(result: dict, generation_time: float = None):
    """Render questions in a polished test paper view."""

    if "parse_error" in result:
        st.error(f"**Parse Error:** {result.get('parse_error')}")
        st.code(result.get('raw_response', ''), language="text")
        return

    # --- Test Header ---
    if "test_metadata" in result:
        meta = result["test_metadata"]

        # Format generation time
        gen_time = generation_time
        if gen_time is not None:
            if gen_time >= 60:
                time_str = f"{int(gen_time // 60)}m {int(gen_time % 60)}s"
            else:
                time_str = f"{gen_time:.1f}s"
        else:
            time_str = "N/A"

        # Format generation time from metadata
        gen_t = meta.get('generation_time')
        gen_str = f"{gen_t}s" if gen_t is not None else "N/A"

        stats = [
            ("Subject", meta.get('subject', 'N/A').title()),
            ("Topic", (meta.get('topic', 'N/A')[:25] + "...") if len(str(meta.get('topic', ''))) > 25 else meta.get('topic', 'N/A')),
            ("Difficulty", meta.get('difficulty', 'N/A').title()),
            ("Type", {
                "mcq": "MCQ",
                "assertion_reason": "Assertion-Reason",
                "match_the_column": "Match the Column",
                "combination": "Mixed"
            }.get(meta.get('question_type', 'combination'), meta.get('question_type', 'N/A'))),
            ("Questions", str(meta.get('total_questions', 'N/A'))),
            ("Generation", gen_str),
            ("Total Time", time_str),
        ]

        cols = st.columns(len(stats))
        for i, (label, value) in enumerate(stats):
            with cols[i]:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}</div>
                </div>
                """, unsafe_allow_html=True)

        # Token usage and pricing details
        token_usage = meta.get('token_usage', {})
        if token_usage:
            gen_tok = token_usage.get('generation', {})
            grand_total = token_usage.get('grand_total', 0)
            cost = token_usage.get('cost', {})
            total_cost = cost.get('total_cost', 0)

            cost_label = f" — Cost: Rs.{total_cost:.2f}" if total_cost else ""
            with st.expander(f"Token Usage & Pricing — Total: {grand_total:,}{cost_label}" if grand_total else "Token Usage & Pricing"):
                tok_cols = st.columns(3)
                with tok_cols[0]:
                    st.markdown("**Tokens**")
                    if gen_tok:
                        st.markdown(f"- Input: **{gen_tok.get('input_tokens', 0):,}**")
                        st.markdown(f"- Output: **{gen_tok.get('output_tokens', 0):,}**")
                        st.markdown(f"- Total: **{gen_tok.get('total_tokens', 0):,}**")
                    else:
                        st.markdown("N/A")
                with tok_cols[1]:
                    st.markdown("**Pricing (GPT-5 mini)**")
                    if cost:
                        st.markdown(f"- Input: **Rs.{cost.get('input_cost', 0):.2f}** ({cost.get('input_rate', '')})")
                        st.markdown(f"- Output: **Rs.{cost.get('output_cost', 0):.2f}** ({cost.get('output_rate', '')})")
                        st.markdown(f"- **Total: Rs.{total_cost:.2f}**")
                    else:
                        st.markdown("N/A")
                with tok_cols[2]:
                    st.markdown("**Summary**")
                    st.markdown(f"- Grand Total Tokens: **{grand_total:,}**")
                    if total_cost:
                        st.markdown(f"- **Estimated Cost: Rs.{total_cost:.2f}**")
                    if gen_t:
                        st.markdown(f"- Generation Time: **{gen_t}s**")

        if meta.get('content_limitation_note'):
            st.markdown(f"""
            <div class="info-banner">
                <span>&#9432;</span> {meta['content_limitation_note']}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")

    # --- Questions ---
    if "questions" in result:
        questions = result["questions"]

        for idx, q in enumerate(questions):
            q_id = q.get('question_id', idx + 1)
            q_type = q.get('question_type', 'MCQ')
            q_text = latex_to_unicode(q.get('question_text', ''))

            type_labels = {
                'MCQ': 'MCQ',
                'ASSERTION_REASON': 'Assertion-Reason',
                'MATCH_THE_COLUMN': 'Match the Column'
            }
            type_label = type_labels.get(q_type, q_type.replace('_', ' '))

            # Open question card
            st.markdown(f"""
            <div class="question-card">
                <div class="q-header">
                    <span class="q-number">Q{q_id}</span>
                    <span class="q-type-badge">{type_label}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Pre-process statement line breaks
            q_text = re.sub(r'\s*(Statement\s+(?:I{1,3}|IV|[1-4])\s*:)', r'  \n\1', q_text).strip()

            # Question text
            if q_type == 'MATCH_THE_COLUMN':
                render_match_the_column(q_text)
            else:
                formatted = q_text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
                if '\n' in formatted:
                    lines = []
                    for line in formatted.split('\n'):
                        stripped = line.strip()
                        if stripped:
                            lines.append(f"**{stripped}**")
                        else:
                            lines.append('')
                    st.markdown('\n\n'.join(lines))
                else:
                    st.markdown(f"**{formatted}**")

            st.write("")

            # Options
            if "options" in q:
                options = q["options"]
                for key in ['a', 'b', 'c', 'd']:
                    if key in options:
                        val = latex_to_unicode(options[key])
                        label = key.upper()

                        letter_col, text_col = st.columns([0.055, 0.945])
                        with letter_col:
                            st.markdown(f'<span class="option-letter option-letter-default">{label}</span>', unsafe_allow_html=True)
                        with text_col:
                            st.markdown(val)

            st.markdown("")
    else:
        st.warning("No questions were generated. Try again or check the PDF content.")


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown('<div class="sidebar-section">PDF Input</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more textbook PDFs (max 50MB each)",
        label_visibility="collapsed"
    )

    # Process uploaded files — sync pdf_configs with uploaded_files
    current_filenames = set()
    if uploaded_files:
        for uf in uploaded_files:
            current_filenames.add(uf.name)
            if uf.name not in st.session_state.pdf_configs:
                pdf_bytes = uf.getvalue()
                file_size_mb = len(pdf_bytes) / (1024 * 1024)
                if file_size_mb > 50:
                    st.error(f"{uf.name} is too large ({file_size_mb:.1f} MB). Max 50MB.")
                    continue
                page_count = _count_pdf_pages(pdf_bytes)
                st.session_state.pdf_configs[uf.name] = {
                    "pdf_bytes": pdf_bytes,
                    "page_count": page_count,
                    "file_size_mb": file_size_mb,
                    "difficulty": "easy",
                    "question_type": "combination",
                    "question_count": 5,
                }
                if uf.name not in st.session_state.pdf_order:
                    st.session_state.pdf_order.append(uf.name)

    # Remove configs for files that were un-uploaded
    removed = [fn for fn in st.session_state.pdf_order if fn not in current_filenames]
    for fn in removed:
        st.session_state.pdf_configs.pop(fn, None)
        st.session_state.results.pop(fn, None)
    st.session_state.pdf_order = [fn for fn in st.session_state.pdf_order if fn in current_filenames]

    if st.session_state.pdf_order:
        st.success(f"{len(st.session_state.pdf_order)} PDF(s) uploaded")

    st.divider()
    st.markdown('<div class="sidebar-section">Global Settings</div>', unsafe_allow_html=True)

    subject = st.selectbox(
        "Subject",
        ["biology", "chemistry"],
        index=0,
        format_func=lambda x: x.title()
    )


# ============================================================
# MAIN CONTENT — TABS
# ============================================================
tab_generate, tab_review = st.tabs(["Generate Questions", "Review & Comment"])


# ============================================================
# TAB 1: GENERATE QUESTIONS
# ============================================================
with tab_generate:
    if not st.session_state.pdf_order:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📄</div>
            <div class="empty-state-title">No PDFs uploaded yet</div>
            <div class="empty-state-text">Upload one or more textbook PDFs in the sidebar to get started</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # --- Per-PDF Configuration Cards ---
        st.markdown("### Configure Each PDF")
        for fname in st.session_state.pdf_order:
            cfg = st.session_state.pdf_configs[fname]
            with st.expander(f"**{fname}** — {cfg['page_count']} pages, {cfg['file_size_mb']:.1f} MB", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    cfg["difficulty"] = st.selectbox(
                        "Difficulty",
                        ["easy", "medium", "hard"],
                        index=["easy", "medium", "hard"].index(cfg.get("difficulty", "easy")),
                        key=f"diff_{fname}"
                    )
                with c2:
                    type_options = ["combination", "mcq", "assertion_reason", "match_the_column"]
                    type_labels = {"combination": "Mixed", "mcq": "MCQ", "assertion_reason": "A-R", "match_the_column": "Match"}
                    cfg["question_type"] = st.selectbox(
                        "Type",
                        type_options,
                        index=type_options.index(cfg.get("question_type", "combination")),
                        format_func=lambda x: type_labels.get(x, x),
                        key=f"type_{fname}"
                    )
                with c3:
                    cfg["question_count"] = st.number_input(
                        "Questions",
                        min_value=1,
                        max_value=100,
                        value=cfg.get("question_count", 5),
                        step=1,
                        key=f"count_{fname}"
                    )

        st.markdown("")

        # --- Generate All Tests Button ---
        generate_btn = st.button(
            f"Generate Tests for {len(st.session_state.pdf_order)} PDF(s)",
            type="primary",
            use_container_width=True,
            icon="🚀"
        )

        if generate_btn:
            if not api_key:
                st.error("Please set your OPENAI_API_KEY environment variable in .env or Streamlit secrets.")
            else:
                total_pdfs = len(st.session_state.pdf_order)
                overall_start = time.time()

                for pdf_idx, fname in enumerate(st.session_state.pdf_order):
                    cfg = st.session_state.pdf_configs[fname]
                    with st.status(f"[{pdf_idx + 1}/{total_pdfs}] Generating {cfg['question_count']} questions from {fname}...", expanded=True) as status:
                        st.write(f"Subject: {subject.title()} | Difficulty: {cfg['difficulty'].title()} | Type: {cfg['question_type'].replace('_', ' ').title()}")
                        start_time = time.time()
                        try:
                            result = generate_neet_test_from_pdf(
                                pdf_bytes=cfg["pdf_bytes"],
                                subject=subject,
                                difficulty=cfg["difficulty"],
                                question_count=cfg["question_count"],
                                question_type=cfg["question_type"],
                                model=model,
                                max_completion_tokens=max_completion_tokens,
                                api_key=api_key,
                            )

                            elapsed = time.time() - start_time

                            if result:
                                # Generate Excel
                                excel_bytes = generate_excel_for_result(result)
                                meta = result.get("test_metadata", {})
                                excel_filename = _make_excel_filename(meta, cfg["page_count"])

                                st.session_state.results[fname] = {
                                    "result": result,
                                    "generation_time": elapsed,
                                    "excel_bytes": excel_bytes,
                                    "excel_filename": excel_filename,
                                }

                                num_q = len(result.get("questions", []))
                                status.update(label=f"[{pdf_idx + 1}/{total_pdfs}] {fname} — {num_q} questions in {elapsed:.1f}s", state="complete")
                            else:
                                status.update(label=f"[{pdf_idx + 1}/{total_pdfs}] {fname} — No result returned", state="error")

                        except Exception as e:
                            import traceback
                            elapsed = time.time() - start_time
                            logger.error(f"Generation failed for {fname} after {elapsed:.1f}s: {type(e).__name__}: {e}")
                            logger.error(traceback.format_exc())
                            status.update(label=f"[{pdf_idx + 1}/{total_pdfs}] {fname} — Error: {e}", state="error")
                            st.code(traceback.format_exc())

                overall_elapsed = time.time() - overall_start
                st.success(f"All {total_pdfs} PDF(s) processed in {overall_elapsed:.1f}s")

        # --- Results Display ---
        for fname in st.session_state.pdf_order:
            if fname in st.session_state.results:
                res_data = st.session_state.results[fname]
                result = res_data["result"]
                gen_time = res_data["generation_time"]
                excel_bytes = res_data["excel_bytes"]
                excel_filename = res_data["excel_filename"]

                st.markdown(f"---")
                st.markdown(f"### Results: {fname}")

                # Download button for Excel
                st.download_button(
                    label=f"Download Excel: {excel_filename}",
                    data=excel_bytes,
                    file_name=excel_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{fname}",
                    type="secondary",
                    use_container_width=True,
                )

                st.markdown("")

                # Render the test view
                render_test_view(result, generation_time=gen_time)

                with st.expander("Raw JSON"):
                    st.code(json.dumps(result, indent=2, ensure_ascii=False), language="json")


# ============================================================
# TAB 2: REVIEW & COMMENT
# ============================================================
with tab_review:
    st.markdown("### Upload Excel for Review")
    st.markdown("Upload a previously exported Excel file to review questions, add accuracy ratings and comments, then re-download.")

    review_file = st.file_uploader(
        "Upload Excel",
        type=["xlsx"],
        accept_multiple_files=False,
        help="Upload an Excel file exported from the Generate tab",
        key="review_uploader",
        label_visibility="collapsed"
    )

    if review_file is not None:
        review_bytes = review_file.getvalue()

        # Parse Excel
        try:
            questions, overall_type = read_excel_for_review(review_bytes)
        except Exception as e:
            st.error(f"Failed to read Excel: {e}")
            questions = []
            overall_type = "UNKNOWN"

        if questions:
            type_display = {
                "MCQ": "MCQ",
                "ASSERTION_REASON": "Assertion-Reason",
                "MATCH_THE_COLUMN": "Match the Column",
                "COMBINATION": "Mixed (Multiple Types)",
            }
            st.markdown(f"""
            <div class="info-banner">
                <span>&#9432;</span> Detected <strong>{len(questions)}</strong> questions — Type: <strong>{type_display.get(overall_type, overall_type)}</strong>
            </div>
            """, unsafe_allow_html=True)

            # Initialize comments and accuracies in session state
            if "review_comments" not in st.session_state or st.session_state.get("_review_file") != review_file.name:
                st.session_state.review_comments = {}
                st.session_state.review_accuracies = {}
                st.session_state._review_file = review_file.name
                # Pre-populate from Excel if already filled
                for i, q in enumerate(questions):
                    st.session_state.review_comments[i] = q.get("comment", "") or ""
                    st.session_state.review_accuracies[i] = q.get("accuracy", "") or ""

            # Display each question as a review card
            for idx, q in enumerate(questions):
                qtype = q.get("_type", "MCQ")

                st.markdown(f"""
                <div class="review-card">
                    <div class="q-header">
                        <span class="q-number">Q{idx + 1}</span>
                        <span class="q-type-badge">{type_display.get(qtype, qtype)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Render question content by type (LaTeX cleaned to Unicode)
                if qtype == "MCQ":
                    st.markdown(f"**{latex_to_unicode(q.get('question_text', ''))}**")
                    opts = q.get("options", {})
                    for key in ["a", "b", "c", "d"]:
                        if key in opts and opts[key]:
                            st.markdown(f"- **{key.upper()}.** {latex_to_unicode(opts[key])}")
                elif qtype == "ASSERTION_REASON":
                    st.markdown(f"**Assertion (A):** {latex_to_unicode(q.get('assertion', ''))}")
                    st.markdown(f"**Reason (R):** {latex_to_unicode(q.get('reason', ''))}")
                elif qtype == "MATCH_THE_COLUMN":
                    st.markdown(f"**List I:** {latex_to_unicode(q.get('list_i', ''))}")
                    st.markdown(f"**List II:** {latex_to_unicode(q.get('list_ii', ''))}")

                # Correct answer
                answer = q.get("correct_answer", "")
                if answer:
                    st.markdown(f'<div class="review-answer">Correct Answer: {answer}</div>', unsafe_allow_html=True)

                # Explanation in expander
                explanation = q.get("explanation", "")
                if explanation:
                    with st.expander("Explanation"):
                        st.markdown(explanation)

                # Accuracy and Comment inputs
                acc_col, comment_col = st.columns([1, 3])
                with acc_col:
                    accuracy_options = ["", "Correct", "Incorrect", "Partially Correct", "Needs Review"]
                    current_acc = st.session_state.review_accuracies.get(idx, "")
                    acc_index = accuracy_options.index(current_acc) if current_acc in accuracy_options else 0
                    st.session_state.review_accuracies[idx] = st.selectbox(
                        "Accuracy",
                        accuracy_options,
                        index=acc_index,
                        key=f"acc_{idx}",
                    )
                with comment_col:
                    st.session_state.review_comments[idx] = st.text_area(
                        "Comment",
                        value=st.session_state.review_comments.get(idx, ""),
                        key=f"comment_{idx}",
                        height=80,
                        placeholder="Add your comment here..."
                    )

                st.markdown("")

            # Save & Download button
            st.markdown("---")
            if st.button("Save Comments & Download", type="primary", use_container_width=True, icon="💾"):
                try:
                    updated_bytes = update_excel_with_comments(
                        review_bytes,
                        st.session_state.review_comments,
                        st.session_state.review_accuracies,
                    )
                    st.download_button(
                        label="Download Updated Excel",
                        data=updated_bytes,
                        file_name=f"reviewed_{review_file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_reviewed",
                        type="secondary",
                        use_container_width=True,
                    )
                    st.success("Comments and accuracy saved! Click the download button above.")
                except Exception as e:
                    st.error(f"Failed to update Excel: {e}")
        elif review_file:
            st.warning("No questions found in the uploaded Excel file. Make sure it was exported from the Generate tab.")
