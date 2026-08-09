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
DEFAULT_LOCAL_VISION_QA_REVISION = "a7da5b986cb59b408707209984f360a5f4ad7e47"
DEFAULT_LOCAL_AGE_QA_REVISION = "4e02ab8057ea7fd74b1670940995c5dfda3e6ec0"
DEFAULT_LOCAL_IDENTITY_MODEL = "facebook/dinov2-small"
DEFAULT_LOCAL_IDENTITY_REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"


class LocalVisualQAError(RuntimeError):
    """Raised when the local vision evaluator cannot produce a response."""


LocalVisualAnswerValue = Literal["yes", "no", "uncertain"]
LocalSmallAnimalLabel = Literal["mouse", "cat", "dog", "rabbit", "other", "none"]


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


@dataclass(frozen=True)
class LocalIdentityAssessment:
    """Reference-backed identity comparison for one recurring fictional character."""

    character_id: str
    score: float
    accepted: bool
    answers: tuple[LocalVisualAnswer, ...]
    model_name: str


@dataclass(frozen=True)
class LocalNarrativeIdentityAssessment:
    """Contrastive identity result for one character inside a narrative frame."""

    character_id: str
    score: float
    accepted: bool
    face_similarity: float
    closest_negative_similarity: float | None
    similarity_margin: float | None
    face_threshold: float
    margin_threshold: float
    reference_boxes: tuple[tuple[int, int, int, int], ...]
    candidate_box: tuple[int, int, int, int]
    issues: tuple[str, ...]
    model_name: str


@dataclass(frozen=True)
class LocalCastIdentityAssessment:
    """Deterministic embedding comparison for two neutral Cast Bible views."""

    score: float
    accepted: bool
    crop_similarity: float
    composition_similarity: float
    crop_threshold: float
    composition_threshold: float | None
    reference_box: tuple[int, int, int, int]
    candidate_box: tuple[int, int, int, int]
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


class _EmbeddingProcessor(Protocol):
    def __call__(
        self,
        *,
        images: list[Image.Image],
        return_tensors: str,
    ) -> dict[str, object]: ...


class _EmbeddingOutput(Protocol):
    last_hidden_state: object


class _EmbeddingModel(Protocol):
    def eval(self) -> object: ...

    def __call__(self, **kwargs: object) -> _EmbeddingOutput: ...


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


def _model_revision(
    *,
    model_name: str,
    env_name: str,
    default_model: str,
    default_revision: str,
) -> str:
    configured_revision = os.getenv(env_name, "").strip()
    if configured_revision:
        return configured_revision
    if model_name == default_model:
        return default_revision
    raise LocalVisualQAError(f"local_model:revision_required:{env_name}")


@lru_cache(maxsize=2)
def _load_local_vision_model(
    model_name: str,
    revision: str,
    longest_edge: int,
) -> tuple[_Processor, _Model]:
    try:
        import torch
        from transformers import AutoModelForVision2Seq, AutoProcessor
    except ImportError as exc:
        raise LocalVisualQAError("local_vlm:sdk_unavailable") from exc

    load_error: Exception | None = None
    attempts = (True,) if _local_files_only() else (True, False)
    for local_files_only in attempts:
        try:
            processor = AutoProcessor.from_pretrained(
                model_name,
                revision=revision,
                size={"longest_edge": longest_edge},
                local_files_only=local_files_only,
            )
            model = AutoModelForVision2Seq.from_pretrained(
                model_name,
                revision=revision,
                torch_dtype=torch.float32,
                _attn_implementation="eager",
                low_cpu_mem_usage=True,
                local_files_only=local_files_only,
            )
            model.eval()
            return cast(_Processor, processor), cast(_Model, model)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            load_error = exc
    assert load_error is not None
    raise LocalVisualQAError(
        f"local_vlm:model_load_failed:{type(load_error).__name__}:{str(load_error)[:240]}"
    ) from load_error


