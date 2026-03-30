from openai import AsyncOpenAI
import re
import yaml
from functools import lru_cache
from typing import Optional
import logging
from pydantic import BaseModel

from core.config import get_settings

from utils.text import (
    is_cyrillic,
    is_latin,
    translite,
    reverse_translite,
    normalize_date,
    clean_phone,
    is_valid_email,
)

# Load centralized settings (cached singleton)
_settings = get_settings()

# Initializing clients
openai = AsyncOpenAI(
  base_url=_settings.openai_api_base_url,
  api_key=_settings.openai_api_key,
)

logger = logging.getLogger(__name__)

MODEL = "gpt-5.4-mini"


# ── Pydantic response models for structured outputs ──────────

class AuthorInfo(BaseModel):
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    phones: list[str] = []
    date_when_document_was_written: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    date_of_issue: Optional[str] = None

class DocumentTypeResponse(BaseModel):
    type: str = ""

class PersonInfo(BaseModel):
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""

class CaseInfoResponse(BaseModel):
    case_number: Optional[str] = None
    suspect: Optional[PersonInfo] = None
    victim: Optional[PersonInfo] = None
    claimant: Optional[PersonInfo] = None

class Article(BaseModel):
    article: int
    part: Optional[int] = None
    clause: Optional[str] = None

class ArticlesResponse(BaseModel):
    articles: list[Article] = []

class IssuesResponse(BaseModel):
    issues: list[str] = []
    keywords: list[str] = []

class DepartmentSelection(BaseModel):
    department_id: Optional[str] = None
    reasoning: str = ""
    confidence: int = 0

class SummaryResponse(BaseModel):
    summary: str

class EntityTypeResponse(BaseModel):
    entity_type: str = ""

class RepeatedRequestResponse(BaseModel):
    is_repeated: bool = False
    dates: list[str] = []


# Precompiled regular expressions for efficiency
NON_WORD_SPACE_RE = re.compile(r'[^\w\s]')
MULTI_SPACE_RE = re.compile(r'\s+')


# Uzbek Latin transliteration variants (LLM output vs YAML canonical forms)
_UZBEK_LATIN_VARIANTS = [
    ('kh', 'x'),     # bukhoro → buxoro, khorazm → xorazm
    ('gh', 'g\''),    # ferghana → farg'ona
    ('sh', 'sh'),     # already consistent, but keep for completeness
    ('yo', 'yo'),
    ('ch', 'ch'),
]

# English→Uzbek Latin region name aliases (LLM often returns English transliterations)
_ENGLISH_REGION_ALIASES: dict[str, str] = {
    "surkhandarya": "surxondaryo",
    "surkhandaryo": "surxondaryo",
    "surxandarya": "surxondaryo",
    "kashkadarya": "qashqadaryo",
    "kashkadaryo": "qashqadaryo",
    "karakalpakstan": "qoraqalpog'iston",
    "karakalpakistan": "qoraqalpog'iston",
    "fergana": "farg'ona",
    "ferghana": "farg'ona",
    "khorezm": "xorazm",
    "khorazm": "xorazm",
    "bukhara": "buxoro",
    "navoi": "navoiy",
    "syrdarya": "sirdaryo",
    "tashkent": "toshkent",
    "andijan": "andijon",
    "samarkand": "samarqand",
}


def _normalize_uzbek_latin(name: str) -> str:
    """Normalize common Uzbek Latin transliteration variants to canonical form."""
    for variant, canonical in _UZBEK_LATIN_VARIANTS:
        if variant != canonical:
            name = name.replace(variant, canonical)
    return name


