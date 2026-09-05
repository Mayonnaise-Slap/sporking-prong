from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional, Protocol, Sequence

from app.config import configure
from app.llm import LLMClient
from app.references import references_block
from app.schema import (
    Field,
    Pass,
    array_field,
    as_list,
    as_object,
    build_prompt,
    clean_text,
    nullable_string,
)
from app.textmatch import DEFAULT_MATCH_THRESHOLD, locate
from app.prompts import GRADER_SYSTEM_PROMPT

STATUSES = ("unmarked", "none", "partial", "full")


@dataclass(frozen=True)
class GraderConfig:
    max_comment_chars: int = 200
    max_summary_chars: int = 1200
    max_evidence_chars: int = 300
    match_threshold: float = DEFAULT_MATCH_THRESHOLD

    @classmethod
    def from_settings(cls, settings: Any) -> "GraderConfig":
        return configure(cls, settings, "grader")


DEFAULT_GRADER_CONFIG = GraderConfig()


class FindingLike(Protocol):
    severity: str
    problem: str
    why_it_matters: Optional[str]
    start_line: Optional[int]


@dataclass(frozen=True)
class Criterion:
    id: int
    title: str
    max_points: float
    min_points: Optional[float] = None

    @classmethod
    def from_row(cls, row: Any) -> "Criterion":
        return cls(
            id=row.id,
            title=row.title,
            max_points=row.max_points,
            min_points=row.min_points,
        )

    @property
    def all_or_nothing(self) -> bool:
        return self.min_points is not None and self.min_points >= self.max_points


@dataclass(frozen=True)
class Verdict:
    criterion_id: int
    status: str
    present: Optional[bool] = None
    issues: Optional[str] = None
    finding_ids: tuple[int, ...] = ()
    points: Optional[float] = None
    comment: Optional[str] = None
    evidence: Optional[str] = None
    evidence_start_line: Optional[int] = None
    evidence_end_line: Optional[int] = None

    def as_dict(self) -> dict:
        return {
            "criterion_id": self.criterion_id,
            "status": self.status,
            "points": self.points,
            "comment": self.comment,
            "evidence": self.evidence,
            "evidence_start_line": self.evidence_start_line,
            "evidence_end_line": self.evidence_end_line,
            "finding_ids": list(self.finding_ids),
        }


@dataclass(frozen=True)
class GradingResult:
    verdicts: tuple[Verdict, ...]
    summary: Optional[str] = None


def _criterion_line(criterion: Criterion) -> str:
    line = f"[id={criterion.id}] {criterion.title} (макс. {criterion.max_points})"
    if criterion.all_or_nothing:
        return line + " — всё или ничего"
    if criterion.min_points is not None:
        return line + f", частичный балл от {criterion.min_points} до {criterion.max_points}"
    return line


def _findings_lines(findings: Sequence[FindingLike]) -> str:
    lines = []
    for number, finding in enumerate(findings, start=1):
        where = f", стр. {finding.start_line}" if finding.start_line else ""
        why = f" — {finding.why_it_matters}" if finding.why_it_matters else ""
        lines.append(f"[{number}] ({finding.severity}{where}) {finding.problem}{why}")
    return "\n".join(lines)


