"""
NEET Test Generator - OpenAI API Wrapper
Generates exam questions from textbook PDFs using gpt-5-mini
"""

import base64
import io
import itertools
import json
import logging
import math
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from pypdf import PdfReader, PdfWriter

import prompts_biology
import prompts_chemistry

logger = logging.getLogger(__name__)


# ============================================================
# JSON / TEXT UTILITIES
# ============================================================

def _fix_latex_json(text: str) -> str:
    """Fix LaTeX backslash commands that break JSON parsing.

    LLMs often write $E^\circ$ instead of $E^\\circ$ in JSON strings.
    \\c is not a valid JSON escape, causing json.loads() to fail.
    This finds single backslashes NOT followed by valid JSON escape
    characters and doubles them so JSON parsing succeeds.
    """
    # Valid JSON escape chars after backslash: \ " / n r t b f u
    # Anything else (like \c in \circ, \D in \Delta) is invalid
    return re.sub(r'(?<!\\)\\(?![\\"/nrtbfu])', r'\\\\', text)


# ============================================================
# POST-PROCESSING FUNCTIONS (unchanged from OpenAI version)
# ============================================================

def _fix_unwrapped_latex(text: str) -> str:
    """Wrap common unwrapped LaTeX patterns in $...$ delimiters.

    The model sometimes outputs M^{2+} or H_2O without $...$.
    This catches those patterns and wraps them so they render properly.
    """
    if not text:
        return text

    # Skip if no LaTeX-like characters present
    if '^' not in text and '_' not in text and '\\' not in text:
        return text

    # Pattern: word^{...} or word_{...} not already inside $...$
    # Match sequences like Fe^{2+}, H_2O, M^{2+}/M that aren't wrapped
    def wrap_match(m):
        # Check if already inside $...$
        start = m.start()
        # Count $ signs before this match
        before = text[:start]
        dollar_count = before.count('$')
        if dollar_count % 2 == 1:
            # Inside a $...$ block already
            return m.group(0)
        return f'${m.group(0)}$'

    # Match: sequences containing ^{...} or _{...} with surrounding chemical context
    # e.g., Fe^{2+}, H_2O, M^{2+}/M, SO_4^{2-}
    text = re.sub(
        r'(?<!\$)([A-Za-z][A-Za-z0-9]*(?:[_^]\{[^}]+\}|[_^][0-9])[A-Za-z0-9_^{}+\-]*(?:/[A-Za-z][A-Za-z0-9_^{}+\-]*)*)(?!\}|\$)',
        wrap_match,
        text
    )

    # Fix double $$ from adjacent wrapping
    text = text.replace('$$', '$ $')

    return text