def _fuzzy_normalize(name: str) -> str:
    """Aggressively normalize for fuzzy matching: strip apostrophes, collapse ambiguous chars.

    Handles Russian Cyrillic→Latin drift (к→k vs қ→q, у→u vs ў→o') by merging
    ambiguous consonants/vowels into a single canonical form.
    """
    # Strip all apostrophes and quotes first
    s = name.replace("'", "").replace("'", "").replace("`", "")
    # Collapse k/q ambiguity (Russian к maps to 'k', Uzbek қ maps to 'q')
    s = s.replace("q", "k")
    # Collapse g'/g ambiguity
    s = s.replace("gh", "g")
    # Collapse u/o ambiguity (Russian у→u, Uzbek ў→o' → after apostrophe strip → o)
    # Only collapse standalone 'u' to 'o' wouldn't work universally, so instead
    # normalize both to same vowel
    s = s.replace("u", "o")
    return s




REASONING_EFFORT = "medium"



@lru_cache(maxsize=None)
def _load_yaml(path: str) -> str:
    """Load YAML file contents with caching."""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()

def load_yaml_data(file_path: Optional[str] = None):
    """Load regions and districts from YAML files and return name-to-ID mappings."""
    if file_path:
        # Load specific YAML file
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    # Load regions
    regions_path = 'data/regions.yaml'
    with open(regions_path, 'r', encoding='utf-8') as f:
        regions_data = yaml.safe_load(f)

    # Load districts
    districts_path = 'data/districts.yaml'
    with open(districts_path, 'r', encoding='utf-8') as f:
        districts_data = yaml.safe_load(f)

    # Create name-to-ID mappings
    region_name_to_id = {name.lower(): region_id for region_id, name in regions_data.items()}
    district_name_to_id = {name.lower(): district_id for district_id, name in districts_data.items()}

    return region_name_to_id, district_name_to_id


