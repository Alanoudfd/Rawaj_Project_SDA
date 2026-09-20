"""The real configurable LLM boundary for Rawaj Outreach & Follow-Up.

This module makes no model call at import time and has no deterministic writing
fallback.  If an API key, supported model, or network connection is missing,
the workflow receives an explicit failure instead of a fabricated decision or
email.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

try:  # Supports package imports and direct local notebook imports.
    from .config import RawajSettings
    from .prompt import (
        build_decision_prompt,
        build_email_generation_prompt,
        build_message_review_prompt,
    )
    from .schemas import (
        ActionType,
        EmailContentProposal,
        MessageReview,
        OutreachDecision,
        RelationshipStatus,
    )
except ImportError:  # pragma: no cover - used by a direct notebook import.
    from config import RawajSettings
    from prompt import (
        build_decision_prompt,
        build_email_generation_prompt,
        build_message_review_prompt,
    )
    from schemas import (
        ActionType,
        EmailContentProposal,
        MessageReview,
        OutreachDecision,
        RelationshipStatus,
    )


class LLMIntegrationError(RuntimeError):
    """Raised when a real LLM call cannot return validated structured output."""


StructuredModelFactory = Callable[[str], Any]
StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class _StrictStructuredOutput(BaseModel):
    """OpenAI Structured Outputs-compatible schema: all fields are required."""

    model_config = ConfigDict(extra="forbid")


class _DecisionOutput(_StrictStructuredOutput):
    action: ActionType
    next_status: RelationshipStatus
    decision_basis: list[str]
    language: Literal["ar", "en"]
    read_calendar: bool
    selected_calendar_event_ids: list[str]
    personalization_observation_ids: list[str]
    requires_human_approval: bool
    requires_escalation: bool
    next_contact_at: str | None


class _EmailOutput(_StrictStructuredOutput):
    subject: str = Field(min_length=1, max_length=500)
    plain_text_body: str = Field(min_length=1, max_length=12_000)
    language: Literal["ar", "en"]
    personalization_observation_ids: list[str]


class _ReviewOutput(_StrictStructuredOutput):
    passed: bool
    issues: list[str]
    approved_fact_references: list[str]
    privacy_safe: bool


class RawajLLMService:
    """Use the configured GPT models for decision, generation, and review.

    The default boundary uses LangChain's ``ChatOpenAI``.  ``model_factory`` is
    dependency injection for deterministic tests only; production must leave it
    unset so the service validates ``OPENAI_API_KEY`` and calls the real model.
    """

    def __init__(
        self,
        settings: RawajSettings,
        *,
        model_factory: StructuredModelFactory | None = None,
    ) -> None:
        self.settings = settings
        if (
            model_factory is not None
            and settings.environment not in {"test", "testing"}
        ):
            raise LLMIntegrationError(
                "An injected LLM model factory is allowed only when RAWAJ_ENV is test."
            )
        self._model_factory = model_factory

    @property
    def model_summary(self) -> dict[str, str]:
        """Expose chosen models without exposing API credentials."""

        return {
            "generation_model": self.settings.openai_generation_model,
            "decision_model": self.settings.openai_decision_model,
            "review_model": self.settings.openai_review_model,
        }

    def decide(self, context: dict[str, Any]) -> OutreachDecision:
        """Return the next structured action; this method does not execute it."""

        return self._invoke_structured(
            model_name=self.settings.openai_decision_model,
            output_schema=_DecisionOutput,
            result_schema=OutreachDecision,
            prompt=build_decision_prompt(context),
        )

    def generate_email(self, context: dict[str, Any]) -> EmailContentProposal:
        """Return customer text before trusted rendering adds HTML and buttons."""

        return self._invoke_structured(
            model_name=self.settings.openai_generation_model,
            output_schema=_EmailOutput,
            result_schema=EmailContentProposal,
            prompt=build_email_generation_prompt(context),
        )

    def review_email(
        self,
        *,
        draft: dict[str, Any],
        customer_safe_context: dict[str, Any],
    ) -> MessageReview:
        """Validate a final trusted-rendered draft before Human Approval."""

        return self._invoke_structured(
            model_name=self.settings.openai_review_model,
            output_schema=_ReviewOutput,
            result_schema=MessageReview,
            prompt=build_message_review_prompt(draft, customer_safe_context),
        )

    def _invoke_structured(
        self,
        *,
        model_name: str,
        output_schema: type[BaseModel],
        result_schema: type[StructuredResult],
        prompt: str,
    ) -> StructuredResult:
        try:
            model = self._create_model(model_name)
            response = model.with_structured_output(
                output_schema,
                method="json_schema",
                strict=True,
            ).invoke(prompt)
            if hasattr(response, "model_dump"):
                response = response.model_dump(mode="json")
            return result_schema.model_validate(response)
        except LLMIntegrationError:
            raise
        except Exception as error:
            raise LLMIntegrationError(
                "The configured LLM did not return valid structured output. "
                "No fallback decision or email was created."
            ) from error

    def _create_model(self, model_name: str) -> Any:
        if self._model_factory is not None:
            return self._model_factory(model_name)

        self.settings.require_openai()
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as error:
            raise LLMIntegrationError(
                "langchain-openai is not installed. Install project requirements."
            ) from error

        return ChatOpenAI(
            model=model_name,
            api_key=self.settings.openai_api_key,
            max_retries=1,
        )


__all__ = ["LLMIntegrationError", "RawajLLMService"]