def _fix_chemical_formatting(questions: list) -> list:
    """Post-process questions to clean up structural formatting.

    Preserves LaTeX $...$ notation for frontend rendering.
    Wraps unwrapped LaTeX patterns (like M^{2+}) in $...$ delimiters.
    Handles numbered statement line breaks and MTC table formatting.
    """

    def _format_numbered_statements(text: str) -> str:
        """Insert line breaks before numbered statements when they're on one line.
        Handles both '1. ...' and '(1) ...' formats used in NEET questions.
        Avoids breaking mid-sentence numbers like '5d = 9.' or 'E° = 1.51'."""
        # Format 1: "(1) ... (2) ... (3) ..." — common in Hard MCQs
        text = re.sub(r'(?<!\n)\s+(\(\d+\)\s)', r'\n\1', text)
        # Format 2: "1. ... 2. ..." — only match if preceded by sentence end (. or :) or start
        text = re.sub(r'(?<=[.:?])\s+(\d+\.\s)', r'\n\1', text)
        return text

    def _format_mtc_question(text: str) -> str:
        """Parse MTC question text and reconstruct as a clean pipe table."""
        # Normalize: replace literal \n with actual newlines, then flatten to one line
        text = text.replace('\\n\\n', ' ').replace('\\n', ' ')
        flat = ' '.join(text.split())

        # Extract pairs: "A. [text] | I. [text]", "B. [text] | II. [text]", etc.
        pair_pattern = r'([A-D])\.\s*(.*?)\s*\|\s*(IV|III|II|I)\.\s*(.*?)(?=\s+[A-D]\.\s|Choose|$)'
        pairs = re.findall(pair_pattern, flat)

        if not pairs:
            return text  # Can't parse — return as-is

        # Extract header (everything before "A.")
        header_match = re.match(r'^(.*?)(?=\s*A\.)', flat)
        header = header_match.group(1).strip() if header_match else "Match List I with List II"
        # Clean header: remove "List I | List II" from it (we'll add it as table header)
        header = re.sub(r'\s*List\s+I\s*\|\s*List\s+II\s*', '', header).strip()
        if not header:
            header = "Match List I with List II"

        # Extract footer
        footer_match = re.search(r'(Choose the correct.*?)$', flat, re.IGNORECASE)
        footer = footer_match.group(1).strip() if footer_match else "Choose the correct answer from the options given below:"

        # Reconstruct as clean table
        lines = [header, "", "List I | List II"]
        for letter, list1, roman, list2 in pairs:
            lines.append(f"{letter}. {list1.strip()} | {roman}. {list2.strip()}")
        lines.append("")
        lines.append(footer)

        return '\n'.join(lines)

    for q in questions:
        if 'question_text' in q and isinstance(q['question_text'], str):
            # Fix unwrapped LaTeX (e.g., M^{2+} → $M^{2+}$)
            q['question_text'] = _fix_unwrapped_latex(q['question_text'])
            q_type = q.get('question_type', '').upper()
            if q_type == 'MATCH_THE_COLUMN':
                q['question_text'] = _format_mtc_question(q['question_text'])
            else:
                q['question_text'] = _format_numbered_statements(q['question_text'])

        if 'options' in q and isinstance(q['options'], dict):
            for key in q['options']:
                if isinstance(q['options'][key], str):
                    q['options'][key] = _fix_unwrapped_latex(q['options'][key])

    return questions


def _fix_duplicate_mtc_options(questions: list) -> list:
    """Post-process MTC questions to ensure all 4 options are unique.

    If two or more options have the same matching combination,
    replace the duplicate(s) with new valid permutations.
    """
    roman = ['I', 'II', 'III', 'IV']
    letters = ['A', 'B', 'C', 'D']

    def _normalize(opt_str: str) -> str:
        """Normalize option string for comparison (strip spaces, uppercase)."""
        return re.sub(r'\s+', '', opt_str.strip().upper())

    def _make_option_str(perm: list) -> str:
        """Create option string like 'A-IV, B-I, C-III, D-II' from a permutation of roman numerals."""
        return ', '.join(f'{letters[i]}-{perm[i]}' for i in range(4))

    for q in questions:
        q_type = q.get('question_type', '').upper()
        if q_type != 'MATCH_THE_COLUMN':
            continue

        options = q.get('options', {})
        if not options or len(options) < 4:
            continue

        # Get current option values
        opt_keys = ['a', 'b', 'c', 'd']
        opt_values = [options.get(k, '') for k in opt_keys]
        normalized = [_normalize(v) for v in opt_values]

        # Check for duplicates
        seen = {}
        duplicates = []
        for i, norm in enumerate(normalized):
            if norm in seen:
                duplicates.append(i)
            else:
                seen[norm] = i

        if not duplicates:
            continue

        logger.warning(f"[MTC-FIX] Q{q.get('question_id', '?')}: Found {len(duplicates)} duplicate option(s), generating replacements")

        # Generate all 24 permutations of roman numerals
        all_perms = [list(p) for p in itertools.permutations(roman)]

        # Remove permutations that match any existing non-duplicate option
        used_norms = set()
        for i, norm in enumerate(normalized):
            if i not in duplicates:
                used_norms.add(norm)

        available = [p for p in all_perms if _normalize(_make_option_str(p)) not in used_norms]
        random.shuffle(available)

        # Replace each duplicate with a new unique permutation
        for dup_idx in duplicates:
            if available:
                new_perm = available.pop()
                new_opt = _make_option_str(new_perm)
                used_norms.add(_normalize(new_opt))
                # Filter out any that now match
                available = [p for p in available if _normalize(_make_option_str(p)) not in used_norms]
                options[opt_keys[dup_idx]] = new_opt
                logger.info(f"[MTC-FIX] Q{q.get('question_id', '?')}: Replaced option ({dup_idx+1}) with {new_opt}")

    return questions


