import logging
import re
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


def load_departments_data(file_path: str):
    """Load departments from YAML file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Classify the given document (citizen complaint or government letter) by selecting the most appropriate document type.
          # Document:
          {text}
          """,
        text_format=DocumentTypeResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    if not parsed:
        return ""
    return parsed.type


# @mlflow.trace
async def extract_case_info(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Extract case information from the given complaint or government letter. Account for the possibility that the **victim** and **claimant** could be the same individual, or they could be different people.

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
        text_format=CaseInfoResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.model_dump() if parsed else {}


# @mlflow.trace
async def extract_articles(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Identify and extract legal article references from the given complaint or government letter. If multiple law articles, parts, or clauses are mentioned, extract each one separately.

          # Steps

          1. **Comprehension**: Read through the document to understand the context and identify legal references.
          2. **Identification**: Locate any text that refers to specific laws, articles, parts, or clauses.
          3. **Extraction**: Extract and differentiate between articles, parts, and clauses mentioned. Multiple mentions should be processed individually.

          # Examples

          - "168-моддаси 4-кисми 'а' банди" → article=168, part=4, clause="a"
          - "121-моддаси 3-кисми 'б' банди ва 124-моддаси 1-кисми" → two articles: (121, 3, "b") and (124, 1, null)

          # Notes
          - Ensure each legal reference is accurately extracted, including articles, parts, and clauses.
          - If a clause is not present, set it to null.
          - Consider regional legal terminology variations when interpreting the case descriptions.

          # Document:
          {text}
        """,
        text_format=ArticlesResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.model_dump() if parsed else {}


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


async def _select_department(departments_yaml, summary):
    response = await openai.responses.parse(
        model=MODEL,
        instructions=f"""
            Given a citizen complaint or government letter, select the most appropriate prosecutor's department that is responsible for handling it according to their duties.

            Perform these reasoning steps before providing your conclusion:
            1. *Analyze the Issue*: Break down the document's content. Extract the main facts and issues. Identify main plaintiff and defendant if applicable.
            2. *Match with Department*: Evaluate the duties of each department provided. Compare these duties to the document's main issues, and identify which department aligns most closely.
            3. *Conclusion*: Based on your reasoning above, state the department primarily responsible for handling this matter.

            Guidelines:
            - If you cannot find a suitable department return null for the department id.
            - In cases where responsibility overlaps, select the department whose main duties most closely fit the document.
            - Provide a confidence score (0-10) indicating how well the selected department matches.

            Departments:
            {departments_yaml}

            Document:
            {summary}
        """,
        text_format=DepartmentSelection,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    logger.info("_select_department response: %s", parsed)
    return parsed.model_dump() if parsed else None


# @mlflow.trace
async def select_department(summary=None):
    departments_data = load_departments_data("data/departments.yaml")
    departments_yaml = yaml.dump(
        departments_data, default_flow_style=False, allow_unicode=True
    )

    result = await _select_department(departments_yaml, summary)

    if result:
        result["id"] = result.get("department_id")
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

    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Analyze the given complaint or government letter and summarize it from a third-person perspective in {language} by highlighting issues and problems.
          Summary should be short, 3 sentences max. Do not mention its summary.

          # Document:
          {text}
          """,
        text_format=SummaryResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.summary if parsed else ""


# @mlflow.trace
async def get_entity_type(text):
    response = await openai.responses.parse(
        model=MODEL,
        input=f"""
          Classify the given complaint or government letter as being written by either an "individual" or a "business".
          Consider the language, content, and structure to determine the entity type.

          # Steps
          1. **Analyze Language**: Examine the tone, style, and vocabulary. Business letters are often formal and may contain industry-specific terms, whereas personal complaints may be informal and use personal pronouns.
          2. **Check Structure**: Look for structural elements such as headers, footers, logos, and contact information indicating business origins.
          3. **Identify Content Type**: Determine if the content relates to business operations or personal/citizen matters.
          4. **Consider Context**: Review contextual clues such as mention of business names, departments, or teams.

          # Document
          {text}
        """,
        text_format=EntityTypeResponse,
        reasoning=REASONING,
    )

    parsed = response.output_parsed
    return parsed.model_dump() if parsed else {}


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
