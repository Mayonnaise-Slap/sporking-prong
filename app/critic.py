from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

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
from app.prompts import CRITIC_PROMPT

SEVERITIES = ("critical", "major", "minor")


@dataclass(frozen=True)
class CriticConfig:
    max_quote_chars: int = 300
    max_problem_chars: int = 300
    max_why_chars: int = 200
    max_findings: int = 20
    match_threshold: float = DEFAULT_MATCH_THRESHOLD

    @classmethod
    def from_settings(cls, settings: Any) -> "CriticConfig":
        return configure(cls, settings, "critic")


DEFAULT_CRITIC_CONFIG = CriticConfig()


@dataclass(frozen=True)
class Finding:
    quote: str
    problem: str
    severity: str
    why_it_matters: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    @property
    def located(self) -> bool:
        return self.start_line is not None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "problem": self.problem,
            "why_it_matters": self.why_it_matters,
            "quote": self.quote,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


def build_critic_prompt(
    statement: str, work: str, config: CriticConfig = DEFAULT_CRITIC_CONFIG
) -> str:
    return build_prompt(
        statement, work, _critic_fields(config), references=references_block(work)
    )


def _finding_fields(config: CriticConfig) -> tuple[Field, ...]:
    return (
        Field("quote", {"type": "string", "maxLength": config.max_quote_chars},
              "дословная цитата из работы — один непрерывный кусок, без склеек через "
              f"многоточие, не длиннее {config.max_quote_chars} символов"),
        Field("problem", {"type": "string", "maxLength": config.max_problem_chars},
              f"что именно не так, по-русски, не длиннее {config.max_problem_chars} символов"),
        Field("why_it_matters", nullable_string(config.max_why_chars),
              f"почему это важно, по-русски, не длиннее {config.max_why_chars} символов"),
        Field("severity", {"type": "string", "enum": list(SEVERITIES)},
              "один из: " + ", ".join(SEVERITIES)),
    )


def _critic_fields(config: CriticConfig) -> tuple[Field, ...]:
    return (
        array_field("findings", "список находок; пустой, если ничего не нашлось",
                    _finding_fields(config)),
    )


def critic_pass(
    statement: str, work: str, config: CriticConfig = DEFAULT_CRITIC_CONFIG
) -> Pass:
    return Pass(
        name="critic",
        system=CRITIC_PROMPT,
        fields=_critic_fields(config),
        build_user=lambda: build_critic_prompt(statement, work, config),
        parse=lambda payload: parse_findings(payload, work, config),
    )


def parse_findings(
    payload: Any, work: str = "", config: CriticConfig = DEFAULT_CRITIC_CONFIG
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for item in as_list(as_object(payload, "critic"), "findings", "critic"):
        if not isinstance(item, dict):
            continue
        quote = clean_text(item.get("quote"), config.max_quote_chars)
        problem = clean_text(item.get("problem"), config.max_problem_chars)
        if not quote or not problem:
            continue
        severity = item.get("severity")
        start, end = locate(quote, work, config.match_threshold)
        findings.append(
            Finding(
                quote=quote,
                problem=problem,
                severity=severity if severity in SEVERITIES else "minor",
                why_it_matters=clean_text(item.get("why_it_matters"), config.max_why_chars),
                start_line=start,
                end_line=end,
            )
        )

    findings.sort(key=lambda finding: SEVERITIES.index(finding.severity))
    return tuple(findings[: config.max_findings])


async def critique(
    client: LLMClient,
    statement: str,
    work: str,
    config: CriticConfig = DEFAULT_CRITIC_CONFIG,
) -> tuple[Finding, ...]:
    if not work.strip():
        return ()
    return await critic_pass(statement, work, config).run(client)