def load_departments_data(file_path: str):
    """Load departments from YAML file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def chunk_departments(departments_list):
    """Split departments into predefined groups.

    Departments are yielded in specific order based on predefined ID groups.
    Any departments not covered by these groups are returned in a final chunk.
    """
    # Create a mapping of department ID to department data
    dept_map = {dept['id']: dept for dept in departments_list}

    # Define the specific chunking order
    chunk_order = [
        ['16.1', '15', '20', '19', '21', '12', '13', '14', '31'],
        ['10.2', '10.3', '10.8', '10.5', '10.6', '10.7', '11.1', '11.2', '32'],
        ['10.1', '10.9', '9', '26', '27', '22', '6', '28']
    ]

    # Yield chunks in the specified order
    for chunk_ids in chunk_order:
        chunk = []
        for dept_id in chunk_ids:
            if dept_id in dept_map:
                chunk.append(dept_map[dept_id])
        if chunk:  # Only yield non-empty chunks
            yield chunk

    # Handle any remaining departments not in the specified order
    used_ids = set()
    for chunk_ids in chunk_order:
        used_ids.update(chunk_ids)

    remaining_depts = [dept for dept in departments_list if dept['id'] not in used_ids]
    if remaining_depts:
        yield remaining_depts

# Initialize mappers
REGION_NAME_TO_ID, DISTRICT_NAME_TO_ID = load_yaml_data()

# District ID → parent Region ID mapping (derived from data/districts.yaml grouping)
DISTRICT_TO_REGION: dict[int, int] = {
    **{d: 1 for d in range(1, 17)},           # andijon
    **{d: 2 for d in range(17, 30)},           # buxoro
    **{d: 3 for d in range(30, 43)},           # jizzax
    **{d: 4 for d in range(43, 58)},           # qashqadaryo
    205: 4, 217: 4,
    **{d: 5 for d in range(58, 68)},           # navoiy
    **{d: 6 for d in range(68, 80)},           # namangan
    204: 6, 207: 6,
    **{d: 7 for d in range(80, 96)},           # samarqand
    **{d: 8 for d in range(96, 110)},          # surxondaryo
    202: 8,
    **{d: 9 for d in range(110, 122)},         # sirdaryo
    **{d: 10 for d in range(122, 133)},        # toshkent shahri
    203: 10,
    **{d: 11 for d in range(133, 155)},        # toshkent viloyat
    **{d: 12 for d in range(155, 174)},        # farg'ona
    **{d: 13 for d in range(174, 186)},        # xorazm
    206: 13,
    **{d: 14 for d in range(186, 202)},        # qoraqalpog'iston
}

_missing = set(DISTRICT_NAME_TO_ID.values()) - set(DISTRICT_TO_REGION.keys())
if _missing:
    logger.warning("Districts missing from DISTRICT_TO_REGION: %s", _missing)


def _find_district_in_region(text: str, region_id: int, region_name: str = "") -> Optional[int]:
    """Search text for any district name belonging to the given region.

    Used during cross-validation: when the LLM-extracted district doesn't match
    the resolved region, scan the address for a district within that region.
    Strips region_name from text first to avoid false matches (e.g. "toshkent"
    district matching the "Toshkent viloyati" region prefix in the address).
    Returns the first (longest-name) match, or None.
    """
    if not text:
        return None

    normalized = text.lower().strip()
    if is_cyrillic(normalized):
        normalized = translite(normalized)
    normalized = NON_WORD_SPACE_RE.sub('', normalized)
    normalized = MULTI_SPACE_RE.sub(' ', normalized).strip()

    # Strip region name so district names that overlap with it don't false-match
    if region_name:
        region_clean = region_name.lower().strip()
        if is_cyrillic(region_clean):
            region_clean = translite(region_clean)
        region_clean = NON_WORD_SPACE_RE.sub('', region_clean)
        region_clean = MULTI_SPACE_RE.sub(' ', region_clean).strip()
        if region_clean:
            normalized = normalized.replace(region_clean, '').strip()

    if not normalized:
        return None

    # Collect districts in the target region, longest name first
    candidates = []
    for name, did in DISTRICT_NAME_TO_ID.items():
        if DISTRICT_TO_REGION.get(did) != region_id:
            continue
        cleaned = name
        if is_cyrillic(cleaned):
            cleaned = translite(cleaned)
        cleaned = NON_WORD_SPACE_RE.sub('', cleaned)
        cleaned = MULTI_SPACE_RE.sub(' ', cleaned).strip()
        if cleaned:
            candidates.append((cleaned, did))

    candidates.sort(key=lambda x: len(x[0]), reverse=True)

    # Street indicators — if match is followed by one of these, it's a street name, not a district
    street_indicators = ("kochasi", "kuchasi", "ko'chasi", "кўчаси", "кучаси", "mavze", "мавзе", "dahasi", "даҳа")

    def _match_candidates(text_norm, cands, fuzzy=False):
        """Try to find a district match in text. If fuzzy, apply _fuzzy_normalize to both sides."""
        t = _fuzzy_normalize(text_norm) if fuzzy else text_norm
        for cname, did in cands:
            c = _fuzzy_normalize(cname) if fuzzy else cname
            idx = t.find(c)
            if idx == -1:
                continue
            after = t[idx + len(c):].lstrip()
            si = [_fuzzy_normalize(s) for s in street_indicators] if fuzzy else street_indicators
            if any(after.startswith(s) for s in si):
                continue
            return did
        return None

    # First pass: exact match
    result = _match_candidates(normalized, candidates)
    if result is not None:
        return result

    # Second pass: fuzzy match (handles Russian Cyrillic к→k vs қ→q drift)
    return _match_candidates(normalized, candidates, fuzzy=True)


def find_region_id(region_name: str) -> Optional[int]:
    """Find region ID by name (case-insensitive) with Cyrillic transliteration support and suffix stripping."""
    if not region_name:
        return None

    # Normalize the input
    normalized_name = region_name.lower().strip()

    # Create both original and transliterated versions for search
    search_names = [normalized_name]
    if is_cyrillic(normalized_name):
        search_names.append(translite(normalized_name))
    elif is_latin(normalized_name):
        search_names.append(reverse_translite(normalized_name))

    # Normalize "shahar" → "shahri" (Uzbek genitive form used in YAML)
    search_names = [n.replace('shahar', 'shahri') for n in search_names]
    # Normalize Uzbek Latin variants (bukhoro → buxoro, khorazm → xorazm, etc.)
    search_names = search_names + [_normalize_uzbek_latin(n) for n in search_names]
    # Deduplicate while preserving order
    search_names = list(dict.fromkeys(search_names))

    # Direct match with both versions
    for search_name in search_names:
        if search_name in REGION_NAME_TO_ID:
            return REGION_NAME_TO_ID[search_name]

    # Define common region suffixes
    region_suffixes = [
      'viloyati', 'region', 'oblast',
      'viloyat', 'viloyatlar', 'oblasts', 'oblast',
    ]
    # Fuzzy matching with both versions and suffix stripping
    for search_name in search_names:
        cleaned_name = NON_WORD_SPACE_RE.sub('', search_name)
        cleaned_name = MULTI_SPACE_RE.sub(' ', cleaned_name).strip()

        # Remove common region suffixes
        for suffix in region_suffixes:
            if cleaned_name.endswith(suffix):
                cleaned_name = cleaned_name[:-len(suffix)].strip()
                break

        if cleaned_name in REGION_NAME_TO_ID:
            return REGION_NAME_TO_ID[cleaned_name]

        # Try English alias lookup (e.g. "surkhandarya" → "surxondaryo")
        alias = _ENGLISH_REGION_ALIASES.get(cleaned_name)
        if alias and alias in REGION_NAME_TO_ID:
            return REGION_NAME_TO_ID[alias]

    return None

def find_district_id(district_name: str) -> Optional[int]:
    """Find district ID by name (case-insensitive) with Cyrillic transliteration support."""
    if not district_name:
        return None

    # Normalize the input
    normalized_name = MULTI_SPACE_RE.sub(' ', district_name.lower().strip())

    # Create both original and transliterated versions for search
    search_names = [normalized_name]
    if is_cyrillic(normalized_name):
        search_names.append(translite(normalized_name))
    elif is_latin(normalized_name):
        search_names.append(reverse_translite(normalized_name))
    # Normalize Uzbek Latin variants (bukhoro → buxoro, etc.)
    search_names = search_names + [_normalize_uzbek_latin(n) for n in search_names]
    search_names = list(dict.fromkeys(search_names))

    # Direct match with both versions
    for search_name in search_names:
        if search_name in DISTRICT_NAME_TO_ID:
            return DISTRICT_NAME_TO_ID[search_name]

    # Fuzzy matching with both versions
    district_suffixes = [
        'tumani', 'rayon', 'tuman', 'rayoni'
    ]

    for search_name in search_names:
        cleaned_name = NON_WORD_SPACE_RE.sub('', search_name)
        cleaned_name = MULTI_SPACE_RE.sub(' ', cleaned_name).strip()

        # Remove common district/city suffixes
        for suffix in district_suffixes:
            if cleaned_name.endswith(suffix):
                cleaned_name = cleaned_name[:-len(suffix)].strip()
                break

        for name, district_id in DISTRICT_NAME_TO_ID.items():
            cleaned_stored = NON_WORD_SPACE_RE.sub('', name)
            cleaned_stored = MULTI_SPACE_RE.sub(' ', cleaned_stored).strip()

            # Also remove suffixes from stored names
            for suffix in district_suffixes:
                if cleaned_stored.endswith(suffix):
                    cleaned_stored = cleaned_stored[:-len(suffix)].strip()
                    break

            if cleaned_name == cleaned_stored or cleaned_name in cleaned_stored or cleaned_stored in cleaned_name:
                return district_id

    # Fuzzy fallback: normalize k/q ambiguity for Russian Cyrillic drift
    for search_name in search_names:
        cleaned_name = NON_WORD_SPACE_RE.sub('', search_name)
        cleaned_name = MULTI_SPACE_RE.sub(' ', cleaned_name).strip()
        for suffix in district_suffixes:
            if cleaned_name.endswith(suffix):
                cleaned_name = cleaned_name[:-len(suffix)].strip()
                break
        fuzzy_input = _fuzzy_normalize(cleaned_name)
        for name, district_id in DISTRICT_NAME_TO_ID.items():
            cleaned_stored = NON_WORD_SPACE_RE.sub('', name)
            cleaned_stored = MULTI_SPACE_RE.sub(' ', cleaned_stored).strip()
            for suffix in district_suffixes:
                if cleaned_stored.endswith(suffix):
                    cleaned_stored = cleaned_stored[:-len(suffix)].strip()
                    break
            fuzzy_stored = _fuzzy_normalize(cleaned_stored)
            if fuzzy_input == fuzzy_stored or fuzzy_input in fuzzy_stored or fuzzy_stored in fuzzy_input:
                return district_id

    return None

# @mlflow.trace
async def extract_author_information(text):


  completion = await openai.chat.completions.create(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          You are NER expert. Extract the complainant's (arizachi/fuqaro/murojaatchi) information from a given legal document.
          IMPORTANT: The author is the citizen who filed the complaint, NOT the government institution or official forwarding it. Use the complainant's residential address, not the institution's address.
          Extract these fields:
          - last_name: complainant's last name (full, not initials)
          - first_name: complainant's first name (full, not initials)
          - middle_name: complainant's middle name / patronymic (full, not initials)
          - date_of_birth: in DD.MM.YYYY format
          - gender: "male" or "female" (REQUIRED — infer from name/patronymic if not explicit in document)
          - phones: list of phone numbers
          - date_when_document_was_written: in DD.MM.YYYY format
          - email
          - country
          - city: complainant's city of residence (e.g. Toshkent, Samarqand)
          - region: complainant's region/viloyat (e.g. Toshkent viloyati, Farg'ona viloyati, Toshkent shahri). Extract from address.
          - district: complainant's district/tuman (e.g. Uchtepa, Chilonzor). Extract from address.
          - address: remaining residential address AFTER extracting region and district (house, street only)

          # Legal Document:
          {text}
        """,
      },
    ],
    response_format=AuthorInfo,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  if not parsed:
    return {}

  json_object = parsed.model_dump()

  logger.info("author_info raw LLM fields: region=%s, district=%s, city=%s, address=%s",
    json_object.get("region"),
    json_object.get("district"),
    json_object.get("city"),
    json_object.get("address"))

  # Validate and clean extracted data
  # Normalize gender: fallback to patronymic-based inference if LLM left it empty
  gender = (json_object.get("gender") or "").strip().lower()
  if gender in ("male", "female"):
      json_object["gender"] = gender
  else:
      middle = (json_object.get("middle_name") or "").strip()
      if middle:
          ml = middle.lower()
          if ml.endswith(("ович", "евич", "угли", "ўғли", "o'g'li", "ич")):
              json_object["gender"] = "male"
          elif ml.endswith(("овна", "евна", "qizi", "қизи", "кизи", "на")):
              json_object["gender"] = "female"
          else:
              json_object["gender"] = ""
      else:
          json_object["gender"] = ""

  email = json_object.get("email", "")
  json_object["email"] = email if is_valid_email(email) else ""

  raw_phones = json_object.get("phones") or []
  json_object["phones"] = clean_phone(raw_phones)

  date_of_birth = json_object.get("date_of_birth", "")
  json_object["date_of_birth"] = normalize_date(date_of_birth)

  date_of_issue = json_object.get("date_of_issue", "")
  json_object["date_of_issue"] = normalize_date(date_of_issue)

  # Normalize "not mentioned" / null-like strings to None
  _NULL_VALUES = {"not mentioned", "none", "null", "n/a", "not specified", "unknown", ""}
  for field in ("region", "district"):
    val = json_object.get(field)
    if isinstance(val, str) and val.lower().strip() in _NULL_VALUES:
      json_object[field] = None

  # Map region and district names to IDs using new mapper functions
  region_name = json_object.get("region", "")
  if region_name:
    region_id = find_region_id(region_name)
    json_object["region_id"] = region_id

  district_name = json_object.get("district", "")
  if district_name:
    district_id = find_district_id(district_name)
    json_object["district_id"] = district_id

  # Fallback: if region still missing, try city field as region (prefer "X шаҳри" city-level)
  if not json_object.get("region_id"):
    city = (json_object.get("city", "") or "").strip()
    if city:
      # Try city-level first (e.g. "Тошкент шаҳри" = region 10), then bare name
      rid = find_region_id(f"{city} шаҳри") or find_region_id(f"{city} shahri") or find_region_id(city)
      if rid:
        json_object["region_id"] = rid
      else:
        # City may be a district-level city (e.g. Qo'qon) — resolve district, derive region
        did = find_district_id(city)
        if did:
          json_object["district_id"] = did
          parent_rid = DISTRICT_TO_REGION.get(did)
          if parent_rid:
            json_object["region_id"] = parent_rid

  # Fallback: if district still missing, scan address parts
  if not json_object.get("district_id"):
    address = json_object.get("address", "") or ""
    for part in (p.strip() for p in address.split(",")):
      if not part:
        continue
      candidates = [part]
      words = part.split()
      if len(words) > 2:
        for size in [3, 2]:
          for i in range(len(words) - size + 1):
            candidates.append(' '.join(words[i:i+size]))
      for candidate in candidates:
        did = find_district_id(candidate)
        if did:
          json_object["district_id"] = did
          json_object["district"] = candidate
          break
      if json_object.get("district_id"):
        break

  # Last-resort fallback: if district still missing but region found, scan the original text
  if json_object.get("region_id") and not json_object.get("district_id"):
    corrected_did = _find_district_in_region(text, json_object["region_id"], json_object.get("region", ""))
    if corrected_did is not None:
      json_object["district_id"] = corrected_did

  # Cross-validate region_id ↔ district_id consistency
  resolved_district_id = json_object.get("district_id")
  resolved_region_id = json_object.get("region_id")
  if resolved_district_id is not None:
      expected_region_id = DISTRICT_TO_REGION.get(resolved_district_id)
      if expected_region_id is not None:
          if resolved_region_id is None:
              # No region resolved; derive from district
              json_object["region_id"] = expected_region_id
          elif resolved_region_id != expected_region_id:
              # Mismatch: try to find correct district from address within the resolved region
              address = json_object.get("address", "") or ""
              corrected_did = _find_district_in_region(address, resolved_region_id, json_object.get("region", ""))
              if corrected_did is not None:
                  json_object["district_id"] = corrected_did
              else:
                  # No address match; trust district, correct region
                  json_object["region_id"] = expected_region_id

  country = (json_object.get("country", "") or "").replace("Республикаси", "").replace("Respublikasi", "").strip() or None
  json_object["country"] = country


  return json_object

