"""
Text processing utilities — cleaning, transliteration, and gibberish detection.

This is master's library/utils.py reorganized into the utils/ package.
All functions, regex patterns, and logic are preserved exactly.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Precompiled regular expressions for gibberish detection
HTML_ENTITY_RE = re.compile(r'&[a-z]+;|&[lg]t;|&amp;|&quot;')
RANDOM_CHARS_RE = re.compile(r'''[^\w\s\.,!\?\-\:;"'(){}\[\]/\\№%]''')
SINGLE_CHAR_RE = re.compile(r'\b[а-яёa-z]\b', re.IGNORECASE)
CYRILLIC_RE = re.compile(r'[а-яё]', re.IGNORECASE)
LATIN_RE = re.compile(r'[a-z]', re.IGNORECASE)
SPACED_SINGLE_CHARS_RE = re.compile(
    r'\b[а-яёa-z]\s+[а-яёa-z]\s+[а-яёa-z]', re.IGNORECASE
)
CHAOS_PATTERNS = [
    re.compile(r'\b[А-Я]{1,3}\s+[а-я]\s+[А-Я]{1,3}\s+\d+'),
    re.compile(r'\d+\s*[)]\s*,\s*[А-Я][а-я]+\s*[)]\s*\d+'),
    re.compile(r'[А-Я]{2,}\s+[A-Z]{2,}\s+[A-Z]{2,}')
]
REPETITIVE_PATTERN_RE = re.compile(r'(.)\1{3,}')
NON_WORD_CHARS_RE = re.compile(r'[^\w\s]')
QUOTE_SPAM_RE = re.compile(r'''["']{2,}''')
PIPE_EQUALS_RE = re.compile(r'[|=]{3,}')
CONSONANT_CLUSTER_RE = re.compile(
    r'\b[bcdfghjklmnpqrstvwxyzбвгджзйклмнпрстфхцчшщ]{4,}\b', re.IGNORECASE
)
OCR_ERROR_CHARS_RE = re.compile(r'[Ўўғқҳ]{2,}')
MOSTLY_NUMERIC_WORD_RE = re.compile(r'^\d+[а-яёa-z]*\d*$', re.IGNORECASE)
WEIRD_COMBINATION_RE = re.compile(r'[=&%\\]')
LEGITIMATE_LINE_RE = re.compile(r'\d{2}\.\d{2}\.\d{4}|\d{6}-\d+|998\d{9}')
LEGITIMATE_NUMERIC_RE = re.compile(r'\d{2}\.\d{2}\.\d{4}|\d{9,}|\d+-\d+')
EXCEPTION_PATTERNS = [
    re.compile(r'^[А-ЯЁA-Z]\.[А-ЯЁA-Z]\.[А-Яа-яёA-Za-z]+$'),
    re.compile(r'^\d{2}\.\d{2}\.\d{4}'),
    re.compile(r'^998\d{9}$'),
    re.compile(r'^\d{6}-\d+$'),
    re.compile(r'^\d+-[А-Яа-я]+$'),
    re.compile(r'^[А-Яа-я]+-\d+$'),
]

# Common representations of null dates for quick membership checks
NULL_DATE_STRINGS = {"null", "none", ""}


def is_latin(s):
    """Check if string contains Latin characters."""
    return bool(re.search('[A-Za-z]', s))


def is_cyrillic(s):
    """Check if string contains Cyrillic characters."""
    return bool(re.search('[А-Яа-я]', s))


def translite(text: str) -> str:
    """Transliterate Cyrillic text to Latin using a simple mapping."""
    cyrillic_to_latin = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'J', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'X', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sh',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        # Uzbek specific characters
        'ў': 'o\'', 'ҳ': 'h', 'қ': 'q', 'ғ': 'g\'',
        'Ў': 'O\'', 'Ҳ': 'H', 'Қ': 'Q', 'Ғ': 'G\''
    }

    result = ''.join(cyrillic_to_latin.get(char, char) for char in text)
    return result


def reverse_translite(text: str) -> str:
    """Transliterate Latin Uzbek text to Cyrillic."""
    # Multi-char mappings must be checked first (order matters)
    latin_to_cyrillic_multi = [
        ("sh", "ш"), ("ch", "ч"), ("g'", "ғ"), ("o'", "ў"),
        ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ts", "ц"),
        ("Sh", "Ш"), ("Ch", "Ч"), ("G'", "Ғ"), ("O'", "Ў"),
        ("Yo", "Ё"), ("Yu", "Ю"), ("Ya", "Я"), ("Ts", "Ц"),
        ("SH", "Ш"), ("CH", "Ч"),
    ]
    latin_to_cyrillic_single = {
        'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
        'j': 'ж', 'z': 'з', 'i': 'и', 'y': 'й', 'k': 'к', 'l': 'л',
        'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с',
        't': 'т', 'u': 'у', 'f': 'ф', 'x': 'х', 'h': 'ҳ', 'q': 'қ',
        'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д', 'E': 'Е',
        'J': 'Ж', 'Z': 'З', 'I': 'И', 'Y': 'Й', 'K': 'К', 'L': 'Л',
        'M': 'М', 'N': 'Н', 'O': 'О', 'P': 'П', 'R': 'Р', 'S': 'С',
        'T': 'Т', 'U': 'У', 'F': 'Ф', 'X': 'Х', 'H': 'Ҳ', 'Q': 'Қ',
    }
    result = text
    for lat, cyr in latin_to_cyrillic_multi:
        result = result.replace(lat, cyr)
    return ''.join(latin_to_cyrillic_single.get(c, c) for c in result)


def normalize_date(date_string):
    """Normalize a date string to DD.MM.YYYY format, or None if invalid."""
    if not date_string or date_string.lower() in NULL_DATE_STRINGS:
        return None
    date_pattern = r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
    match = re.search(date_pattern, date_string)
    return match.group(0) if match else None


def clean_phone(phone_list):
    """Clean and validate phone numbers. Returns list or None."""
    if not phone_list:
        return None
    phone_pattern = r'\+?\d{9,12}'
    updated_phone_list = []
    for phone in phone_list:
        match = re.search(phone_pattern, phone.strip())
        if match:
            cleaned_phone = match.group(0)
            if len(cleaned_phone) >= 12 and cleaned_phone.startswith('1'):
                cleaned_phone = cleaned_phone[1:]
            updated_phone_list.append(cleaned_phone)
    return updated_phone_list if updated_phone_list else None


def is_valid_email(email):
    """Validate email address format."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def is_gibberish_text(text: str, threshold: float = 0.4) -> bool:
    """
    Detect if text is gibberish based on various heuristics.
    Handles legitimate Cyrillic and Latin text properly.
    """
    if not text or len(text.strip()) < 10:
        return False

    clean_text = text.strip()
    words = clean_text.split()

    if len(words) == 0:
        return True

    total_chars = len(clean_text)
    gibberish_indicators = 0

    # 1. HTML entities
    html_entities = len(HTML_ENTITY_RE.findall(clean_text))
    gibberish_indicators += html_entities * 6

    # 2. Random characters and symbols
    random_chars = RANDOM_CHARS_RE.findall(clean_text)
    gibberish_indicators += len(random_chars)

    # 3. Single characters separated by spaces (OCR artifacts)
    single_chars = SINGLE_CHAR_RE.findall(clean_text)
    if len(words) > 0 and len(single_chars) > len(words) * 0.5:
        gibberish_indicators += len(single_chars) * 2

    # 4. Random script mixing in same phrase/line
    script_chaos = 0
    text_parts = clean_text.split()
    for i in range(len(text_parts) - 1):
        curr_word = text_parts[i]
        next_word = text_parts[i + 1]

        curr_has_cyr = bool(CYRILLIC_RE.search(curr_word))
        curr_has_lat = bool(LATIN_RE.search(curr_word))
        next_has_cyr = bool(CYRILLIC_RE.search(next_word))
        next_has_lat = bool(LATIN_RE.search(next_word))

        if ((curr_has_cyr and not curr_has_lat) and (next_has_lat and not next_has_cyr)) or \
           ((curr_has_lat and not curr_has_cyr) and (next_has_cyr and not next_has_lat)):
            if len(curr_word) <= 3 or len(next_word) <= 3:
                script_chaos += 1

    gibberish_indicators += script_chaos * 4

    # 5. Mixed scripts within individual words
    mixed_script_words = 0
    for word in words:
        if len(word) > 2:
            has_cyrillic = bool(CYRILLIC_RE.search(word))
            has_latin = bool(LATIN_RE.search(word))
            if has_cyrillic and has_latin:
                mixed_script_words += 1

    if len(words) > 0 and mixed_script_words > len(words) * 0.2:
        gibberish_indicators += mixed_script_words * 4

    # 6. Random alphanumeric chaos
    chaos_count = 0
    for pattern in CHAOS_PATTERNS:
        matches = pattern.findall(clean_text)
        chaos_count += len(matches)

    if chaos_count > 0 and not LEGITIMATE_LINE_RE.search(clean_text):
        gibberish_indicators += chaos_count * 6

    # 7. Repetitive character patterns
    repetitive_patterns = REPETITIVE_PATTERN_RE.findall(clean_text)
    gibberish_indicators += len(repetitive_patterns) * 4

    # 8. Excessive very short words
    very_short_words = [w for w in words if len(w) <= 2 and w.isalpha()]
    if len(words) > 0 and len(very_short_words) > len(words) * 0.5:
        gibberish_indicators += len(very_short_words) * 2

    # 9. Spaced single chars
    spaced_single_chars = SPACED_SINGLE_CHARS_RE.findall(clean_text)
    gibberish_indicators += len(spaced_single_chars) * 6

    # 10. Lines with mostly punctuation
    non_word_chars = len(NON_WORD_CHARS_RE.findall(clean_text))
    if total_chars > 0 and non_word_chars > total_chars * 0.4:
        gibberish_indicators += non_word_chars * 0.5

    # 11. Quote spam
    quote_spam = len(QUOTE_SPAM_RE.findall(clean_text))
    gibberish_indicators += quote_spam * 3

    # 12. Pipe/equals
    pipe_equals = len(PIPE_EQUALS_RE.findall(clean_text))
    if pipe_equals > 0:
        gibberish_indicators += pipe_equals * 4

    # 13. Random consonant clusters
    consonant_clusters = CONSONANT_CLUSTER_RE.findall(clean_text)
    gibberish_indicators += len(consonant_clusters) * 4

    # 14. OCR-error prone characters
    ocr_error_chars = len(OCR_ERROR_CHARS_RE.findall(clean_text))
    gibberish_indicators += ocr_error_chars * 5

    # 15. Mostly-numeric lines
    if len(words) > 3 and not LEGITIMATE_NUMERIC_RE.search(clean_text):
        mostly_numeric_words = [w for w in words if MOSTLY_NUMERIC_WORD_RE.match(w)]
        if len(mostly_numeric_words) > len(words) * 0.7:
            gibberish_indicators += len(mostly_numeric_words) * 2

    # 16. Encoding errors
    if len(words) >= 3:
        weird_combinations = 0
        for word in words:
            if 2 <= len(word) <= 4 and WEIRD_COMBINATION_RE.search(word):
                weird_combinations += 1

        if weird_combinations >= 2:
            gibberish_indicators += weird_combinations * 6

    # 17. Exceptions for legitimate content
    for pattern in EXCEPTION_PATTERNS:
        if pattern.search(clean_text.strip()):
            gibberish_indicators = max(0, gibberish_indicators - 12)
            break

    gibberish_ratio = gibberish_indicators / max(total_chars, 1)
    return gibberish_ratio > threshold


def clean_extracted_content(content: str) -> str:
    """Clean extracted content by removing gibberish text and excessive noise."""
    if not content:
        return content

    paragraphs = content.split('\n\n')
    clean_paragraphs = []
    lines_buffer: list[str] = []
    clean_lines_buffer: list[str] = []

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if is_gibberish_text(paragraph):
            logger.info(f"Filtered out gibberish paragraph: {paragraph[:100]}...")
            continue

        lines_buffer[:] = paragraph.split('\n')
        clean_lines_buffer.clear()

        for line in lines_buffer:
            line = line.strip()
            if not line:
                continue

            if is_gibberish_text(line):
                logger.info(f"Filtered out gibberish line: {line[:50]}...")
                continue

            line = re.sub(r'\s+', ' ', line)
            clean_lines_buffer.append(line)

        if clean_lines_buffer:
            clean_paragraphs.append('\n'.join(clean_lines_buffer))

    return '\n\n'.join(clean_paragraphs)
