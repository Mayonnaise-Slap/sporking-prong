"""Локальная детекция ИИ-текста на GigaCheck-Classifier-Multi.

Модель весит 14,5 ГБ и грузится минутами, поэтому она живёт в модуле как
ленивый синглтон: воркер платит за загрузку один раз при первой задаче.
torch импортируется внутри функций, иначе процесс API, который тянет
JOB_HANDLERS ради постановки задач, тоже грузил бы torch в память.

Голова и пулинг воспроизводят gigacheck/model/mistral_ai_detector.py, чтобы
не тащить пакет gigacheck: он требует deepspeed и flash-attn, нужные только
для обучения и не собирающиеся на macOS.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.config import configure

_WORD_RE = re.compile(r"\S+")

PROVIDER = "gigacheck"


@dataclass(frozen=True)
class AICheckConfig:
    # Каталог со снапшотом весов. Пусто — детектор выключен, задача пишет
    # "unavailable" вместо падения.
    model_dir: str = ""
    # Пусто — выбрать mps/cuda, если доступны, иначе cpu.
    device: str = ""
    # Человеческая проза на контроле дала 0,0-0,1%, машинная 100%, так что
    # порог стоит в разрыве. Управляет только предупреждением в интерфейсе.
    review_threshold_pct: float = 60.0
    # Короткое окно завышает оценку: один и тот же текст дал 98% на 110
    # словах, 29% на 250 и 2% на 330. Ниже этого порога вердикт говорит о
    # размере образца, а не об авторстве, поэтому такой текст не оцениваем.
    min_words: int = 200
    # Инференс идёт десятки секунд на фрагмент, так что длинную работу режем.
    max_chunks: int = 6
    # Окно, набравшее меньше этого числа слов, не выбрасывается, а достраивается
    # назад по уже проверенному тексту — см. _split_chunks. Порог именно в
    # словах: на токенах окно бывает полным и при 194 словах (плотный код), а
    # завышает оценку как раз бедный контекст, а не бедный словарь.
    min_chunk_words: int = 200

    @classmethod
    def from_settings(cls, settings: Any) -> "AICheckConfig":
        return configure(cls, settings, "aicheck")


DEFAULT_CONFIG = AICheckConfig()


@dataclass(frozen=True)
class Span:
    start_line: int
    end_line: int
    score_pct: float

    def as_dict(self) -> dict:
        return {"start_line": self.start_line, "end_line": self.end_line, "score_pct": self.score_pct}


@dataclass(frozen=True)
class AICheckReport:
    status: str  # ok | skipped | unavailable
    label: str  # human | ai | unknown
    # Максимум по фрагментам: одна дописанная моделью глава не должна
    # растворяться в среднем по работе.
    ai_score_pct: float
    # Доля слов в помеченных фрагментах — «сколько текста выглядит машинным».
    ai_text_pct: float
    chunks_total: int
    chunks_flagged: int
    words_scored: int
    words_total: int
    review_threshold_pct: float
    spans: tuple[Span, ...]
    detail: Optional[str] = None

    @property
    def truncated(self) -> bool:
        return self.words_scored < self.words_total

    @property
    def needs_review(self) -> bool:
        return self.status == "ok" and self.ai_score_pct >= self.review_threshold_pct

    def as_dict(self) -> dict:
        return {
            "provider": PROVIDER,
            "status": self.status,
            "label": self.label,
            "ai_score_pct": self.ai_score_pct,
            "ai_text_pct": self.ai_text_pct,
            "chunks_total": self.chunks_total,
            "chunks_flagged": self.chunks_flagged,
            "words_scored": self.words_scored,
            "words_total": self.words_total,
            "truncated": self.truncated,
            "needs_review": self.needs_review,
            "review_threshold_pct": self.review_threshold_pct,
            "spans": [span.as_dict() for span in self.spans],
            "detail": self.detail,
        }


def _empty(status: str, config: AICheckConfig, words_total: int, detail: Optional[str]) -> AICheckReport:
    return AICheckReport(
        status=status,
        label="unknown",
        ai_score_pct=0.0,
        ai_text_pct=0.0,
        chunks_total=0,
        chunks_flagged=0,
        words_scored=0,
        words_total=words_total,
        review_threshold_pct=config.review_threshold_pct,
        spans=(),
        detail=detail,
    )


class _Detector:
    """Загруженная модель. Создаётся один раз на процесс."""

    def __init__(self, model_dir: pathlib.Path, device: str):
        import torch
        import torch.nn as nn
        from safetensors.torch import load_file
        from transformers import AutoTokenizer, MistralConfig, MistralModel

        # transformers 5.x отбрасывает max_length как устаревший генерационный
        # параметр и подменяет id2label заглушками, поэтому читаем из файла.
        raw = json.loads((model_dir / "config.json").read_text())
        self.max_length = int(raw["max_length"])
        self.id2label = {int(key): value for key, value in raw["id2label"].items()}
        self.ai_id = next(index for index, name in self.id2label.items() if name == "ai")

        config = MistralConfig.from_pretrained(model_dir)
        # Собираем сразу в bfloat16: в float32 семь миллиардов параметров
        # заняли бы 29 ГБ ещё до загрузки весов.
        torch.set_default_dtype(torch.bfloat16)
        try:
            backbone = MistralModel(config)
            dense = nn.Linear(config.hidden_size, config.hidden_size)
            out_proj = nn.Linear(config.hidden_size, 2)
        finally:
            torch.set_default_dtype(torch.float32)

        backbone_sd: dict = {}
        dense_sd: dict = {}
        out_sd: dict = {}
        for shard in sorted(model_dir.glob("model-*.safetensors")):
            for key, tensor in load_file(str(shard)).items():
                if key.startswith("model."):
                    backbone_sd[key[len("model.") :]] = tensor
                elif key.startswith("classification_head.dense."):
                    dense_sd[key[len("classification_head.dense.") :]] = tensor
                elif key.startswith("classification_head.out_proj."):
                    out_sd[key[len("classification_head.out_proj.") :]] = tensor

        missing, unexpected = backbone.load_state_dict(backbone_sd, strict=False)
        if unexpected or any("rotary" not in name for name in missing):
            raise ValueError(f"веса не подошли: лишние={unexpected[:3]} отсутствуют={missing[:3]}")
        dense.load_state_dict(dense_sd)
        out_proj.load_state_dict(out_sd)

        if not device:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        self.torch = torch
        self.backbone = backbone.to(device).eval()
        self.dense = dense.to(device).eval()
        self.out_proj = out_proj.to(device).eval()
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)

    def token_count(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=False).input_ids)

    def split_by_tokens(self, text: str, budget: int) -> list[str]:
        """Разрезать текст на куски, точно влезающие в окно модели."""
        ids = self.tokenizer(text, add_special_tokens=False).input_ids
        return [
            self.tokenizer.decode(ids[start : start + budget], skip_special_tokens=True)
            for start in range(0, len(ids), budget)
        ]

    def ai_probability(self, text: str) -> float:
        torch = self.torch
        with torch.no_grad():
            ids = self.tokenizer(text, add_special_tokens=False).input_ids[: self.max_length - 2]
            ids = [self.tokenizer.bos_token_id] + ids + [self.tokenizer.eos_token_id]
            input_ids = torch.tensor([ids], device=self.device)
            hidden = self.backbone(input_ids, attention_mask=torch.ones_like(input_ids))[0]
            # Без паддинга пулинг GigaCheck берёт последний токен (EOS).
            logits = self.out_proj(torch.tanh(self.dense(hidden[0, -1])))
            probs = torch.softmax(logits.float(), dim=-1)
            return float(probs[self.ai_id]) * 100


_detector: Optional[_Detector] = None
_detector_key: tuple[str, str] = ("", "")
_detector_lock = asyncio.Lock()


def _get_detector(config: AICheckConfig) -> _Detector:
    global _detector, _detector_key
    key = (config.model_dir, config.device)
    if _detector is None or _detector_key != key:
        _detector = _Detector(pathlib.Path(config.model_dir), config.device)
        _detector_key = key
    return _detector


@dataclass(frozen=True)
class _Chunk:
    text: str
    start_line: int
    end_line: int
    words: int


def _split_chunks(text: str, detector: _Detector, config: AICheckConfig) -> list[_Chunk]:
    """Нарезать текст на окна, влезающие в лимит токенов модели.

    Границы по возможности идут по строкам, чтобы номера строк в отчёте
    совпадали с тем, что видит проверяющий. Строка длиннее окна (в docx это
    абзац на всю работу) режется по токенам: иначе модель молча получила бы
    обрезок, а отчёт считал бы всю строку проверенной.

    Недобравшее окно не выбрасывается, а достраивается назад, по уже
    проверенному тексту. Иначе без оценки оставались и хвост работы, и участки,
    плотные по токенам, но бедные словами: блок кода из ноутбука заполнил окно
    на 1014 токенов из 1022, набрав лишь 194 слова, и выпадал целиком — причём
    из середины документа, а не с конца.

    Платой служит нахлёст: вердикт достроенного окна относится и к повторно
    взятым строкам, поэтому по нему нельзя судить об одном лишь хвосте.
    """
    budget = detector.max_length - 2
    lines = text.split("\n")
    # Токенизация не бесплатна, а строк бывают сотни: считаем стоимость раз.
    # Оценка приблизительная — токенизатор склеивает границу строк иначе, чем
    # сумма строк по отдельности, — поэтому готовое окно ниже проверяется точно.
    costs = [detector.token_count(line) + 1 for line in lines]  # +1 за перенос
    line_words = [len(_WORD_RE.findall(line)) for line in lines]

    chunks: list[_Chunk] = []
    covered: set[int] = set()
    index = 0

    def add(body: str, first: int, last: int, words: int) -> None:
        """Записать окно. first и last — номера строк, 1-based включительно."""
        chunks.append(_Chunk(body, first, last, words))
        covered.update(range(first - 1, last))

    while index < len(lines) and len(chunks) < config.max_chunks:
        if costs[index] - 1 > budget:
            # Строка длиннее окна — в docx это абзац на всю работу. Режем по
            # токенам, иначе модель получила бы обрезок.
            for piece in detector.split_by_tokens(lines[index], budget):
                add(piece, index + 1, index + 1, len(_WORD_RE.findall(piece)))
                if len(chunks) >= config.max_chunks:
                    return chunks
            index += 1
            continue

        end, tokens = index, 0
        while end < len(lines) and costs[end] - 1 <= budget and tokens + costs[end] <= budget:
            tokens += costs[end]
            end += 1
        end = max(end, index + 1)  # окно всегда забирает хотя бы одну строку

        start = index
        if sum(line_words[start:end]) < config.min_chunk_words:
            while start > 0 and tokens + costs[start - 1] <= budget:
                start -= 1
                tokens += costs[start]

        # Теперь по факту: ai_probability обрезает всё сверх бюджета молча, и
        # отчёт считал бы обрезанные строки проверенными. Нахлёст отдаём первым —
        # он лишь дублирует уже проверенный текст.
        while end - start > 1 and detector.token_count("\n".join(lines[start:end])) > budget:
            if start < index:
                start += 1
            else:
                end -= 1

        # Окно из одних пробелов и уже проверенных строк не несёт нового: тратить
        # на него полминуты инференса незачем.
        if any(line_words[at] and at not in covered for at in range(start, end)):
            add("\n".join(lines[start:end]), start + 1, end, sum(line_words[start:end]))
        index = end

    return chunks


def _analyze(text: str, config: AICheckConfig) -> AICheckReport:
    words_total = len(_WORD_RE.findall(text))

    if not config.model_dir:
        return _empty("unavailable", config, words_total, "AICHECK_MODEL_DIR не задан")
    if not pathlib.Path(config.model_dir).is_dir():
        return _empty("unavailable", config, words_total, f"каталог модели не найден: {config.model_dir}")
    if words_total < config.min_words:
        return _empty("skipped", config, words_total, f"слишком короткий текст ({words_total} < {config.min_words} слов)")

    try:
        detector = _get_detector(config)
    except Exception as error:  # noqa: BLE001 — отказ модели не должен валить конвейер
        return _empty("unavailable", config, words_total, f"{type(error).__name__}: {error}")

    chunks = _split_chunks(text, detector, config)
    if not chunks:
        return _empty("skipped", config, words_total, "не удалось выделить фрагмент достаточной длины")

    # Окна перекрываются, поэтому слова считаем по объединению строк: сумма по
    # фрагментам дала бы покрытие больше 100%. Строку, разрезанную по токенам,
    # объединение помечает целиком — она и так представляет один абзац.
    line_words = [len(_WORD_RE.findall(line)) for line in text.split("\n")]
    spans: list[Span] = []
    scored_lines: set[int] = set()
    flagged_lines: set[int] = set()
    top_score = 0.0
    for chunk in chunks:
        score = detector.ai_probability(chunk.text)
        window = range(chunk.start_line - 1, chunk.end_line)
        scored_lines.update(window)
        top_score = max(top_score, score)
        if score >= config.review_threshold_pct:
            flagged_lines.update(window)
            spans.append(Span(chunk.start_line, chunk.end_line, round(score, 1)))

    words_scored = sum(line_words[at] for at in scored_lines)
    ai_words = sum(line_words[at] for at in flagged_lines)

    return AICheckReport(
        status="ok",
        label="ai" if spans else "human",
        ai_score_pct=round(top_score, 1),
        ai_text_pct=round(100.0 * ai_words / words_scored, 1) if words_scored else 0.0,
        chunks_total=len(chunks),
        chunks_flagged=len(spans),
        words_scored=words_scored,
        words_total=words_total,
        review_threshold_pct=config.review_threshold_pct,
        spans=tuple(spans),
        detail=None,
    )


async def check_text(text: str, config: AICheckConfig = DEFAULT_CONFIG) -> AICheckReport:
    """Оценить авторство текста, деградируя вместо исключения.

    Инференс блокирует поток на секунды, поэтому уходит в отдельный поток:
    воркер тем временем обслуживает остальные задачи. Блокировка не даёт двум
    задачам одновременно грузить 14 ГБ весов.
    """
    async with _detector_lock:
        return await asyncio.to_thread(_analyze, text, config)