# @mlflow.trace
async def select_document_type(text):


  completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          Classify the given Document by selecting the most appropriate document type. Reason through the Document first.
          # Document:
          {text}
          """,
      },
    ],
    response_format=DocumentTypeResponse,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  if not parsed:
    return ""
  return parsed.type


# @mlflow.trace
async def extract_case_info(text):


  completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          Below is an updated version of the instructions that incorporates **claimant** details. In this version, we account for the possibility that the **victim** and **claimant** could be the same individual, or they could be different people.

          1. **Identify the Case Number**
             - Locate and extract the case number from the case description.
             - The case number typically follows a standardized format that may include letters, numbers, or symbols.

          2. **Extract Suspect (Defendant) Details**
             - Search the case description for the name of the suspect or defendant.
             - Capture the first name, middle name or initial (if present), and last name.
             - If the middle name is not provided, use an empty string.

          3. **Extract Victim Details**
             - Locate the name of the victim in the case description.
             - Capture the victim's first name, middle name or initial (if present), and last name.
             - If the middle name is not provided, use an empty string.
             - If no victim name is given, use empty strings for these fields.

          4. **Extract Claimant Details**
             - Identify the name of the claimant, if provided.
             - Capture the claimant's first name, middle name or initial (if present), and last name.
             - If no claimant name is provided, use empty strings for these fields.
             - **Important**: If the case description indicates that the victim and the claimant are the same person, repeat the same name details for both the victim and claimant. Otherwise, treat them as separate individuals.

           ### Notes
           - If no victim name or no claimant name is found, fill the respective fields with empty strings.
           - Consider variations in formatting for the case number and names (capitalization, hyphens, initials, etc.).
           - If multiple suspects, victims, or claimants appear, return the main (primary) individuals relevant to the case.

          # Case Description:
          {text}
        """,
      },
    ],
    response_format=CaseInfoResponse,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  return parsed.model_dump() if parsed else {}

