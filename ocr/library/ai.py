import logging
import re
from pathlib import Path
from typing import Optional

import yaml
from core.config import get_settings
from openai import AsyncOpenAI
from pydantic import BaseModel
from utils.text import (
    clean_phone,
    is_valid_email,
    normalize_date,
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
REASONING = {"effort": "medium"}
OFFICIALS_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "toshkent-tumani-officials.yaml"
)


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


class IssuesResponse(BaseModel):
    issues: list[str] = []
    keywords: list[str] = []


class DepartmentSelection(BaseModel):
    order: Optional[int] = None
    reasoning: str = ""


class RepeatedRequestResponse(BaseModel):
    is_repeated: bool = False
    dates: list[str] = []


def load_yaml_data(file_path: str | Path):
    """Load YAML data from disk."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def build_officials_prompt_data(officials_data):
    """Trim the officials list to fields relevant for routing."""
    return [
        {
            "order": official.get("order"),
            "position": official.get("position"),
            "responsibilities": official.get("responsibilities") or [],
        }
        for official in officials_data
        if isinstance(official, dict)
    ]


# @mlflow.trace
async def extract_author_information(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          You are NER expert. Extract the author's (arizachi/fuqaro/murojaatchi) information from a citizen complaint or government letter.
          IMPORTANT: The author is the citizen who filed the complaint, NOT the government institution or official forwarding it. Use the complainant's residential address, not the institution's address.
          Extract these fields:
          - last_name: author's last name (full, not initials)
          - first_name: author's first name (full, not initials)
          - middle_name: author's middle name / patronymic (full, not initials)
          - date_of_birth: in DD.MM.YYYY format
          - gender: "male" or "female" (REQUIRED — infer from name/patronymic if not explicit)
          - phones: list of phone numbers
          - date_when_document_was_written: in DD.MM.YYYY format
          - email
          - country
          - city: author's city of residence (e.g. Toshkent, Samarqand)
          - region: author's region/viloyat (e.g. Toshkent viloyati, Farg'ona viloyati, Toshkent shahri). Extract from address.
          - district: author's district/tuman (e.g. Uchtepa, Chilonzor). Extract from address.
          - address: remaining residential address AFTER extracting region and district (house, street only)

          # Document:
          {text}
        """,
        text_format=AuthorInfo,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    if not parsed:
        return {}

    json_object = parsed.model_dump()

    logger.info(
        "author_info raw LLM fields: region=%s, district=%s, city=%s, address=%s",
        json_object.get("region"),
        json_object.get("district"),
        json_object.get("city"),
        json_object.get("address"),
    )

    email = json_object.get("email", "")
    json_object["email"] = email if is_valid_email(email) else ""

    raw_phones = json_object.get("phones") or []
    json_object["phones"] = clean_phone(raw_phones)

    date_of_birth = json_object.get("date_of_birth", "")
    json_object["date_of_birth"] = normalize_date(date_of_birth)

    date_of_issue = json_object.get("date_of_issue", "")
    json_object["date_of_issue"] = normalize_date(date_of_issue)

    country = (json_object.get("country", "") or "").replace(
        "Республикаси", ""
    ).replace("Respublikasi", "").strip() or None
    json_object["country"] = country

    return json_object


# @mlflow.trace
async def select_document_type(text):
    response = await openai.responses.create(
        model=MODEL,
        input=f"""
          Classify the given document (citizen complaint or government letter) by selecting the most appropriate document type.
          Return only the document type as plain text.
          # Document:
          {text}
          """,
        reasoning=REASONING,
    )

    return (response.output_text or "").strip()


# @mlflow.trace

# @mlflow.trace


# @mlflow.trace
async def extract_issues(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Extract the main issues and important keywords from the given complaint or government letter.

          # Document:
          {text}
          """,
        text_format=IssuesResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.model_dump() if parsed else {"issues": [], "keywords": []}


async def _select_department(officials_yaml, summary):
    response = await openai.responses.parse(
        model=MODEL,
        instructions=f"""
            Given a citizen complaint or government letter, select the district administration official who should handle the issue or who is the most likely intended recipient of the letter.

            Your goal is to find the single best-matching official based on the letter's content.

            Selection rules:
            - Focus on the core issue, requested action, and any explicitly targeted position in the letter.
            - Match the issue to the official whose responsibilities most directly cover the matter.
            - If the letter is clearly addressed to a position in the list, prefer that official when it is a reasonable match.
            - If several officials could be involved, choose the one who should primarily resolve the issue or reply to the letter.
            - Use only the provided officials list.
            - Return only:
              - order: the selected official's order number, or null if no reasonable match exists
              - reasoning: a short explanation of why this position is the best fit

            Officials:
            {officials_yaml}

            Letter:
            {summary or ""}
        """,
        text_format=DepartmentSelection,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    logger.info("_select_department response: %s", parsed)
    return parsed.model_dump() if parsed else None


# @mlflow.trace
async def select_department(summary=None):
    officials_data = load_yaml_data(OFFICIALS_DATA_PATH)
    officials_yaml = yaml.dump(
        build_officials_prompt_data(officials_data),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    result = await _select_department(officials_yaml, summary)

    if result:
        order = result.get("order")
        result["id"] = str(order) if order is not None else None
        return result

    return {}


# @mlflow.trace


# @mlflow.trace
async def summarize(text, language="Uzbek"):
    # Count sentences by splitting on sentence-ending punctuation
    sentences = re.split(r"[.!?]+", text.strip())
    # Filter out empty strings and count actual sentences
    sentence_count = len([s for s in sentences if s.strip()])

    # If text has 3 or fewer sentences, return the original text
    if sentence_count <= 3:
        return text

    response = await openai.responses.create(
        model=MODEL,
        input=f"""
          Analyze the given complaint or government letter and summarize it from a third-person perspective in {language} by highlighting issues and problems.
          Return only the summary as plain text.
          Summary should be short, 3 sentences max. Do not mention that it is a summary.

          # Document:
          {text}
          """,
        reasoning=REASONING,
    )

    return (response.output_text or "").strip()


# @mlflow.trace
async def get_entity_type(text):
    response = await openai.responses.create(
        model=MODEL,
        input=f"""
          Classify the given complaint or government letter as being written by either an "individual" or a "business".
          Return only one value as plain text: "individual" or "business".
          Consider the language, content, and structure to determine the entity type.

          # Steps
          1. **Analyze Language**: Examine the tone, style, and vocabulary. Business letters are often formal and may contain industry-specific terms, whereas personal complaints may be informal and use personal pronouns.
          2. **Check Structure**: Look for structural elements such as headers, footers, logos, and contact information indicating business origins.
          3. **Identify Content Type**: Determine if the content relates to business operations or personal/citizen matters.
          4. **Consider Context**: Review contextual clues such as mention of business names, departments, or teams.

          # Document
          {text}
        """,
        reasoning=REASONING,
    )

    entity_type = (response.output_text or "").strip()
    return {"entity_type": entity_type} if entity_type else {}


# @mlflow.trace
async def check_for_repeated_request(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Analyze the given complaint or government letter and determine if the author has submitted a similar complaint before. Provide no additional information.

          # Document
          {text}
          """,
        text_format=RepeatedRequestResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.model_dump() if parsed else {}