def _fix_sequential_mtc_mapping(questions: list) -> list:
    """Post-process MTC questions to fix sequential correct answers (A-I, B-II, C-III, D-IV).

    When the correct option has a sequential mapping, we shuffle the List II roman
    numeral assignments throughout the question text AND all options.
    """
    roman_numerals = ['I', 'II', 'III', 'IV']
    sequential_pattern = re.compile(
        r'A\s*[-–—]\s*I\s*,\s*B\s*[-–—]\s*II\s*,\s*C\s*[-–—]\s*III\s*,\s*D\s*[-–—]\s*IV',
        re.IGNORECASE
    )

    def _apply_numeral_swap(text: str, swap_map: dict) -> str:
        """Swap roman numerals in an option string using a mapping like {'I': 'III', 'III': 'I'}."""
        # Replace each roman numeral with a placeholder first to avoid double-swaps
        placeholders = {}
        result = text
        for old, new in swap_map.items():
            placeholder = f"__ROMAN_{old}__"
            placeholders[placeholder] = new
            # Match the roman numeral that follows a dash (part of A-I pattern)
            result = re.sub(rf'([-–—]\s*){re.escape(old)}(?!\w)', rf'\1{placeholder}', result)
        # Also handle standalone roman numerals after pipe/dot in question text table
        for old, new in swap_map.items():
            placeholder = f"__ROMAN_{old}__"
            # Match "I." or "II." etc at start of List II items
            result = re.sub(rf'(?<!\w){re.escape(old)}\.', f'{placeholder}.', result)
        # Replace placeholders with final values
        for placeholder, new in placeholders.items():
            result = result.replace(placeholder, new)
        return result

    for q in questions:
        q_type = q.get('question_type', '').upper()
        if q_type != 'MATCH_THE_COLUMN':
            continue

        options = q.get('options', {})
        correct_key = q.get('correct_answer', '').lower().strip()
        if correct_key not in options:
            continue

        correct_option_text = options[correct_key]

        # Check if the correct option is sequential (A-I, B-II, C-III, D-IV)
        if not sequential_pattern.search(correct_option_text):
            continue

        logger.warning(f"[MTC-SHUFFLE] Q{q.get('question_id', '?')}: Sequential correct answer detected ({correct_option_text}), shuffling List II")

        # Generate a random non-sequential permutation of roman numerals
        while True:
            shuffled = list(roman_numerals)
            random.shuffle(shuffled)
            # Ensure it's not sequential (I, II, III, IV)
            if shuffled != roman_numerals:
                break

        # Build swap map: old numeral → new numeral
        swap_map = {}
        for i, old in enumerate(roman_numerals):
            if old != shuffled[i]:
                swap_map[old] = shuffled[i]

        if not swap_map:
            continue

        # Apply swap to all 4 options
        for key in ['a', 'b', 'c', 'd']:
            if key in options:
                options[key] = _apply_numeral_swap(options[key], swap_map)

        # Apply swap to question text (List II labels in the table)
        if 'question_text' in q:
            q['question_text'] = _apply_numeral_swap(q['question_text'], swap_map)

        # Apply swap to explanation if it references roman numerals
        explanation = q.get('explanation', {})
        if isinstance(explanation, dict):
            for key in explanation:
                if isinstance(explanation[key], str):
                    explanation[key] = _apply_numeral_swap(explanation[key], swap_map)
        elif isinstance(explanation, str):
            q['explanation'] = _apply_numeral_swap(explanation, swap_map)

        logger.info(f"[MTC-SHUFFLE] Q{q.get('question_id', '?')}: Shuffled List II: {dict(zip(roman_numerals, shuffled))}. New correct: {options[correct_key]}")

    return questions


