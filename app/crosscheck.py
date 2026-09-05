
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from rapidfuzz.distance import LCSseq

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


@dataclass(frozen=True)
class CrossCheckConfig:
    min_block_tokens: int = 4
    merge_gap_tokens: int = 3
    boilerplate_doc_ratio: float = 0.6
    min_docs_for_boilerplate: int = 5
    threshold_pct: float = 25.0
    max_matches: int = 5

    @classmethod
    def from_settings(cls, settings: Any) -> "CrossCheckConfig":
        return cls(
            min_block_tokens=settings.crosscheck_min_block_tokens,
            merge_gap_tokens=settings.crosscheck_merge_gap_tokens,
            boilerplate_doc_ratio=settings.crosscheck_boilerplate_doc_ratio,
            min_docs_for_boilerplate=settings.crosscheck_min_docs_for_boilerplate,
            threshold_pct=settings.crosscheck_threshold_pct,
            max_matches=settings.crosscheck_max_matches,
        )


DEFAULT_CONFIG = CrossCheckConfig()


@dataclass(frozen=True)
class Document:
    submission_id: int
    words: tuple[str, ...]
    lines: tuple[int, ...]

    def __len__(self) -> int:
        return len(self.words)


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    matched_start: int
    matched_end: int


@dataclass(frozen=True)
class MatchedSpan:
    start_line: int
    end_line: int
    matched_start_line: int
    matched_end_line: int

    def as_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "matched_start_line": self.matched_start_line,
            "matched_end_line": self.matched_end_line,
        }


@dataclass(frozen=True)
class Match:
    matched_submission_id: int
    similarity_pct: float
    spans: tuple[MatchedSpan, ...]
    note: str


@dataclass(frozen=True)
class CrossCheckReport:
    submission_id: int
    overall_similarity_pct: float
    matches: tuple[Match, ...]
    threshold_pct: float
    cohort_complete: bool
    boilerplate_filtered: bool
    boilerplate_tokens: int
    reference_tokens: int
    token_count: int
    cohort_size: int

    @property
    def provisional(self) -> bool:
        return not self.cohort_complete

    @property
    def flagged(self) -> bool:
        return self.cohort_complete and self.overall_similarity_pct >= self.threshold_pct

    @property
    def reference_overlap_pct(self) -> float:
        return _pct(self.reference_tokens, self.token_count)

    @property
    def cohort_overlap_pct(self) -> float:
        return _pct(self.boilerplate_tokens, self.token_count)

    def as_dict(self) -> dict:
        return {
            "overall_similarity_pct": self.overall_similarity_pct,
            "threshold_pct": self.threshold_pct,
            "flagged": self.flagged,
            "provisional": self.provisional,
            "cohort_complete": self.cohort_complete,
            "cohort_size": self.cohort_size,
            "boilerplate_filtered": self.boilerplate_filtered,
            "boilerplate_tokens": self.boilerplate_tokens,
            "cohort_overlap_pct": self.cohort_overlap_pct,
            "reference_tokens": self.reference_tokens,
            "reference_overlap_pct": self.reference_overlap_pct,
            "matches": [
                {
                    "matched_submission_id": match.matched_submission_id,
                    "similarity_pct": match.similarity_pct,
                    "note": match.note,
                    "spans": [span.as_dict() for span in match.spans],
                }
                for match in self.matches
            ],
        }


def build_document(submission_id: int, text: str) -> Document:
    words: list[str] = []
    lines: list[int] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for word in _WORD_RE.findall(line.lower()):
            words.append(word)
            lines.append(line_number)
    return Document(submission_id=submission_id, words=tuple(words), lines=tuple(lines))


def align(
    target: Document, other: Document, config: CrossCheckConfig = DEFAULT_CONFIG
) -> tuple[Block, ...]:
    if not target.words or not other.words:
        return ()

    blocks: list[list[int]] = []
    for opcode in LCSseq.opcodes(target.words, other.words):
        if opcode.tag != "equal" or opcode.src_end - opcode.src_start < config.min_block_tokens:
            continue
        run = [opcode.src_start, opcode.src_end, opcode.dest_start, opcode.dest_end]
        if blocks:
            previous = blocks[-1]
            near_in_both = (
                run[0] - previous[1] <= config.merge_gap_tokens
                and run[2] - previous[3] <= config.merge_gap_tokens
            )
            if near_in_both:
                previous[1], previous[3] = run[1], run[3]
                continue
        blocks.append(run)

    return tuple(Block(*block) for block in blocks)


def _matched_indices(blocks: Sequence[Block]) -> set[int]:
    return {index for block in blocks for index in range(block.start, block.end)}


def _to_spans(target: Document, other: Document, blocks: Sequence[Block]) -> tuple[MatchedSpan, ...]:
    return tuple(
        MatchedSpan(
            start_line=target.lines[block.start],
            end_line=target.lines[block.end - 1],
            matched_start_line=other.lines[block.matched_start],
            matched_end_line=other.lines[block.matched_end - 1],
        )
        for block in blocks
    )


def _match(
    target: Document,
    other: Document,
    blocks: Sequence[Block],
    ignored: frozenset[int],
) -> Optional[Match]:
    considered = set(range(len(target))) - ignored
    matched = _matched_indices(blocks) - ignored
    if not blocks or not considered or not matched:
        return None

    spans = _to_spans(target, other, blocks)
    longest = max(block.end - block.start for block in blocks)
    return Match(
        matched_submission_id=other.submission_id,
        similarity_pct=_pct(len(matched), len(considered)),
        spans=spans,
        note=f"{len(spans)} matching fragment(s), longest {longest} words",
    )


def cross_check(
    target: Document,
    cohort: Sequence[Document],
    reference_texts: Sequence[str] = (),
    config: CrossCheckConfig = DEFAULT_CONFIG,
    cohort_complete: bool = False,
) -> CrossCheckReport:
    others = [document for document in cohort if document.submission_id != target.submission_id]
    reference = frozenset(
        index
        for text in reference_texts
        for index in _matched_indices(align(target, build_document(0, text), config))
    )
    alignments = {other.submission_id: align(target, other, config) for other in others}
    boilerplate: frozenset[int] = frozenset()
    if len(others) >= config.min_docs_for_boilerplate:
        coverage: Counter[int] = Counter()
        for blocks in alignments.values():
            coverage.update(_matched_indices(blocks) - reference)
        cutoff = config.boilerplate_doc_ratio * len(others)
        boilerplate = frozenset(index for index, count in coverage.items() if count > cutoff)

    ignored = reference | boilerplate
    matches = [
        match
        for other in others
        if (match := _match(target, other, alignments[other.submission_id], ignored))
    ]
    matches.sort(key=lambda match: match.similarity_pct, reverse=True)

    considered = set(range(len(target))) - ignored
    covered = {
        index for blocks in alignments.values() for index in _matched_indices(blocks)
    } - ignored

    return CrossCheckReport(
        submission_id=target.submission_id,
        overall_similarity_pct=_pct(len(covered), len(considered)),
        matches=tuple(matches[: config.max_matches]),
        threshold_pct=config.threshold_pct,
        cohort_complete=cohort_complete,
        boilerplate_filtered=bool(boilerplate),
        boilerplate_tokens=len(boilerplate),
        reference_tokens=len(reference),
        token_count=len(target),
        cohort_size=len(others),
    )
