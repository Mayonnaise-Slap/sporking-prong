from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Optional, Sequence

from app.critic import DEFAULT_CRITIC_CONFIG, CriticConfig, Finding, critique
from app.grader import (
    DEFAULT_GRADER_CONFIG,
    Criterion,
    GraderConfig,
    Verdict,
    grade,
    points_range,
)
from app.llm import LLMClient
from app.references import external_references


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]
    verdicts: tuple[Verdict, ...]
    summary: Optional[str]
    points_low: float
    points_high: float
    external_references: tuple[str, ...]

    def as_dict(self, applied: Collection[int] = (), comments_written: int = 0) -> dict:
        # `applied` and `comments_written` are outcomes of writing this review
        # down, not part of the review itself — the caller knows them, so they
        # come in rather than being stored here.
        return {
            "summary": self.summary,
            "points_low": self.points_low,
            "points_high": self.points_high,
            "comments_written": comments_written,
            "external_references": list(self.external_references),
            "findings": [finding.as_dict() for finding in self.findings],
            "verdicts": [
                verdict.as_dict() | {"applied": verdict.criterion_id in applied}
                for verdict in self.verdicts
            ],
        }


async def review_submission(
    client: LLMClient,
    statement: str,
    criteria: Sequence[Criterion],
    work: str,
    critic_config: CriticConfig = DEFAULT_CRITIC_CONFIG,
    grader_config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> Review:
    """Two passes over one submission, in the order that makes them work.

    The critic runs first and without the rubric: asked to grade, the model
    answers the rubric's question and a section that exists but is wrong keeps
    full marks. The grader then scores with those findings in hand.
    """
    findings = await critique(client, statement, work, critic_config)
    draft = await grade(client, statement, criteria, work, findings, grader_config)
    low, high = points_range(draft.verdicts, criteria)
    return Review(
        findings=findings,
        verdicts=draft.verdicts,
        summary=draft.summary,
        points_low=low,
        points_high=high,
        external_references=external_references(work),
    )