def _randomize_answer_positions(questions: list) -> list:
    """
    Post-process questions to ensure correct answers are distributed
    roughly equally across A, B, C, D. Applies to MCQ and MTC questions.
    AR questions have fixed option structure (a/b/c/d = specific answer types) and cannot be shuffled.
    """
    # Separate shufflable questions from AR (fixed structure)
    shufflable_indices = []
    for i, q in enumerate(questions):
        qtype = q.get("question_type", "").upper()
        # AR options are fixed (a=both true R explains, b=both true R doesn't explain, etc.)
        # MCQ and MTC options can be freely swapped
        if qtype not in ("ASSERTION_REASON", "ASSERTION-REASON", "AR"):
            shufflable_indices.append(i)

    if len(shufflable_indices) < 2:
        return questions

    # Build target distribution: near-equal across A, B, C, D
    n = len(shufflable_indices)
    base = n // 4
    remainder = n % 4
    letters = ["a", "b", "c", "d"]
    random.shuffle(letters)  # randomize which letters get the extra question
    target_counts = {}
    for i, l in enumerate(letters):
        target_counts[l] = base + (1 if i < remainder else 0)

    # Assign each question a target letter
    # Shuffle the indices so the reassignment is random, not always Q1→A, Q2→B...
    indices_shuffled = list(shufflable_indices)
    random.shuffle(indices_shuffled)

    assignments = []  # (question_index, target_letter)
    pos = 0
    for letter in ["a", "b", "c", "d"]:
        for _ in range(target_counts[letter]):
            assignments.append((indices_shuffled[pos], letter))
            pos += 1

    # Apply swaps where needed
    swaps_done = 0
    for q_idx, target_letter in assignments:
        q = questions[q_idx]
        current_answer = q.get("correct_answer", "").lower().strip()

        if current_answer == target_letter:
            continue  # already correct letter

        options = q.get("options", {})
        explanation = q.get("explanation", {})

        if current_answer in options and target_letter in options:
            # Swap the option content
            options[current_answer], options[target_letter] = options[target_letter], options[current_answer]
            # Swap the explanation content
            if isinstance(explanation, dict) and current_answer in explanation and target_letter in explanation:
                explanation[current_answer], explanation[target_letter] = explanation[target_letter], explanation[current_answer]
            # Update correct answer
            q["correct_answer"] = target_letter
            swaps_done += 1

    # Log final distribution
    final_dist = {"a": 0, "b": 0, "c": 0, "d": 0}
    for i in shufflable_indices:
        ans = questions[i].get("correct_answer", "").lower().strip()
        if ans in final_dist:
            final_dist[ans] += 1
    logger.info(f"[RANDOMIZE] {swaps_done} swaps applied. Final distribution: {final_dist}")

    return questions


# ============================================================
# PROMPT MODULE SELECTOR
# ============================================================

def _get_prompt_module(subject: str):
    """Return the correct prompts module based on the subject."""
    if subject.lower().strip() == "chemistry":
        return prompts_chemistry
    return prompts_biology


# ============================================================
# OPENAI API HELPERS
# ============================================================