def build_user_prompt(
    statement: str,
    criteria: Sequence[Criterion],
    work: str,
    findings: Sequence[FindingLike] = (),
    config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> str:
    sections = [
        ("КРИТЕРИИ ОЦЕНИВАНИЯ", "\n".join(_criterion_line(item) for item in criteria)),
        ("НАХОДКИ ПРЕДВАРИТЕЛЬНОЙ ПРОВЕРКИ", _findings_lines(findings)),
    ]
    return build_prompt(
        statement,
        work,
        _result_fields(criteria, config),
        sections=sections,
        references=references_block(work),
    )


def _verdict_fields(
    criteria: Sequence[Criterion], config: GraderConfig
) -> tuple[Field, ...]:
    # Order is the reasoning order: everything the model must weigh comes before
    # the verdict, because strict decoding emits fields in schema order.
    return (
        Field("criterion_id", {"type": "integer", "enum": [item.id for item in criteria]},
              "id критерия из списка выше"),
        Field("present", {"type": "boolean"},
              "есть ли в работе содержимое, относящееся к этому критерию"),
        Field("evidence", nullable_string(config.max_evidence_chars),
              "дословная цитата из работы, на которой основан статус; один непрерывный "
              f"кусок, не длиннее {config.max_evidence_chars} символов"),
        Field("issues", nullable_string(config.max_comment_chars),
              "что именно неверно в этом содержимом; пусто, если ошибок нет; не длиннее "
              f"{config.max_comment_chars} символов"),
        Field("finding_ids", {"type": "array", "items": {"type": "integer"}},
              "номера находок предварительной проверки, относящихся к этому критерию; "
              "пустой список, если ни одна не относится"),
        Field("status", {"type": "string", "enum": list(STATUSES)},
              "один из: " + ", ".join(STATUSES)),
        Field("points", {"type": ["number", "null"]},
              "предлагаемый балл; обязателен для partial, для остальных не нужен"),
        Field("comment", nullable_string(config.max_comment_chars),
              "одно короткое предложение по-русски по существу, не длиннее "
              f"{config.max_comment_chars} символов"),
    )


def _result_fields(criteria: Sequence[Criterion], config: GraderConfig) -> tuple[Field, ...]:
    return (
        array_field("verdicts", "по одному вердикту на каждый критерий из списка",
                    _verdict_fields(criteria, config)),
        Field("summary", nullable_string(config.max_summary_chars),
              "разбор работы в целом по правилам выше, не длиннее "
              f"{config.max_summary_chars} символов"),
    )


def grader_pass(
    statement: str,
    criteria: Sequence[Criterion],
    work: str,
    findings: Sequence[FindingLike] = (),
    config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> Pass:
    return Pass(
        name="grader",
        system=GRADER_SYSTEM_PROMPT,
        fields=_result_fields(criteria, config),
        build_user=lambda: build_user_prompt(statement, criteria, work, findings, config),
        parse=lambda payload: parse_result(payload, criteria, work, findings, config),
    )


def _points(status: str, criterion: Criterion, raw: Any) -> Optional[float]:
    if status == "full":
        return criterion.max_points
    if status == "none":
        return 0.0
    if status != "partial" or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    floor = criterion.min_points if criterion.min_points is not None else 0.0
    return round(min(max(float(raw), floor), criterion.max_points), 2)


def _resolve(
    status: str,
    criterion: Criterion,
    present: Optional[bool],
    issues: Optional[str],
    severities: Sequence[str],
    raw_points: Any,
) -> tuple[str, Optional[float]]:
    critical = "critical" in severities
    serious = critical or "major" in severities

    if status == "full" and present is False:
        status = "none"
    if status == "full" and (issues or serious):
        status = "partial"
    if status == "none" and present is True and severities and not critical:
        status = "unmarked"
    if status == "partial" and criterion.all_or_nothing:
        status = "unmarked"

    points = _points(status, criterion, raw_points)
    if status == "partial" and points is None:
        return "unmarked", None
    return status, points


def _finding_ids(raw: Any, count: int) -> tuple[int, ...]:
    values = raw if isinstance(raw, list) else []
    return tuple(
        number
        for number in values
        if isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= count
    )


def parse_verdicts(
    payload: Any,
    criteria: Sequence[Criterion],
    findings: Sequence[FindingLike] = (),
    config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> tuple[Verdict, ...]:
    by_id = {item.id: item for item in criteria}
    seen: dict[int, Verdict] = {}

    for item in as_list(as_object(payload, "grader"), "verdicts", "grader"):
        if not isinstance(item, dict):
            continue
        criterion_id = item.get("criterion_id")
        if criterion_id not in by_id or criterion_id in seen:
            continue

        status = item.get("status")
        present = item.get("present")
        issues = clean_text(item.get("issues"), config.max_comment_chars)
        finding_ids = _finding_ids(item.get("finding_ids"), len(findings))
        status, points = _resolve(
            status if status in STATUSES else "unmarked",
            by_id[criterion_id],
            present,
            issues,
            [findings[number - 1].severity for number in finding_ids],
            item.get("points"),
        )
        seen[criterion_id] = Verdict(
            criterion_id=criterion_id,
            status=status,
            present=present if isinstance(present, bool) else None,
            issues=issues,
            finding_ids=finding_ids,
            points=points,
            comment=clean_text(item.get("comment"), config.max_comment_chars),
            evidence=clean_text(item.get("evidence"), config.max_evidence_chars),
        )

    return tuple(
        seen.get(item.id, Verdict(criterion_id=item.id, status="unmarked")) for item in criteria
    )


def parse_result(
    payload: Any,
    criteria: Sequence[Criterion],
    work: str = "",
    findings: Sequence[FindingLike] = (),
    config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> GradingResult:
    data = as_object(payload, "grader")
    verdicts = []
    for verdict in parse_verdicts(data, criteria, findings, config):
        start, end = locate(verdict.evidence, work, config.match_threshold)
        verdicts.append(replace(verdict, evidence_start_line=start, evidence_end_line=end))
    return GradingResult(
        verdicts=tuple(verdicts),
        summary=clean_text(data.get("summary"), config.max_summary_chars),
    )


def points_range(
    verdicts: Sequence[Verdict], criteria: Sequence[Criterion]
) -> tuple[float, float]:
    max_by_id = {item.id: item.max_points for item in criteria}
    low = sum(verdict.points for verdict in verdicts if verdict.points is not None)
    open_points = sum(
        max_by_id.get(verdict.criterion_id, 0.0)
        for verdict in verdicts
        if verdict.points is None
    )
    return round(low, 2), round(low + open_points, 2)


async def grade(
    client: LLMClient,
    statement: str,
    criteria: Sequence[Criterion],
    work: str,
    findings: Sequence[FindingLike] = (),
    config: GraderConfig = DEFAULT_GRADER_CONFIG,
) -> GradingResult:
    if not criteria:
        return GradingResult(verdicts=())
    return await grader_pass(statement, criteria, work, findings, config).run(client)
