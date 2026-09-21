from pydantic import BaseModel, Field
from typing import List


class Gap(BaseModel):
    gap: str
    description: str = ""
    status: str = ""
    severity: str = ""
    priority: int = 0
    confidence: str = ""

    evidence: List[str] = Field(default_factory=list)
    evidence_source: List[str] = Field(default_factory=list)
    benchmark_evidence: List[str] = Field(default_factory=list)

    rationale: str = ""
    data_limitations: List[str] = Field(default_factory=list)

    # Important for the Strategy Agent later
    recommendation_focus: str = ""


class Report(BaseModel):
    restaurant: str
    qualification: str
    decision_rationale: str
    qualification_confidence: str = ""

    marketing_gaps: List[Gap] = Field(default_factory=list)

    strengths: List[str] = Field(default_factory=list)
    data_limitations: List[str] = Field(default_factory=list)