def _api_call_with_retry(client, model, messages, max_completion_tokens, temperature, max_retries=3):
    """Make an OpenAI API call with retry logic for rate limits and connection errors.

    Uses escalating backoff: 2s, 4s, 8s.
    """
    wait_times = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
            )
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e).lower()
            is_retryable = (
                "ratelimit" in err_name.lower()
                or "rate" in err_str
                or "429" in err_str
                or "connection" in err_name.lower()
                or "timeout" in err_str
                or "unavailable" in err_str
                or "503" in err_str
                or "overloaded" in err_str
            )
            if attempt < max_retries and is_retryable:
                wait = wait_times[min(attempt, len(wait_times) - 1)]
                logger.warning(f"[RETRY] Attempt {attempt + 1} failed ({err_name}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    return None


def _extract_token_usage(response) -> dict:
    """Extract token usage from an OpenAI API response."""
    tokens = {}
    if hasattr(response, 'usage') and response.usage:
        u = response.usage
        tokens = {
            "input_tokens": getattr(u, 'prompt_tokens', 0) or 0,
            "output_tokens": getattr(u, 'completion_tokens', 0) or 0,
            "total_tokens": getattr(u, 'total_tokens', 0) or 0,
        }
    return tokens


def _parse_json_response(result_text: str) -> dict:
    """Parse JSON from a Gemini text response with progressive repair.

    Handles: markdown code blocks, LaTeX backslashes, truncated output.
    """
    clean_text = result_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    # If model output text before JSON, extract the JSON object
    if not clean_text.startswith("{"):
        json_start = clean_text.find("{")
        if json_start != -1:
            logger.info(f"[JSON FIX] Stripping {json_start} chars of non-JSON text before '{{'")
            clean_text = clean_text[json_start:]

    # Try direct parse first
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # Try fixing LaTeX backslashes
    try:
        result = json.loads(_fix_latex_json(clean_text))
        logger.info("JSON parse succeeded after fixing LaTeX backslashes")
        return result
    except json.JSONDecodeError:
        pass

    # If JSON was truncated (hit max_completion_tokens or model stopped mid-output), try to repair
    logger.info("[JSON FIX] Response appears truncated or malformed, attempting repair")

    repair_text = _fix_latex_json(clean_text)

    # Try progressively shorter cuts — find each "}" and try to close
    pos = len(repair_text)
    while pos > 0:
        pos = repair_text.rfind("}", 0, pos)
        if pos == -1:
            break
        truncated = repair_text[:pos + 1]
        for suffix in ["", "}", "]}", "]}}", "]}}}",  "]}]}"]:
            try:
                result = json.loads(truncated + suffix)
                # Verify it has questions
                if "questions" in result and len(result["questions"]) > 0:
                    logger.info(f"[JSON FIX] Repaired! Recovered {len(result['questions'])} question(s) with suffix: '{suffix}'")
                    return result
            except json.JSONDecodeError:
                continue

    return {
        "raw_response": result_text[:500],
        "parse_error": "Failed to parse response as JSON"
    }


# ============================================================
# PRICING CALCULATION
# ============================================================

# GPT-5 mini pricing (per million tokens) — in USD
GPT5_MINI_PRICING = {
    "input_per_million": 0.25,   # $0.25 per 1M input tokens
    "output_per_million": 2.00,  # $2.00 per 1M output tokens
}

# USD to INR conversion rate
USD_TO_INR = 87.0


def calculate_cost(token_usage: dict) -> dict:
    """Calculate estimated cost from token usage in INR.

    Args:
        token_usage: dict with 'input_tokens' and 'output_tokens'

    Returns:
        dict with input_cost, output_cost, total_cost (in INR)
    """
    input_tokens = token_usage.get("input_tokens", 0)
    output_tokens = token_usage.get("output_tokens", 0)

    input_cost_usd = (input_tokens / 1_000_000) * GPT5_MINI_PRICING["input_per_million"]
    output_cost_usd = (output_tokens / 1_000_000) * GPT5_MINI_PRICING["output_per_million"]

    input_cost = input_cost_usd * USD_TO_INR
    output_cost = output_cost_usd * USD_TO_INR
    total_cost = input_cost + output_cost

    return {
        "input_cost": round(input_cost, 4),
        "output_cost": round(output_cost, 4),
        "total_cost": round(total_cost, 4),
        "input_rate": f"₹{GPT5_MINI_PRICING['input_per_million'] * USD_TO_INR:.1f}/1M tokens",
        "output_rate": f"₹{GPT5_MINI_PRICING['output_per_million'] * USD_TO_INR:.1f}/1M tokens",
    }


# ============================================================
# PDF SPLITTING HELPERS
# ============================================================

def _get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Return total number of pages in a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def _split_pdf_pages(pdf_bytes: bytes, start_page: int, end_page: int) -> bytes:
    """Extract pages start_page to end_page (0-indexed, inclusive) and return as new PDF bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i in range(start_page, min(end_page + 1, len(reader.pages))):
        writer.add_page(reader.pages[i])
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _build_chunks(total_pages: int, question_count: int, chunk_size: int = 15):
    """Split pages into chunks and distribute questions proportionally.

    Returns list of (start_page, end_page, num_questions) tuples (0-indexed pages).
    """
    chunks = []
    for start in range(0, total_pages, chunk_size):
        end = min(start + chunk_size - 1, total_pages - 1)
        chunk_pages = end - start + 1
        chunk_q = max(1, round(question_count * chunk_pages / total_pages))
        chunks.append([start, end, chunk_q])

    # Adjust so total questions match exactly
    allocated = sum(c[2] for c in chunks)
    diff = question_count - allocated
    if diff != 0:
        # Add/subtract from the largest chunk
        largest_idx = max(range(len(chunks)), key=lambda i: chunks[i][2])
        chunks[largest_idx][2] += diff

    return [(c[0], c[1], c[2]) for c in chunks]


def _generate_single_chunk(client, model, pdf_bytes, formatted_prompt, user_instruction,
                           question_count, max_completion_tokens, temperature, chunk_label=""):
    """Run a single API call for one PDF chunk. Returns (questions_list, token_usage, generation_time)."""
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    messages = [
        {"role": "system", "content": formatted_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": "textbook.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf_base64}",
                    },
                },
                {"type": "text", "text": user_instruction},
            ],
        },
    ]

    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
    logger.info(f"[CHUNK {chunk_label}] PDF: {pdf_size_mb:.1f}MB | Questions: {question_count} | max_tokens: {max_completion_tokens}")

    gen_start = time.time()
    response = _api_call_with_retry(client, model, messages, max_completion_tokens, temperature)
    generation_time = round(time.time() - gen_start, 1)

    if response is None:
        logger.error(f"[CHUNK {chunk_label}] API call failed")
        return [], {}, generation_time

    token_usage = _extract_token_usage(response)
    result_text = response.choices[0].message.content or ""
    logger.info(f"[CHUNK {chunk_label}] Response: {len(result_text)} chars in {generation_time}s")

    result = _parse_json_response(result_text)
    questions = result.get("questions", [])
    logger.info(f"[CHUNK {chunk_label}] Parsed {len(questions)} questions")

    return questions, token_usage, generation_time


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def generate_neet_test_from_pdf(
    pdf_bytes: bytes,
    subject: str = "biology",
    difficulty: str = "hard",
    question_count: int = 5,
    question_type: str = "mcq",
    model: str = "gpt-5-mini",
    temperature: float = 1.0,
    max_completion_tokens: int = 70000,
    api_key: str = None,
) -> dict:
    """
    Generate NEET test questions from a PDF.

    For large PDFs (>20 pages), splits into parallel chunks for faster generation.
    For small PDFs (≤20 pages), uses a single API call.
    """
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)

    # Get the prompt from the correct module based on subject
    effective_type = question_type if question_type != "combination" else "mcq"
    prompt_module = _get_prompt_module(subject)

    if (effective_type, difficulty) not in prompt_module.PROMPTS_CONFIG:
        raise ValueError(f"No prompt configured for ({effective_type}, {difficulty}) in {prompt_module.__name__}")

    logger.info(f"[PROMPT] Using {prompt_module.__name__} prompt for ({effective_type}, {difficulty})")

    # Check if parallel processing should be used (large PDF > 20 pages)
    total_pages = _get_pdf_page_count(pdf_bytes)
    use_parallel = total_pages > 20

    pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
    logger.info(f"[GENERATE] PDF size: {pdf_size_mb:.1f}MB | Pages: {total_pages} | Model: {model}")
    logger.info(f"[SETTINGS] subject={subject}, difficulty={difficulty}, type={question_type}, count={question_count}")

    if use_parallel:
        # ── PARALLEL GENERATION (large PDF) ──
        chunks = _build_chunks(total_pages, question_count, chunk_size=15)
        logger.info(f"[PARALLEL] Splitting into {len(chunks)} chunks: {[(c[0]+1, c[1]+1, c[2]) for c in chunks]}")
        logger.info("=" * 80)

        gen_start = time.time()
        all_questions = []
        total_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        def _run_chunk(chunk_info):
            start_page, end_page, chunk_q = chunk_info
            chunk_label = f"p{start_page+1}-{end_page+1}"

            # Split PDF to just this chunk's pages
            chunk_pdf = _split_pdf_pages(pdf_bytes, start_page, end_page)

            # Get prompt for this chunk's question count
            chunk_prompt = prompt_module.get_prompt(effective_type, difficulty, subject, chunk_q)

            # Build instruction for this chunk
            chunk_instruction = (
                f"Generate {chunk_q} {difficulty} {effective_type.replace('_', ' ')} questions "
                f"from this textbook PDF. Each question MUST test a COMPLETELY DIFFERENT concept — "
                "no two questions can cover the same topic, fact, or principle even if rephrased.\n\n"
                "ACCURACY IS #1 PRIORITY — every correct_answer MUST match the PDF. If unsure, skip that question.\n\n"
                "RULES:\n"
                "- Each question tests a DIFFERENT concept from a DIFFERENT page/section.\n"
                "- Spread across ALL pages of this PDF.\n"
                "- Every question has EXACTLY ONE correct answer. The other 3 must be clearly wrong.\n"
                "- NO ambiguous questions where 2 options could be correct.\n"
            )

            # Calculate tokens for this chunk (varies by question type)
            if question_type == "match_the_column":
                tpq = 3500
            elif question_type == "assertion_reason":
                tpq = 2500 if difficulty == "hard" else 2000
            else:
                tpq = 2500 if difficulty == "hard" else 1500
            chunk_max_tokens = max(4096, chunk_q * tpq + 1000)
            chunk_max_tokens = min(max_completion_tokens, chunk_max_tokens)

            return _generate_single_chunk(
                client, model, chunk_pdf, chunk_prompt, chunk_instruction,
                chunk_q, chunk_max_tokens, temperature, chunk_label
            )

        # Run all chunks in parallel
        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            results = list(executor.map(_run_chunk, chunks))

        # Merge results from all chunks
        for questions, token_usage, _ in results:
            all_questions.extend(questions)
            for key in total_token_usage:
                total_token_usage[key] += token_usage.get(key, 0)

        generation_time = round(time.time() - gen_start, 1)

        # Re-number question IDs sequentially
        for i, q in enumerate(all_questions, 1):
            q["question_id"] = i

        total = len(all_questions)
        logger.info("=" * 80)
        logger.info(f"[PARALLEL DONE] Generated {total} questions in {generation_time}s across {len(chunks)} chunks")
        logger.info(f"[TOKENS] Input: {total_token_usage['input_tokens']:,}, Output: {total_token_usage['output_tokens']:,}, Total: {total_token_usage['total_tokens']:,}")
        logger.info("=" * 80)

        # Build result
        result = {
            "questions": all_questions,
            "test_metadata": {}
        }
        token_usage = total_token_usage

    else:
        # ── SINGLE API CALL (small PDF ≤ 20 pages) ──
        formatted_prompt = prompt_module.get_prompt(effective_type, difficulty, subject, question_count)

        user_instruction = (
            f"Generate {question_count} {difficulty} {effective_type.replace('_', ' ')} questions "
            f"from this textbook PDF. Each question MUST test a COMPLETELY DIFFERENT concept — "
            "no two questions can cover the same topic, fact, or principle even if rephrased.\n\n"
            "ACCURACY IS #1 PRIORITY — every correct_answer MUST match the PDF. If unsure, skip that question.\n\n"
            "RULES:\n"
            "- Each question tests a DIFFERENT concept from a DIFFERENT page/section.\n"
            "- Spread across ALL pages — first third, middle third, last third.\n"
            "- Every question has EXACTLY ONE correct answer. The other 3 must be clearly wrong.\n"
            "- NO ambiguous questions where 2 options could be correct.\n"
        )

        # Dynamic max_completion_tokens
        if question_type == "match_the_column":
            tokens_per_q = 3500
        elif question_type == "assertion_reason":
            tokens_per_q = 2500 if difficulty == "hard" else 2000
        else:
            tokens_per_q = 2500 if difficulty == "hard" else 1500
        dynamic_max_completion_tokens = max(4096, question_count * tokens_per_q + 1000)
        effective_max_completion_tokens = min(max_completion_tokens, dynamic_max_completion_tokens)

        # Encode PDF as base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": formatted_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": "textbook.pdf",
                            "file_data": f"data:application/pdf;base64,{pdf_base64}",
                        },
                    },
                    {"type": "text", "text": user_instruction},
                ],
            },
        ]

        logger.info(f"[GENERATE] max_completion_tokens: {effective_max_completion_tokens}")
        logger.info("=" * 80)

        gen_start = time.time()
        response = _api_call_with_retry(client, model, messages, effective_max_completion_tokens, temperature)
        generation_time = round(time.time() - gen_start, 1)

        if response is None:
            logger.error("[GENERATE] All API attempts failed")
            return {"parse_error": "All API attempts failed", "raw_response": ""}

        token_usage = _extract_token_usage(response)
        if token_usage:
            logger.info(f"[TOKENS] Input: {token_usage['input_tokens']:,}, Output: {token_usage['output_tokens']:,}, Total: {token_usage['total_tokens']:,}")

        result_text = response.choices[0].message.content or ""
        logger.info(f"[RESPONSE] Length: {len(result_text)} chars")
        if len(result_text) > 200:
            logger.info(f"[RESPONSE] Ends with: ...{result_text[-200:]!r}")

        result = _parse_json_response(result_text)

        if "parse_error" in result:
            logger.error(f"[GENERATE] PARSE ERROR: {result.get('parse_error')}")
            logger.error(f"[GENERATE] Raw response: {result.get('raw_response', '')[:300]}...")
            return result

        total = len(result.get("questions", []))
        logger.info("=" * 80)
        logger.info(f"[DONE] Generated {total} questions in {generation_time}s")
        logger.info("=" * 80)

    # ── POST-PROCESSING (both paths) ──
    if "questions" in result:
        # Log generated questions
        for q in result["questions"]:
            if "question_text" in q:
                source_info = q.get("source_info", {}) or {}
                page = source_info.get("page_or_section", "N/A")
                concepts = source_info.get("key_concepts", [])
                logger.info(f"  Q{q.get('question_id', '?')} ({q.get('question_type', 'unknown')}): {q['question_text'][:100]}...")
                logger.info(f"    Source: {page} | Concepts: {concepts if concepts else 'N/A'}")

        result["questions"] = _fix_chemical_formatting(result["questions"])
        result["questions"] = _fix_duplicate_mtc_options(result["questions"])
        result["questions"] = _fix_sequential_mtc_mapping(result["questions"])
        result["questions"] = _randomize_answer_positions(result["questions"])

        if "test_metadata" not in result:
            result["test_metadata"] = {}
        result["test_metadata"]["total_questions"] = len(result["questions"])
        result["test_metadata"]["requested_questions"] = question_count
        result["test_metadata"]["question_type"] = question_type
        result["test_metadata"]["generation_time"] = generation_time
        result["test_metadata"]["parallel_chunks"] = len(chunks) if use_parallel else 1
        cost = calculate_cost(token_usage) if token_usage else {}
        result["test_metadata"]["token_usage"] = {
            "generation": token_usage,
            "total_input": token_usage.get("input_tokens", 0),
            "total_output": token_usage.get("output_tokens", 0),
            "grand_total": token_usage.get("total_tokens", 0),
            "cost": cost,
        }
        if cost:
            logger.info(f"[COST] Input: ₹{cost['input_cost']:.4f} | Output: ₹{cost['output_cost']:.4f} | Total: ₹{cost['total_cost']:.4f}")
        logger.info(f"[TOKENS SUMMARY] Generation: {token_usage.get('total_tokens', 'N/A')} | Time: {generation_time}s")

    return result