@lru_cache(maxsize=1)
def _load_local_identity_model(
    model_name: str,
    revision: str,
) -> tuple[_EmbeddingProcessor, _EmbeddingModel]:
    try:
        from transformers import AutoImageProcessor, AutoModel
    except ImportError as exc:
        raise LocalVisualQAError("local_identity:sdk_unavailable") from exc

    load_error: Exception | None = None
    attempts = (True,) if _local_files_only() else (True, False)
    for local_files_only in attempts:
        try:
            processor = AutoImageProcessor.from_pretrained(
                model_name,
                revision=revision,
                local_files_only=local_files_only,
                use_fast=False,
            )
            model = AutoModel.from_pretrained(
                model_name,
                revision=revision,
                local_files_only=local_files_only,
            )
            model.eval()
            return cast(_EmbeddingProcessor, processor), cast(_EmbeddingModel, model)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            load_error = exc
    assert load_error is not None
    raise LocalVisualQAError(
        "local_identity:model_load_failed:"
        f"{type(load_error).__name__}:{str(load_error)[:240]}"
    ) from load_error


def _neutral_subject_crop(
    image: Image.Image,
    *,
    head_ratio: float,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    try:
        import numpy as np
    except ImportError as exc:
        raise LocalVisualQAError("local_identity:numpy_unavailable") from exc

    rgb = image.convert("RGB")
    pixels = np.asarray(rgb).astype(np.int16)
    height, width = pixels.shape[:2]
    border_width = max(2, min(8, width // 20, height // 20))
    border = np.concatenate(
        [
            pixels[:border_width].reshape(-1, 3),
            pixels[-border_width:].reshape(-1, 3),
            pixels[:, :border_width].reshape(-1, 3),
            pixels[:, -border_width:].reshape(-1, 3),
        ]
    )
    background = np.median(border, axis=0)
    mask = np.linalg.norm(pixels - background, axis=2) > 32
    rows, columns = np.where(mask)
    if len(columns) < 100:
        subject_box = (0, 0, width, height)
    else:
        left = int(columns.min())
        right = int(columns.max() + 1)
        top = int(rows.min())
        bottom = int(rows.max() + 1)
        horizontal_padding = int((right - left) * 0.05)
        vertical_padding = int((bottom - top) * 0.03)
        subject_box = (
            max(0, left - horizontal_padding),
            max(0, top - vertical_padding),
            min(width, right + horizontal_padding),
            min(height, bottom + vertical_padding),
        )
    left, top, right, bottom = subject_box
    crop_bottom = min(bottom, top + max(1, int((bottom - top) * head_ratio)))
    return rgb.crop((left, top, right, crop_bottom)), subject_box


def _box_iou(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> float:
    intersection_left = max(left[0], right[0])
    intersection_top = max(left[1], right[1])
    intersection_right = min(left[2], right[2])
    intersection_bottom = min(left[3], right[3])
    intersection = max(0, intersection_right - intersection_left) * max(
        0, intersection_bottom - intersection_top
    )
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _face_candidate_boxes(
    image: Image.Image,
) -> tuple[tuple[int, int, int, int], ...]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise LocalVisualQAError("local_identity:opencv_unavailable") from exc

    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    minimum_face = max(40, round(min(image.size) * 0.04))
    detected: list[tuple[int, int, int, int]] = []
    for cascade_name in (
        "haarcascade_frontalface_default.xml",
        "haarcascade_frontalface_alt2.xml",
        "haarcascade_profileface.xml",
    ):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_name)
        if cascade.empty():
            continue
        boxes = cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=4,
            minSize=(minimum_face, minimum_face),
        )
        detected.extend(
            (int(x), int(y), int(x + width), int(y + height))
            for x, y, width, height in boxes
        )

    deduplicated: list[tuple[int, int, int, int]] = []
    for box in sorted(
        detected,
        key=lambda item: (item[2] - item[0]) * (item[3] - item[1]),
        reverse=True,
    ):
        if all(_box_iou(box, existing) < 0.55 for existing in deduplicated):
            deduplicated.append(box)
        if len(deduplicated) >= 12:
            break
    return tuple(deduplicated)


def detect_local_face_boxes(
    image: Image.Image,
) -> tuple[tuple[int, int, int, int], ...]:
    """Return bounded face candidates for downstream local quality gates."""

    return _face_candidate_boxes(image)


def _expanded_face_crop(
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> Image.Image:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    return image.crop(
        (
            max(0, left - round(width * 0.35)),
            max(0, top - round(height * 0.45)),
            min(image.width, right + round(width * 0.35)),
            min(image.height, bottom + round(height * 0.55)),
        )
    )


def _primary_reference_face(
    image: Image.Image,
) -> tuple[Image.Image, tuple[int, int, int, int]] | None:
    boxes = _face_candidate_boxes(image)
    if not boxes:
        return None
    center_x = image.width / 2
    center_y = image.height / 2

    def priority(box: tuple[int, int, int, int]) -> float:
        width = box[2] - box[0]
        height = box[3] - box[1]
        box_center_x = (box[0] + box[2]) / 2
        box_center_y = (box[1] + box[3]) / 2
        distance = abs(box_center_x - center_x) / max(1, image.width) + abs(
            box_center_y - center_y
        ) / max(1, image.height)
        return (width * height) / (1.0 + distance)

    selected = max(boxes, key=priority)
    return _expanded_face_crop(image, selected), selected


def _bounded_identity_margin_env(name: str, default: float) -> float:
    try:
        configured = float(os.getenv(name, str(default)))
    except ValueError:
        configured = default
    return max(-0.5, min(0.5, configured))


def _calibrated_identity_score(
    *,
    face_similarity: float,
    face_threshold: float,
    similarity_margin: float | None,
    margin_threshold: float,
) -> float:
    def component(value: float, threshold: float, ceiling: float) -> float:
        if value < threshold:
            return max(0.0, min(79.0, (value / max(0.001, threshold)) * 79.0))
        return min(
            100.0,
            80.0 + ((value - threshold) / max(0.001, ceiling - threshold)) * 20.0,
        )

    face_score = component(face_similarity, face_threshold, 1.0)
    if similarity_margin is None:
        return round(face_score, 1)
    margin_score = component(similarity_margin, margin_threshold, 0.5)
    return round(min(face_score, margin_score), 1)


def evaluate_local_narrative_identity(
    *,
    reference_paths: Sequence[Path],
    candidate_path: Path,
    character_id: str,
    negative_reference_paths: Sequence[Path] = (),
    reference_boxes_override: Sequence[tuple[int, int, int, int]] = (),
    candidate_boxes_override: Sequence[tuple[int, int, int, int]] = (),
    restrict_candidate_boxes: bool = False,
    model_name: str = DEFAULT_LOCAL_IDENTITY_MODEL,
) -> LocalNarrativeIdentityAssessment:
    """Match a scene face to a canonical multi-view identity prototype."""

    positive_crops: list[Image.Image] = []
    reference_boxes: list[tuple[int, int, int, int]] = []
    for reference_index, reference_path in enumerate(reference_paths[:6]):
        reference = _load_rgb_image(reference_path)
        if reference_index == 0 and reference_boxes_override:
            for box in reference_boxes_override[:6]:
                left, top, right, bottom = (int(value) for value in box)
                bounded = (
                    max(0, min(reference.width - 1, left)),
                    max(0, min(reference.height - 1, top)),
                    max(1, min(reference.width, right)),
                    max(1, min(reference.height, bottom)),
                )
                if bounded[2] - bounded[0] >= 24 and bounded[3] - bounded[1] >= 24:
                    positive_crops.append(_expanded_face_crop(reference, bounded))
                    reference_boxes.append(bounded)
            continue
        selected = _primary_reference_face(reference)
        if selected is not None:
            crop, box = selected
            positive_crops.append(crop)
            reference_boxes.append(box)
    if not positive_crops:
        raise LocalVisualQAError("local_identity:reference_face_not_detected")

    negative_crops: list[Image.Image] = []
    for negative_path in negative_reference_paths[:12]:
        negative = _load_rgb_image(negative_path)
        selected = _primary_reference_face(negative)
        if selected is not None:
            negative_crops.append(selected[0])

    candidate = _load_rgb_image(candidate_path)
    candidate_boxes: list[tuple[int, int, int, int]] = []
    for box in candidate_boxes_override[:25]:
        left, top, right, bottom = (int(value) for value in box)
        bounded = (
            max(0, min(candidate.width - 1, left)),
            max(0, min(candidate.height - 1, top)),
            max(1, min(candidate.width, right)),
            max(1, min(candidate.height, bottom)),
        )
        if (
            bounded[2] - bounded[0] >= 24
            and bounded[3] - bounded[1] >= 24
            and all(_box_iou(bounded, existing) < 0.75 for existing in candidate_boxes)
        ):
            candidate_boxes.append(bounded)
    if not restrict_candidate_boxes:
        for box in _face_candidate_boxes(candidate):
            if all(_box_iou(box, existing) < 0.75 for existing in candidate_boxes):
                candidate_boxes.append(box)
    if not candidate_boxes:
        raise LocalVisualQAError("local_identity:candidate_face_not_detected")
    candidate_crops = [_expanded_face_crop(candidate, box) for box in candidate_boxes]

    processor, model = _load_local_identity_model(
        model_name,
        DEFAULT_LOCAL_IDENTITY_REVISION,
    )
    try:
        import torch

        inputs = processor(
            images=[*positive_crops, *negative_crops, *candidate_crops],
            return_tensors="pt",
        )
        with torch.inference_mode():
            outputs = model(**inputs)
        embeddings = torch.nn.functional.normalize(
            outputs.last_hidden_state[:, 0],
            dim=-1,
        )
        positive_count = len(positive_crops)
        negative_count = len(negative_crops)
        positive_prototype = torch.nn.functional.normalize(
            embeddings[:positive_count].mean(dim=0),
            dim=0,
        )
        negative_embeddings = embeddings[
            positive_count : positive_count + negative_count
        ]
        candidate_embeddings = embeddings[positive_count + negative_count :]
        positive_similarities = candidate_embeddings @ positive_prototype
        selected_index = int(positive_similarities.argmax().item())
        face_similarity = float(positive_similarities[selected_index].item())
        closest_negative_similarity = (
            float(
                (negative_embeddings @ candidate_embeddings[selected_index])
                .max()
                .item()
            )
            if negative_count
            else None
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_identity:narrative_inference_failed:{type(exc).__name__}:"
            f"{str(exc)[:240]}"
        ) from exc

    face_threshold = _bounded_similarity_env(
        "LOCAL_NARRATIVE_IDENTITY_MIN_SIMILARITY",
        0.65,
    )
    margin_threshold = _bounded_identity_margin_env(
        "LOCAL_NARRATIVE_IDENTITY_MIN_MARGIN",
        -0.12,
    )
    similarity_margin = (
        face_similarity - closest_negative_similarity
        if closest_negative_similarity is not None
        else None
    )
    issues = []
    if face_similarity < face_threshold:
        issues.append("identity_face_similarity_below_threshold")
    if similarity_margin is not None and similarity_margin < margin_threshold:
        issues.append("identity_contrastive_margin_below_threshold")
    accepted = not issues
    score = _calibrated_identity_score(
        face_similarity=face_similarity,
        face_threshold=face_threshold,
        similarity_margin=similarity_margin,
        margin_threshold=margin_threshold,
    )
    return LocalNarrativeIdentityAssessment(
        character_id=character_id,
        score=score,
        accepted=accepted,
        face_similarity=round(face_similarity, 4),
        closest_negative_similarity=(
            round(closest_negative_similarity, 4)
            if closest_negative_similarity is not None
            else None
        ),
        similarity_margin=(
            round(similarity_margin, 4) if similarity_margin is not None else None
        ),
        face_threshold=face_threshold,
        margin_threshold=margin_threshold,
        reference_boxes=tuple(reference_boxes),
        candidate_box=tuple(candidate_boxes[selected_index]),
        issues=tuple(issues),
        model_name=model_name,
    )


def _bounded_similarity_env(name: str, default: float) -> float:
    try:
        configured = float(os.getenv(name, str(default)))
    except ValueError:
        configured = default
    return max(0.55, min(0.98, configured))


def _identity_similarity_threshold(view_id: str) -> float:
    defaults = {
        "profile": 0.65,
        "three_quarter": 0.75,
        "full_body": 0.68,
        "expression_neutral": 0.84,
        "expression_warm": 0.88,
        "expression_concerned": 0.84,
    }
    default = defaults.get(view_id, 0.88)
    specific_name = f"LOCAL_CAST_IDENTITY_{view_id.upper()}_MIN_SIMILARITY"
    global_value = os.getenv("LOCAL_CAST_IDENTITY_MIN_SIMILARITY")
    if specific_name not in os.environ and global_value is not None:
        return _bounded_similarity_env("LOCAL_CAST_IDENTITY_MIN_SIMILARITY", default)
    return _bounded_similarity_env(specific_name, default)


def _identity_composition_threshold(view_id: str) -> float | None:
    defaults: dict[str, float | None] = {
        "profile": 0.65,
        "three_quarter": 0.80,
        "full_body": None,
        "expression_neutral": 0.90,
        "expression_warm": 0.90,
        "expression_concerned": 0.90,
    }
    default = defaults.get(view_id, 0.82)
    if default is None:
        return None
    name = f"LOCAL_CAST_IDENTITY_{view_id.upper()}_COMPOSITION_MIN_SIMILARITY"
    return _bounded_similarity_env(name, default)


def evaluate_local_cast_reference_identity(
    *,
    reference_path: Path,
    candidate_path: Path,
    view_id: str,
    model_name: str = DEFAULT_LOCAL_IDENTITY_MODEL,
) -> LocalCastIdentityAssessment:
    """Compare neutral character references with deterministic DINOv2 embeddings."""

    reference = _load_rgb_image(reference_path)
    candidate = _load_rgb_image(candidate_path)
    reference_face = (
        _primary_reference_face(reference) if view_id == "full_body" else None
    )
    candidate_face = (
        _primary_reference_face(candidate) if view_id == "full_body" else None
    )
    if reference_face is not None and candidate_face is not None:
        reference_crop, reference_box = reference_face
        candidate_crop, candidate_box = candidate_face
    else:
        candidate_head_ratio = 0.32 if view_id == "full_body" else 0.62
        reference_crop, reference_box = _neutral_subject_crop(
            reference,
            head_ratio=0.52,
        )
        candidate_crop, candidate_box = _neutral_subject_crop(
            candidate,
            head_ratio=candidate_head_ratio,
        )
    processor, model = _load_local_identity_model(
        model_name,
        DEFAULT_LOCAL_IDENTITY_REVISION,
    )
    try:
        import torch

        inputs = processor(
            images=[reference_crop, candidate_crop, reference, candidate],
            return_tensors="pt",
        )
        with torch.inference_mode():
            outputs = model(**inputs)
        embeddings = cast(_TensorLike, outputs.last_hidden_state)[:, 0]
        normalized = torch.nn.functional.normalize(embeddings, dim=-1)
        crop_similarity = float((normalized[0] * normalized[1]).sum().item())
        composition_similarity = float((normalized[2] * normalized[3]).sum().item())
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise LocalVisualQAError(
            f"local_identity:inference_failed:{type(exc).__name__}:{str(exc)[:240]}"
        ) from exc

    crop_threshold = _identity_similarity_threshold(view_id)
    composition_threshold = _identity_composition_threshold(view_id)
    accepted = crop_similarity >= crop_threshold and (
        composition_threshold is None or composition_similarity >= composition_threshold
    )
    weighted_similarity = (
        crop_similarity
        if composition_threshold is None
        else (crop_similarity * 0.75) + (composition_similarity * 0.25)
    )
    return LocalCastIdentityAssessment(
        score=round(max(0.0, min(1.0, weighted_similarity)) * 100, 1),
        accepted=accepted,
        crop_similarity=round(crop_similarity, 4),
        composition_similarity=round(composition_similarity, 4),
        crop_threshold=crop_threshold,
        composition_threshold=composition_threshold,
        reference_box=reference_box,
        candidate_box=candidate_box,
        model_name=model_name,
    )


@lru_cache(maxsize=2)
def _load_local_age_model(
    model_name: str,
    revision: str,
) -> tuple[_ImageProcessor, _ImageClassifierModel]:
    try:
        from transformers import ViTForImageClassification, ViTImageProcessor
    except ImportError as exc:
        raise LocalVisualQAError("local_age:sdk_unavailable") from exc

    try:
        processor = ViTImageProcessor.from_pretrained(
            model_name,
            revision=revision,
            local_files_only=_local_files_only(),
        )
        model = ViTForImageClassification.from_pretrained(
            model_name,
            revision=revision,
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
    images: Sequence[Image.Image],
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
                *({"type": "image"} for _image in images),
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
            images=list(images),
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


def _normalize_confirmation_answer(
    response: str,
) -> LocalVisualAnswerValue | None:
    match = re.fullmatch(
        r"\s*(yes|no|uncertain)\s*[.!]?\s*",
        response.strip().lower(),
    )
    if not match:
        return None
    return cast(LocalVisualAnswerValue, match.group(1))


def _evaluate_visual_criteria_batch(
    *,
    processor: _Processor,
    model: _Model,
    images: Sequence[Image.Image],
    criteria: Sequence[LocalVisualCriterion],
    context: str,
) -> list[LocalVisualAnswer]:
    numbered_questions = "\n".join(
        f"{index}. {criterion.question}"
        for index, criterion in enumerate(criteria, start=1)
    )
    response = _run_local_visual_prompt(
        processor=processor,
        model=model,
        images=images,
        prompt=(
            f"{context} Evaluate every numbered criterion independently. "
            "Return exactly one answer per line using only '<number>: yes', "
            "'<number>: no', or '<number>: uncertain'. Do not omit any number.\n"
            f"{numbered_questions}"
        ),
        max_new_tokens=min(192, max(48, len(criteria) * 8)),
    )
    indexed_answers = {
        int(match.group(1)): cast(LocalVisualAnswerValue, match.group(2).lower())
        for match in re.finditer(
            r"(?mi)^\s*(\d{1,2})\s*[:.)-]\s*(yes|no|uncertain)\b",
            response,
        )
    }
    answers: list[LocalVisualAnswer] = []
    for index, criterion in enumerate(criteria, start=1):
        answer = indexed_answers.get(index)
        raw_response = response[:240]
        requires_confirmation = bool(
            answer is not None and criterion.critical and answer != criterion.expected
        )
        if answer is None or requires_confirmation:
            fallback_response = _run_local_visual_prompt(
                processor=processor,
                model=model,
                images=images,
                prompt=(
                    f"{context} Re-check this criterion independently. "
                    "Answer only yes, no, or uncertain. "
                    f"{criterion.question}"
                ),
                max_new_tokens=8,
            )
            if requires_confirmation:
                confirmed_answer = _normalize_confirmation_answer(fallback_response)
                if confirmed_answer is not None:
                    answer = confirmed_answer
            else:
                answer = _normalize_binary_answer(fallback_response)
            raw_response = fallback_response[:120]
        answers.append(
            LocalVisualAnswer(
                criterion=criterion,
                answer=answer,
                raw_response=raw_response,
            )
        )
    return answers


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
    revision = _model_revision(
        model_name=model_name,
        env_name="LOCAL_VISION_QA_REVISION",
        default_model=DEFAULT_LOCAL_VISION_QA_MODEL,
        default_revision=DEFAULT_LOCAL_VISION_QA_REVISION,
    )
    processor, model = _load_local_vision_model(
        model_name,
        revision,
        _local_longest_edge(),
    )
    return _run_local_visual_prompt(
        processor=processor,
        model=model,
        images=[image],
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
    revision = _model_revision(
        model_name=model_name,
        env_name="LOCAL_VISION_QA_REVISION",
        default_model=DEFAULT_LOCAL_VISION_QA_MODEL,
        default_revision=DEFAULT_LOCAL_VISION_QA_REVISION,
    )
    processor, model = _load_local_vision_model(
        model_name,
        revision,
        _local_longest_edge(),
    )
    return _evaluate_visual_criteria_batch(
        processor=processor,
        model=model,
        images=[image],
        criteria=bounded_criteria,
        context="Inspect the full image carefully.",
    )


def classify_local_small_animal(
    *,
    image_path: Path,
    model_name: str = DEFAULT_LOCAL_VISION_QA_MODEL,
) -> LocalSmallAnimalLabel:
    """Classify one visible small animal with mutually exclusive labels."""

    image = _load_rgb_image(image_path)
    revision = _model_revision(
        model_name=model_name,
        env_name="LOCAL_VISION_QA_REVISION",
        default_model=DEFAULT_LOCAL_VISION_QA_MODEL,
        default_revision=DEFAULT_LOCAL_VISION_QA_REVISION,
    )
    processor, model = _load_local_vision_model(
        model_name,
        revision,
        _local_longest_edge(),
    )
    response = _run_local_visual_prompt(
        processor=processor,
        model=model,
        images=[image],
        prompt=(
            "Identify the single small animal visible in the image. Answer with "
            "exactly one word from: mouse, cat, dog, rabbit, other, none."
        ),
        max_new_tokens=8,
    )
    match = re.search(
        r"\b(mouse|cat|kitten|dog|rabbit|bunny|other|none)\b",
        response.strip().lower(),
    )
    if not match:
        raise LocalVisualQAError("local_vlm:invalid_small_animal_label")
    label = match.group(1)
    if label == "kitten":
        label = "cat"
    elif label == "bunny":
        label = "rabbit"
    return cast(LocalSmallAnimalLabel, label)


def reconcile_exclusive_small_animal_answers(
    answers: Sequence[LocalVisualAnswer],
    label: LocalSmallAnimalLabel,
) -> list[LocalVisualAnswer]:
    """Replace contradictory binary animal checks with one exclusive classification."""

    detected_by_code = {
        "hero_mouse_missing_or_wrong": label == "mouse",
        "forbidden_cat": label == "cat",
        "forbidden_dog": label == "dog",
        "forbidden_rabbit": label == "rabbit",
    }
    reconciled: list[LocalVisualAnswer] = []
    for answer in answers:
        detected = detected_by_code.get(answer.criterion.code)
        if detected is None:
            reconciled.append(answer)
            continue
        reconciled.append(
            LocalVisualAnswer(
                criterion=answer.criterion,
                answer="yes" if detected else "no",
                raw_response=f"exclusive_small_animal_classifier:{label}",
            )
        )
    return reconciled


def evaluate_local_character_identity(
    *,
    reference_path: Path,
    candidate_path: Path,
    character_id: str,
    character_name: str,
    identity_prompt: str,
    model_name: str = DEFAULT_LOCAL_VISION_QA_MODEL,
) -> LocalIdentityAssessment:
    """Compare an approved reference with a scene frame without external transfer."""

    reference = _load_rgb_image(reference_path)
    candidate = _load_rgb_image(candidate_path)
    revision = _model_revision(
        model_name=model_name,
        env_name="LOCAL_VISION_QA_REVISION",
        default_model=DEFAULT_LOCAL_VISION_QA_MODEL,
        default_revision=DEFAULT_LOCAL_VISION_QA_REVISION,
    )
    processor, model = _load_local_vision_model(
        model_name,
        revision,
        _local_longest_edge(),
    )
    criteria = (
        LocalVisualCriterion(
            code=f"identity_face_{character_id}",
            question=(
                f"Image 1 is the approved reference for {character_name}; Image 2 is a story "
                "frame. Ignoring pose, expression, camera and lighting, is the same unmistakable "
                "fictional character present in Image 2 with matching face shape and defining "
                "facial features?"
            ),
            expected="yes",
            weight=4.0,
            critical=True,
        ),
        LocalVisualCriterion(
            code=f"identity_age_kind_{character_id}",
            question=(
                f"Does {character_name} in Image 2 preserve the same age group, gender or animal "
                f"kind as Image 1 and this identity contract: {identity_prompt[:320]}?"
            ),
            expected="yes",
            weight=3.0,
            critical=True,
        ),
        LocalVisualCriterion(
            code=f"identity_hair_{character_id}",
            question=(
                f"Does {character_name} in Image 2 preserve the reference hair design and color, "
                "or the exact coat pattern and color for an animal character?"
            ),
            expected="yes",
            weight=2.0,
            critical=True,
        ),
        LocalVisualCriterion(
            code=f"identity_wardrobe_{character_id}",
            question=(
                f"Does {character_name} in Image 2 preserve the canonical wardrobe, colors and "
                "era-specific clothing from Image 1 and the identity contract, or correctly remain "
                "without clothing when the character is an animal?"
            ),
            expected="yes",
            weight=2.0,
            critical=True,
        ),
        LocalVisualCriterion(
            code=f"identity_silhouette_{character_id}",
            question=(
                f"Does {character_name} in Image 2 preserve the reference body proportions, "
                "height category and recognizable silhouette while allowing a different pose?"
            ),
            expected="yes",
            weight=2.0,
            critical=True,
        ),
        LocalVisualCriterion(
            code=f"identity_unique_{character_id}",
            question=(
                f"Is exactly one {character_name} visible in Image 2, without a duplicate or a "
                "different person or animal replacing the approved reference?"
            ),
            expected="yes",
            weight=3.0,
            critical=True,
        ),
    )
    answers = _evaluate_visual_criteria_batch(
        processor=processor,
        model=model,
        images=[reference, candidate],
        criteria=criteria,
        context=(
            "Compare both images carefully. Image 1 is the approved identity reference "
            "and Image 2 is the candidate scene."
        ),
    )
    total_weight = sum(answer.criterion.weight for answer in answers)
    earned_weight = sum(
        (
            answer.criterion.weight
            if answer.matched
            else answer.criterion.weight * 0.5 if answer.answer == "uncertain" else 0.0
        )
        for answer in answers
    )
    score = round((earned_weight / total_weight) * 100, 1)
    return LocalIdentityAssessment(
        character_id=character_id,
        score=score,
        accepted=score >= 88 and all(answer.matched for answer in answers),
        answers=tuple(answers),
        model_name=model_name,
    )


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
    revision = _model_revision(
        model_name=model_name,
        env_name="LOCAL_AGE_QA_REVISION",
        default_model=DEFAULT_LOCAL_AGE_QA_MODEL,
        default_revision=DEFAULT_LOCAL_AGE_QA_REVISION,
    )
    processor, model = _load_local_age_model(model_name, revision)
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