# @mlflow.trace
async def extract_articles(text):


  completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          Identify and extract legal details from a given criminal case description. If multiple law articles, parts, or clauses are mentioned, extract each one separately.

          # Steps

          1. **Comprehension**: Read through the criminal case description to understand the context and identify legal references.
          2. **Identification**: Locate any text that refers to specific laws, articles, parts, or clauses.
          3. **Extraction**: Extract and differentiate between articles, parts, and clauses mentioned. Multiple mentions should be processed individually.

          # Examples

          - "168-моддаси 4-кисми 'а' банди" → article=168, part=4, clause="a"
          - "121-моддаси 3-кисми 'б' банди ва 124-моддаси 1-кисми" → two articles: (121, 3, "b") and (124, 1, null)

          # Notes
          - Ensure each legal reference is accurately extracted, including articles, parts, and clauses.
          - If a clause is not present, set it to null.
          - Consider regional legal terminology variations when interpreting the case descriptions.

          # Criminal Case Description:
          {text}
        """,
      },
    ],
    response_format=ArticlesResponse,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  return parsed.model_dump() if parsed else {}

# @mlflow.trace
async def extract_issues(text):


  completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          Extract the main issues and important keywords from the given legal document.

          # Legal Document:
          {text}
          """,
      },
    ],
    response_format=IssuesResponse,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  return parsed.model_dump() if parsed else {"issues": [], "keywords": []}


 #  A) Justice & Security Oversight
 #  Law-enforcement, criminal justice, and courts (all proceedings)
	# •	16.1, 15, 20, 19, 21, 12, 13, 14, 31

 #  B) Economy, Infrastructure & Natural Resources
 #  Markets, anti-shadow, energy, construction, environment, agri/fisheries, land
	# •	10.2, 10.3, 10.8, 10.5, 10.6, 10.7, 11.1, 11.2, 32

 #  C) Social Policy, International & Corporate Services
 #  Social sectors, poverty/minors, international/migration, strategy/comms, HR/admin
	# •	10.1, 10.9, 9, 26, 27, 22, 6, 28

