"""
Streamlit UI for Testing NEET Question Generator
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

# Initialize session state
if "generator_result" not in st.session_state:
    st.session_state.generator_result = None
if "generation_time" not in st.session_state:
    st.session_state.generation_time = None


# Load API key from environment variable
api_key = os.getenv("OPENAI_API_KEY")
model = "gpt-5-mini"
max_completion_tokens = 80000

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown('<div class="sidebar-section">PDF Input</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        accept_multiple_files=False,
        help="Upload a textbook chapter PDF (max 50MB, up to 1000 pages)",
        label_visibility="collapsed"
    )

    pdf_bytes = None
    if uploaded_file is not None:
        pdf_bytes = uploaded_file.getvalue()
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        st.success(f"Uploaded: {uploaded_file.name} ({file_size_mb:.1f} MB)")

        if file_size_mb > 50:
            st.error("PDF is too large. Maximum size is 50MB.")
            pdf_bytes = None

    st.divider()
    st.markdown('<div class="sidebar-section">Configuration</div>', unsafe_allow_html=True)

    subject = st.selectbox(
        "Subject",
        ["biology", "chemistry"],
        index=0,
        format_func=lambda x: x.title()
    )

    col_diff, col_type = st.columns(2)
    with col_diff:
        difficulty = st.selectbox(
            "Difficulty",
            ["easy", "medium", "hard"],
            index=2
        )
    with col_type:
        question_type = st.selectbox(
            "Type",
            ["combination", "mcq", "assertion_reason", "match_the_column"],
            index=0,
            format_func=lambda x: {
                "combination": "Mixed",
                "mcq": "MCQ",
                "assertion_reason": "A-R",
                "match_the_column": "Match"
            }.get(x, x)
        )

    question_count = st.number_input(
        "Number of Questions",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def render_match_the_column(text: str):
    """Dedicated renderer for Match the Column questions. Handles all formats."""
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


def render_test_view(result: dict):
    """Render questions in a polished test paper view."""

    if "parse_error" in result:
        st.error(f"**Parse Error:** {result.get('parse_error')}")
        st.code(result.get('raw_response', ''), language="text")
        return

    # --- Test Header ---
    if "test_metadata" in result:
        meta = result["test_metadata"]

        # Stat cards
        # Format generation time
        gen_time = st.session_state.get('generation_time')
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

            cost_label = f" — Cost: ₹{total_cost:.2f}" if total_cost else ""
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
                        st.markdown(f"- Input: **₹{cost.get('input_cost', 0):.2f}** ({cost.get('input_rate', '')})")
                        st.markdown(f"- Output: **₹{cost.get('output_cost', 0):.2f}** ({cost.get('output_rate', '')})")
                        st.markdown(f"- **Total: ₹{total_cost:.2f}**")
                    else:
                        st.markdown("N/A")
                with tok_cols[2]:
                    st.markdown("**Summary**")
                    st.markdown(f"- Grand Total Tokens: **{grand_total:,}**")
                    if total_cost:
                        st.markdown(f"- **Estimated Cost: ₹{total_cost:.2f}**")
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
            q_text = q.get('question_text', '')

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

            # Question text — st.markdown renders LaTeX $...$ natively
            if q_type == 'MATCH_THE_COLUMN':
                render_match_the_column(q_text)
            else:
                # Normalize escaped newlines
                formatted = q_text.replace('\\n\\n', '\n\n').replace('\\n', '\n')
                # Bold non-empty lines
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

            # Options — st.markdown renders LaTeX $...$ in options too
            if "options" in q:
                options = q["options"]
                for key in ['a', 'b', 'c', 'd']:
                    if key in options:
                        val = options[key]
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
# MAIN CONTENT
# ============================================================
has_pdf = pdf_bytes is not None

if not has_pdf:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-state-icon">📄</div>
        <div class="empty-state-title">No PDF uploaded yet</div>
        <div class="empty-state-text">Upload a textbook PDF in the sidebar to get started</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Action button
    generate_btn = st.button(
        "Generate Test",
        type="primary",
        use_container_width=True,
        icon="🚀"
    )

    st.markdown("")

    # --- Generate Test ---
    if generate_btn:
        logger.info("=== Generate Test button clicked ===")
        if not api_key:
            logger.warning("No API key provided")
            st.error("Please set your OPENAI_API_KEY environment variable in .env")
        else:
            logger.info(f"Starting generation: subject={subject}, difficulty={difficulty}, type={question_type}, count={question_count}")
            with st.spinner(f"Generating {question_count} questions from PDF..."):
                start_time = time.time()
                try:
                    result = generate_neet_test_from_pdf(
                        pdf_bytes=pdf_bytes,
                        subject=subject,
                        difficulty=difficulty,
                        question_count=question_count,
                        question_type=question_type,
                        model=model,
                        max_completion_tokens=max_completion_tokens,
                        api_key=api_key,
                    )

                    elapsed = time.time() - start_time
                    if result:
                        logger.info(f"Generation complete! Got {len(result.get('questions', []))} questions in {elapsed:.1f}s")
                        st.session_state.generator_result = result
                        st.session_state.generation_time = elapsed
                except Exception as e:
                    import traceback
                    elapsed = time.time() - start_time
                    logger.error(f"Generation failed after {elapsed:.1f}s: {type(e).__name__}: {e}")
                    logger.error(traceback.format_exc())
                    st.error(f"Error: {type(e).__name__}: {e}")
                    st.code(traceback.format_exc())

# ============================================================
# RESULTS DISPLAY
# ============================================================
if st.session_state.generator_result:
    render_test_view(st.session_state.generator_result)

    with st.expander("Raw JSON"):
        st.code(json.dumps(st.session_state.generator_result, indent=2, ensure_ascii=False), language="json")
