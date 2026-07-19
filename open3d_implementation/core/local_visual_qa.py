"""Local-only vision-language evaluation for private AI Film frames."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Mapping, Protocol, Sequence, cast

from PIL import Image, UnidentifiedImageError


DEFAULT_LOCAL_VISION_QA_MODEL = "HuggingFaceTB/SmolVLM-500M-Instruct"
DEFAULT_LOCAL_AGE_QA_MODEL = "dima806/fairface_age_image_detection"


class LocalVisualQAError(RuntimeError):
    """Raised when the local vision evaluator cannot produce a response."""


LocalVisualAnswerValue = Literal["yes", "no", "uncertain"]


@dataclass(frozen=True)
class LocalVisualCriterion:
    """One atomic visual assertion evaluated by the local VLM."""

    code: str
    question: str
    expected: Literal["yes", "no"]
    weight: float
    critical: bool = False
    hero_object: bool = False


@dataclass(frozen=True)
class LocalVisualAnswer:
    """Normalized answer and provenance for one local visual criterion."""

    criterion: LocalVisualCriterion
    answer: LocalVisualAnswerValue
    raw_response: str

    @property
    def matched(self) -> bool:
        return self.answer == self.criterion.expected


@dataclass(frozen=True)
class LocalAgeEstimate:
    """Age-bracket probabilities produced from one explicitly bounded face crop."""

    predicted_label: str
    probabilities: Mapping[str, float]
    crop_box: tuple[float, float, float, float]
    model_name: str


class _TensorLike(Protocol):
    shape: tuple[int, ...]

    def __getitem__(self, key: object) -> "_TensorLike": ...


class _Processor(Protocol):
    def apply_chat_template(
        self,
        conversation: list[dict[str, object]],
        *,
        add_generation_prompt: bool,
    ) -> str: ...

    def __call__(
        self,
        *,
        text: str,
        images: list[Image.Image],
        return_tensors: str,
    ) -> dict[str, object]: ...

    def batch_decode(
        self,
        sequences: object,
        *,
        skip_special_tokens: bool,
    ) -> list[str]: ...


class _Model(Protocol):
    def eval(self) -> object: ...

    def generate(self, **kwargs: object) -> object: ...


class _ClassifierConfig(Protocol):
    id2label: Mapping[int, str]


class _ProbabilityTensor(Protocol):
    def softmax(self, dim: int) -> "_ProbabilityTensor": ...

    def __getitem__(self, key: object) -> "_ProbabilityTensor": ...

    def tolist(self) -> list[float]: ...


class _ClassifierOutput(Protocol):
    logits: _ProbabilityTensor


class _ImageClassifierModel(Protocol):
    config: _ClassifierConfig

    def eval(self) -> object: ...

    def __call__(self, **kwargs: object) -> _ClassifierOutput: ...


class _ImageProcessor(Protocol):
    def __call__(
        self,
        *,
        images: Image.Image,
        return_tensors: str,
    ) -> dict[str, object]: ...


def _local_files_only() -> bool:
    return os.getenv("LOCAL_VISION_QA_OFFLINE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _local_longest_edge() -> int:
    raw_value = os.getenv("LOCAL_VISION_QA_LONGEST_EDGE", "1024").strip()
    try:
        value = int(raw_value)
    except ValueError:
        value = 1024
    return max(512, min(1536, value))


@lru_cache(maxsize=2)
def _load_local_vision_model(
    model_name: str,
    longest_edge: int,
) -> tuple[_Processor, _Model]:
    try:
        import torch
        from transformers import AutoModelForVision2Seq, AutoProcessor
    except ImportError as exc:
        raise LocalVisualQAError("local_vlm:sdk_unavailable") from exc

    try:
        processor = AutoProcessor.from_pretrained(
            model_name,
            size={"longest_edge": longest_edge},
            local_files_only=_local_files_only(),
        )
        model = AutoModelForVision2Seq.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            _attn_implementation="eager",
            low_cpu_mem_usage=True,
            local_files_only=_local_files_only(),
        )
        model.eval()
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_vlm:model_load_failed:{type(exc).__name__}:{str(exc)[:240]}"
        ) from exc
    return cast(_Processor, processor), cast(_Model, model)


@lru_cache(maxsize=2)
def _load_local_age_model(
    model_name: str,
) -> tuple[_ImageProcessor, _ImageClassifierModel]:
    try:
        from transformers import ViTForImageClassification, ViTImageProcessor
    except ImportError as exc:
        raise LocalVisualQAError("local_age:sdk_unavailable") from exc

    try:
        processor = ViTImageProcessor.from_pretrained(
            model_name,
            local_files_only=_local_files_only(),
        )
        model = ViTForImageClassification.from_pretrained(
            model_name,
            local_files_only=_local_files_only(),
        )
        model.eval()
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_age:model_load_failed:{type(exc).__name__}:{str(exc)[:240]}"
        ) from exc
    return cast(_ImageProcessor, processor), cast(_ImageClassifierModel, model)


def _load_rgb_image(image_path: Path) -> Image.Image:
    if not image_path.is_file():
        raise LocalVisualQAError("local_vlm:missing_image")
    try:
        with Image.open(image_path) as source:
            return source.convert("RGB")
    except (OSError, UnidentifiedImageError) as exc:
        raise LocalVisualQAError(
            f"local_vlm:invalid_image:{type(exc).__name__}"
        ) from exc


def _run_local_visual_prompt(
    *,
    processor: _Processor,
    model: _Model,
    image: Image.Image,
    prompt: str,
    max_new_tokens: int,
) -> str:
    try:
        import torch
    except ImportError as exc:
        raise LocalVisualQAError("local_vlm:torch_unavailable") from exc

    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    try:
        chat_prompt = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
        )
        inputs = processor(
            text=chat_prompt,
            images=[image],
            return_tensors="pt",
        )
        input_ids = cast(_TensorLike, inputs["input_ids"])
        with torch.inference_mode():
            generated_ids = cast(
                _TensorLike,
                model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                ),
            )
        response_start = input_ids.shape[-1]
        response_tokens = generated_ids[:, response_start:]
        responses = processor.batch_decode(
            response_tokens,
            skip_special_tokens=True,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_vlm:inference_failed:{type(exc).__name__}:{str(exc)[:240]}"
        ) from exc

    response = responses[0].strip() if responses else ""
    if not response:
        raise LocalVisualQAError("local_vlm:empty_response")
    return response


def _normalize_binary_answer(response: str) -> LocalVisualAnswerValue:
    match = re.search(r"\b(yes|no|uncertain)\b", response.strip().lower())
    if not match:
        return "uncertain"
    return cast(LocalVisualAnswerValue, match.group(1))


def evaluate_local_visual_qa(
    *,
    image_path: Path,
    prompt: str,
    model_name: str = DEFAULT_LOCAL_VISION_QA_MODEL,
    max_new_tokens: int = 240,
) -> str:
    """Evaluate one local image without sending image or prompt data off-device."""

    bounded_tokens = max(96, min(800, int(max_new_tokens)))
    image = _load_rgb_image(image_path)
    processor, model = _load_local_vision_model(model_name, _local_longest_edge())
    return _run_local_visual_prompt(
        processor=processor,
        model=model,
        image=image,
        prompt=prompt,
        max_new_tokens=bounded_tokens,
    )


def evaluate_local_visual_checklist(
    *,
    image_path: Path,
    criteria: Sequence[LocalVisualCriterion],
    model_name: str = DEFAULT_LOCAL_VISION_QA_MODEL,
) -> list[LocalVisualAnswer]:
    """Evaluate bounded atomic criteria while loading the image and model once."""

    bounded_criteria = list(criteria[:16])
    if not bounded_criteria:
        raise LocalVisualQAError("local_vlm:empty_criteria")
    image = _load_rgb_image(image_path)
    processor, model = _load_local_vision_model(model_name, _local_longest_edge())
    answers: list[LocalVisualAnswer] = []
    for criterion in bounded_criteria:
        response = _run_local_visual_prompt(
            processor=processor,
            model=model,
            image=image,
            prompt=(
                "Inspect the full image. Answer only yes, no, or uncertain. "
                f"{criterion.question}"
            ),
            max_new_tokens=8,
        )
        answers.append(
            LocalVisualAnswer(
                criterion=criterion,
                answer=_normalize_binary_answer(response),
                raw_response=response[:120],
            )
        )
    return answers


def evaluate_local_age_classification(
    *,
    image_path: Path,
    crop_box: tuple[float, float, float, float],
    model_name: str = DEFAULT_LOCAL_AGE_QA_MODEL,
) -> LocalAgeEstimate:
    """Classify one fictional-character face crop without transmitting the frame."""

    left, top, right, bottom = crop_box
    if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
        raise LocalVisualQAError("local_age:invalid_crop_box")
    image = _load_rgb_image(image_path)
    crop = image.crop(
        (
            round(image.width * left),
            round(image.height * top),
            round(image.width * right),
            round(image.height * bottom),
        )
    )
    processor, model = _load_local_age_model(model_name)
    try:
        import torch
    except ImportError as exc:
        raise LocalVisualQAError("local_age:torch_unavailable") from exc

    try:
        inputs = processor(images=crop, return_tensors="pt")
        with torch.inference_mode():
            output = model(**inputs)
        probability_values = output.logits.softmax(dim=-1)[0].tolist()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_age:inference_failed:{type(exc).__name__}:{str(exc)[:240]}"
        ) from exc
    probabilities = {
        str(model.config.id2label.get(index, str(index))): round(float(value), 6)
        for index, value in enumerate(probability_values)
    }
    if not probabilities:
        raise LocalVisualQAError("local_age:empty_response")
    predicted_label = max(probabilities, key=probabilities.__getitem__)
    return LocalAgeEstimate(
        predicted_label=predicted_label,
        probabilities=probabilities,
        crop_box=crop_box,
        model_name=model_name,
    )