async def _select_department(departments_yaml, summary):


    completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
        {
        "role": "system",
        "content": f"""
            Given legal complaint select most appropriate prosecutor's department that is responsible for handling the complaint according to their duties.

            For each complaint, perform these reasoning steps before providing your conclusion:
            1. *Analyze the Issue*: Break down the complaint's description. Extract the main facts and issues of the complaint. Identify main plaintiff and defendant.
            2. *Match with Department*: Evaluate the duties of each department provided. Compare these duties to the complaint's main issues, and identify which department aligns most closely with the complaint.
            3. *Conclusion*: Based on your reasoning above, state the department primarily responsible for handling the complaint.

            Guidelines:
            - If you cannot find a suitable department return null for the department id.
            - In cases where responsibility overlaps, select the department whose main duties most closely fit the complaint.
            - Provide a confidence score (0-10) indicating how well the selected department matches the complaint.

            Departments:
            {departments_yaml}

            Complaint:
            {summary}
        """,
        },
    ],
    response_format=DepartmentSelection,
    reasoning_effort=REASONING_EFFORT,
    )

    parsed = completion.choices[0].message.parsed
    logger.info("_select_department response: %s", parsed)
    return parsed.model_dump() if parsed else None



# @mlflow.trace
async def select_department(summary=None):
  best_result = None
  best_confidence = 0

  departments_data = load_departments_data("data/departments.yaml")
  departments = []
  confidences = []

  for index, department_chunk in enumerate(chunk_departments(departments_data)):
    departments_yaml = yaml.dump(department_chunk, default_flow_style=False, allow_unicode=True)

    json_object = await _select_department(departments_yaml, summary)

    if json_object:
        confidence = int(json_object.get("confidence", 0))
        if confidence > 7:
            department_id = json_object.get("department_id")
            if department_id:
                for dept in department_chunk:
                    if str(dept.get("id")) == str(department_id):
                        departments.append(dept)
                        confidences.append(confidence)

        if confidence >= best_confidence:
          best_confidence = confidence
          best_result = json_object

    if index == 1 and best_confidence > 8 and len(confidences) == 2 and confidences[0] != confidences[1]:
        departments = None
        confidences = None
        break

  if departments and len(departments) > 1 and len(set(confidences)) <= 2:
    departments_yaml = yaml.dump(departments, default_flow_style=False, allow_unicode=True)
    best_result = await _select_department(departments_yaml, summary)

  if best_result:
    best_result["id"] = best_result.get("department_id")
    return best_result

  return {}


