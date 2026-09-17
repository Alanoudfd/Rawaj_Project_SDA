from pydantic import BaseModel, Field
from typing import List


class Gap(BaseModel):
    gap: str
    severity: str
    priority: int
    evidence: List[str] = Field(default_factory=list)
    recommendation_focus: str


class Report(BaseModel):
    restaurant: str
    qualification: str
    decision_rationale: str
    marketing_gaps: List[Gap] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    data_limitations: List[str] = Field(default_factory=list)