"""
Pydantic schemas for AI extraction results.

These mirror the schemas in library/schemas.py but are organized
under the schemas/ package for the layered architecture.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Gender(str, Enum):
    male = "male"
    female = "female"


class EntityType(str, Enum):
    individual = "individual"
    business = "business"


class LegalType(str, Enum):
    qonun = "qonun"
    qaror = "qaror"
    farmon = "farmon"
    farmoyish = "farmoyish"
    buyruqlar = "buyruqlar"
    amaliy_qollanmalar = "amaliy qo'llanmalar"
    qoshma_farmoyish = "qo'shma farmoyish"


class AuthorInformation(BaseModel):
    last_name: Optional[str] = Field(None, description="Last name of the author")
    first_name: Optional[str] = Field(None, description="First name of the author")
    middle_name: Optional[str] = Field(None, description="Middle name of the author")
    date_of_birth: Optional[str] = Field(None, description="Date of birth in DD.MM.YYYY format")
    gender: Optional[Gender] = Field(None, description="Gender: male or female")
    phones: Optional[List[str]] = Field(None, description="Phone numbers")
    date_of_issue: Optional[str] = Field(None, description="Date when document was written in DD.MM.YYYY format")
    email: Optional[str] = Field(None, description="Email address")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field("Uzbekistan")
    region: Optional[str] = Field(None, description="Region in latin letters")
    district: Optional[str] = Field(None, description="District in latin letters")
    address: Optional[str] = Field(None, description="Address without district and region")


class DepartmentSelection(BaseModel):
    department_id: str = Field(..., description="ID of the selected department")
    reasoning: str = Field(..., description="Reasoning for the department selection")
    confidence: int = Field(..., description="Confidence score (0-10) for the department selection")


class EntityInformation(BaseModel):
    type: EntityType = Field(..., description="Type of entity: individual or business")
    name: str = Field(..., description="Name of the individual or business")


class RepeatedRequestCheck(BaseModel):
    is_repeated: bool = Field(..., description="Whether this is a repeated complaint")
    dates: Optional[List[str]] = Field(None, description="List of dates when previous complaints were submitted in DD.MM.YYYY format")


class CategorySelection(BaseModel):
    category_id: str = Field(..., description="ID of the selected category")
    reasoning: str = Field(..., description="Reasoning for the category selection")


class DocumentType(BaseModel):
    type: Optional[LegalType] = Field(None, description="Legal document type classification")
    confidence: float = Field(..., description="Confidence score for the classification")


class IssueExtraction(BaseModel):
    issues: List[str] = Field(default_factory=list, description="List of main issues in the document")
    keywords: List[str] = Field(default_factory=list, description="List of important keywords")


class Article(BaseModel):
    article: int = Field(..., description="Article number")
    part: Optional[int] = Field(None, description="Part number")
    clause: Optional[str] = Field(None, description="Clause letter or number")


class ArticleExtraction(BaseModel):
    articles: List[Article] = Field(default_factory=list, description="List of extracted legal articles")


class Person(BaseModel):
    first_name: Optional[str] = Field(None, description="First name")
    middle_name: Optional[str] = Field(None, description="Middle name")
    last_name: Optional[str] = Field(None, description="Last name")


class CaseInformation(BaseModel):
    case_number: Optional[str] = Field(None, description="Case number")
    suspect: Optional[Person] = Field(None, description="Suspect/defendant information")
    victim: Optional[Person] = Field(None, description="Victim information")
    claimant: Optional[Person] = Field(None, description="Claimant information")


class OriginSelection(BaseModel):
    origin_id: int = Field(..., description="ID of the selected origin")
    reasoning: str = Field(..., description="Reasoning for the origin selection")