# @mlflow.trace

# @mlflow.trace
async def summarize(text, language="Uzbek"):
  # Count sentences by splitting on sentence-ending punctuation
  sentences = re.split(r'[.!?]+', text.strip())
  # Filter out empty strings and count actual sentences
  sentence_count = len([s for s in sentences if s.strip()])

  # If text has 3 or fewer sentences, return the original text
  if sentence_count <= 3:
    return text

  completion = await openai.chat.completions.parse(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": f"""
          Analyze the given legal document and summarize it from a third-person perspective in {language} by highlighting issues and problems.
          Summary should be short, 3 sentences max. Do not mention its summary.

          # Legal document:
          {text}
          """,
      },
    ],
    response_format=SummaryResponse,
    reasoning_effort=REASONING_EFFORT,
  )

  parsed = completion.choices[0].message.parsed
  return parsed.summary if parsed else ""

# @mlflow.trace
async def get_entity_type(text):


  completion = await openai.chat.completions.create(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": _prepare_prompt(f"""
          Classify the document as being written by either an "individual" or a "business"
          Consider the language, content, and structure of the document to determine the entity type. Features and indicators to consider may include formality, presence of business terminology, organizational logos, personal pronouns, or informal language.

          # Steps
          1. **Analyze Document Language**: Examine the tone, style, and vocabulary. Business documents are often formal and may contain industry-specific terms, whereas personal writing may be informal and use personal pronouns.
          2. **Check Document Structure**: Look for structural elements such as headers, footers, logos, and contact information indicating business origins.
          3. **Identify Content Type**: Determine if the content is relevant to business operations, strategies, or products, which would usually indicate a business document.
          4. **Consider Context**: Review any contextual clues within or surrounding the document, such as mention of business names, departments, or teams.

          # Document
          {text}
        """)
      },
    ],
    **_get_params(top_p=0.7)
  )

  response_content = completion.choices[0].message.content

  if not response_content:
    return {}

  try:
    json_object = json.loads(response_content)
  except json.JSONDecodeError as e:
    logger.error("Failed to parse JSON in get_entity_type: %s", e)
    return {}

  return json_object

# @mlflow.trace
async def check_for_repeated_request(text):


  completion = await openai.chat.completions.create(
    model=MODEL,
    messages=[
      {
        "role": "user",
        "content": _prepare_prompt(f"""
          Analyze the given legal complaint and determine if the user has written a complaint before, excluding the current given legal complaint. Provide no additional information.

          # Legal Complaint
          {text}
          """),
      },
    ],
    **_get_params()
  )

  response_content = completion.choices[0].message.content

  if not response_content:
    return {}

  try:
    json_object = json.loads(response_content)
  except json.JSONDecodeError as e:
    logger.error("Failed to parse JSON in check_for_repeated_request: %s", e)
    return {}

  return json_object
