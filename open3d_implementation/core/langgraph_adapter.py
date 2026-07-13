"""
LangGraph Adapter for Open3D Implementation
Integrates LangGraph workflows with Open3D visualization
"""

import ast
import base64
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, TypedDict

import requests


class Open3DAgentState(TypedDict, total=False):
    """State for Open3D Agent workflow"""

    messages: List[str]
    current_step: str
    scene_data: Dict[str, Any]
    generated_content: Dict[str, Any]
    # Campos adicionais necessários
    story_text: str
    session_id: str
    input_type: str
    max_scenes: int
    image_style: str
    image_quality_preset: str
    visual_bible: Dict[str, Any]
    enhanced_multimodal_input_asset: Dict[str, Any]
    cinematic_prompt: str
    scenes: List[Dict[str, Any]]
    scenes_count: int
    scene_images: List[Dict[str, Any]]
    images_count: int
    audio_files: List[Dict[str, Any]]
    audio_count: int
    video_path: str
    video_size: int
    generation_method: str
    status: str
    runpod_jobs: List[Dict[str, Any]]
    quality_metrics: Dict[str, Any]
    cost_estimate: Dict[str, Any]


IMAGE_STYLE_PRESETS: Dict[str, Dict[str, str]] = {
    "comic_storybook": {
        "label": "Comic storybook",
        "prompt": (
            "premium comic storybook animation, original family-friendly illustrated characters, "
            "expressive clean faces with large readable eyes, bold readable silhouettes, "
            "hand-inked comic linework, painted storybook backgrounds, warm theatrical lighting, "
            "consistent character identity across a single narrative film frame, "
            "high-end animated feature concept art, "
            "clear emotional acting, no brand imitation, no copyrighted character likeness"
        ),
    },
    "cinematic_realism": {
        "label": "Cinematic realism",
        "prompt": (
            "premium cinematic realism, historically accurate production design, "
            "natural human proportions, expressive but believable face, soft film grain, "
            "ARRI Alexa look, 35mm lens, controlled depth of field"
        ),
    },
    "storybook_animation": {
        "label": "Storybook animation",
        "prompt": (
            "premium storybook animation, family feature film look, handcrafted character design, "
            "soft expressive faces, elegant shapes, painterly backgrounds, warm whimsical lighting"
        ),
    },
    "editorial_black_white": {
        "label": "Editorial black and white",
        "prompt": (
            "editorial black and white cinema, silver gelatin tonal range, high contrast, "
            "classic portrait composition, refined film still, precise lighting"
        ),
    },
    "watercolor_illustration": {
        "label": "Watercolor illustration",
        "prompt": (
            "premium watercolor book illustration, delicate paper texture, transparent washes, "
            "controlled linework, charming character proportions, illustrated historical setting"
        ),
    },
    "anime_cinematic": {
        "label": "Anime cinematic",
        "prompt": (
            "cinematic anime film still, elegant character design, detailed background art, "
            "clean facial structure, soft rim light, premium animation composition"
        ),
    },
}

DEFAULT_IMAGE_STYLE = "comic_storybook"

IMAGE_QUALITY_PRESETS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "width": 768,
        "height": 1024,
        "steps": 28,
        "cfg": 5.0,
        "sampler_name": "euler_ancestral",
        "scheduler": "normal",
    },
    "high": {
        "width": 832,
        "height": 1216,
        "steps": 35,
        "cfg": 5.0,
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
    },
    "turbo": {
        "width": 832,
        "height": 1216,
        "steps": 8,
        "cfg": 2.0,
        "sampler_name": "euler_ancestral",
        "scheduler": "normal",
    },
}

IMAGE_NEGATIVE_PROMPT = (
    "low quality, worst quality, blurry, distorted, deformed, bad anatomy, malformed face, "
    "asymmetrical eyes, crossed eyes, broken nose, melted facial features, extra fingers, "
    "missing fingers, fused hands, extra limbs, long neck, dislocated neck, cropped head, "
    "out of frame, duplicate person, duplicate girl, duplicate child, duplicate face, twins, clones, "
    "multiple versions of the same character, repeated character, doll face, plastic skin, uncanny, "
    "second Alice, extra Victorian girl, extra young woman, replacing a male professor with a girl, "
    "princess costume, fantasy ball gown, blue princess dress, adult Alice, dog when the story asks for cats, "
    "unrequested rabbit, unrequested bunny, unrequested white rabbit, kitten beside the lap when the prompt says in lap, "
    "oversaturated grass, random modern clothing, incorrect era clothing, text, letters, words, captions, "
    "subtitles, title card, fake typography, poster layout, book page layout, page border, decorative frame, "
    "watermark, logo, signature, artist mark, UI overlay, label, sign, banner, credits, "
    "character sheet, model sheet, reference sheet, turnaround sheet, expression sheet, pose sheet, "
    "concept art grid, costume design grid, multiple panels, split screen, tiled layout, lineup, "
    "many versions of the same character, multiple poses of the same character, plain beige character sheet background, "
    "anthropomorphic mouse, mouse wearing clothes, mouse holding teacup, mouse as main character, giant mouse, "
    "human-sized mouse, mascot mouse, mouse portrait"
)

IMAGE_NEGATIVE_CORE = (
    "low quality, worst quality, blurry, distorted, deformed, bad anatomy, malformed face, "
    "extra fingers, fused hands, extra limbs, duplicate character, duplicate face, cropped head, "
    "text, captions, watermark, logo, signature, multiple panels, split screen, character sheet, "
    "adult Alice, fantasy ball gown, wrong era clothing, anthropomorphic mouse, mouse wearing clothes, "
    "mouse as main character, giant mouse, mascot mouse"
)


def _resolve_image_style(style_key: str | None) -> Dict[str, str]:
    return IMAGE_STYLE_PRESETS.get(
        style_key or DEFAULT_IMAGE_STYLE, IMAGE_STYLE_PRESETS[DEFAULT_IMAGE_STYLE]
    )


def _resolve_quality_preset(preset_key: str | None) -> Dict[str, Any]:
    return IMAGE_QUALITY_PRESETS.get(
        preset_key or "high", IMAGE_QUALITY_PRESETS["high"]
    )


def _resolve_comfyui_checkpoint(style_key: str | None) -> str:
    style_specific_key = (
        f"COMFYUI_CHECKPOINT_{(style_key or DEFAULT_IMAGE_STYLE).upper()}"
    )
    return (
        os.getenv(style_specific_key)
        or os.getenv("COMFYUI_DEFAULT_CHECKPOINT")
        or "ai-film-semantic-juggernaut-xl.safetensors"
    )


def _cancel_runpod_job(endpoint_id: str, api_key: str, job_id: str) -> None:
    if not endpoint_id or not api_key or not job_id:
        return
    try:
        import requests

        headers = {"Authorization": f"Bearer {api_key}"}
        requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/cancel/{job_id}",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"⚠️ Não foi possível cancelar job RunPod {job_id}: {exc}")


def _write_fallback_scene_image(
    image_path: str,
    scene: Dict[str, Any],
    style_label: str,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont

        width, height = 1280, 720
        img = Image.new("RGB", (width, height), (18, 20, 24))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            shade = int(18 + (y / height) * 38)
            draw.line((0, y, width, y), fill=(shade, shade + 3, shade + 8))

        try:
            font_title = ImageFont.truetype("Arial.ttf", 52)
            font_body = ImageFont.truetype("Arial.ttf", 30)
        except OSError:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        title = f"Cena {scene.get('scene_id', '')}".strip()
        prompt = str(scene.get("prompt") or scene.get("description") or "")[:220]
        lines = [prompt[i : i + 58] for i in range(0, len(prompt), 58)][:4]

        draw.rectangle(
            (72, 72, width - 72, height - 72), outline=(220, 176, 92), width=3
        )
        draw.text((112, 118), title, fill=(242, 205, 128), font=font_title)
        draw.text((112, 190), style_label, fill=(180, 190, 205), font=font_body)
        y = 280
        for line in lines:
            draw.text((112, y), line, fill=(232, 234, 238), font=font_body)
            y += 44

        os.makedirs(os.path.dirname(image_path) or ".", exist_ok=True)
        img.save(image_path, "PNG")
    except (OSError, ValueError, ImportError) as exc:
        print(f"⚠️ Falha ao criar fallback PNG real: {exc}")
        raise


def _scene_seed(session_id: str, style_key: str, scene_id: Any) -> int:
    seed_source = f"{session_id}:{style_key}:{scene_id}"
    digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 2_147_483_647


def _story_has_any(story_text: str, terms: List[str]) -> bool:
    lowered = story_text.lower()
    return any(term in lowered for term in terms)


def _text_has_any(text: str, terms: List[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _text_has_phrase(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text.lower()))


def _text_has_any_phrase(text: str, terms: List[str]) -> bool:
    return any(_text_has_phrase(text, term) for term in terms)


def _story_excerpt_around(
    story_text: str,
    terms: List[str],
    *,
    radius: int = 520,
) -> str:
    lowered = story_text.lower()
    positions = [lowered.find(term.lower()) for term in terms]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return story_text[: radius * 2].strip()
    center = min(positions)
    start = max(0, center - radius)
    end = min(len(story_text), center + radius)
    return story_text[start:end].strip()


def _canonical_story_scenes(
    story_text: str,
    style_key: str,
    max_scenes: int,
) -> List[Dict[str, Any]]:
    style = _resolve_image_style(style_key)
    anchors: List[Dict[str, Any]] = []

    if _story_has_any(story_text, ["formigueiro", "formigas", "anthill", "ants"]):
        excerpt = _story_excerpt_around(
            story_text,
            ["formigueiro", "formigas", "anthill", "ants"],
        )
        anchors.append(
            {
                "scene_id": len(anchors) + 1,
                "description": (
                    "Alice está no jardim da universidade, de bruços ou ajoelhada junto "
                    "às raízes de uma faia antiga, observando um pequeno formigueiro."
                ),
                "prompt": (
                    f"{style['prompt']}. Alice, uma menina vitoriana de aproximadamente "
                    "10 anos, cabelo castanho e vestido marfim modesto, observa de perto "
                    "um pequeno formigueiro na grama junto às raízes de uma grande faia "
                    "antiga no jardim da universidade. Enquadramento vertical 9:16, "
                    "luz natural suave, sem gatos visíveis."
                ),
                "duration": 7,
                "composition_notes": (
                    "ground-level observational shot at the beech roots; anthill in the foreground, "
                    "Alice low to the ground, university garden architecture may sit softly in the distance"
                ),
                "source_excerpt": excerpt,
                "must_include": [
                    "Alice approximately 10 years old",
                    "modest ivory-white Victorian day dress",
                    "giant ancient beech tree roots",
                    "small anthill in the grass",
                    "university garden",
                ],
                "must_not_include": [
                    "cat",
                    "kitten",
                    "dog",
                    "rabbit",
                    "modern elements",
                    "duplicate Alice",
                ],
                "camera_motion": "slow cinematic push-in toward Alice and the anthill",
            }
        )

    if _story_has_any(
        story_text,
        [
            "açucareiro",
            "acucareiro",
            "ratinho",
            "rato branco",
            "sugar bowl",
            "white mouse",
        ],
    ):
        excerpt = _story_excerpt_around(
            story_text,
            [
                "açucareiro",
                "acucareiro",
                "ratinho",
                "rato branco",
                "sugar bowl",
                "white mouse",
            ],
        )
        anchors.append(
            {
                "scene_id": len(anchors) + 1,
                "description": (
                    "Na sala de jantar vitoriana, Ludovico revela o truque do açucareiro: "
                    "um pequeno ratinho branco surge do açucareiro sobre a mesa de chá, "
                    "enquanto Alice observa maravilhada."
                ),
                "prompt": (
                    f"{style['prompt']}. Interior vitoriano em mesa de chá: Ludovico, "
                    "um professor adulto alto e magro, levanta a tampa de um açucareiro "
                    "de prata ou porcelana sobre a mesa; um pequeno ratinho branco está "
                    "visivelmente saindo do açucareiro. Alice, a mesma menina vitoriana "
                    "de vestido marfim, observa maravilhada. Composição medium-wide: "
                    "açucareiro central totalmente visível, ratinho claramente visível, "
                    "rostos, mãos e troncos de Alice e Ludovico no quadro sem corte agressivo. "
                    "Enquadramento vertical 9:16, luz quente de janela, sem moedas, sem "
                    "guardanapo como objeto principal."
                ),
                "duration": 8,
                "composition_notes": (
                    "interior tea-table two-shot; sugar bowl central in the lower third, "
                    "Alice and Ludovico leaning in from opposite sides with hands visible"
                ),
                "source_excerpt": excerpt,
                "must_include": [
                    "Alice approximately 10 years old",
                    "adult male Ludovico mathematics professor",
                    "Victorian tea table",
                    "fully visible sugar bowl with open lid",
                    "small white mouse emerging from the sugar bowl",
                    "Alice and Ludovico upper bodies and hands visible",
                ],
                "must_not_include": [
                    "coin trick",
                    "handkerchief trick as the main object",
                    "empty sugar bowl",
                    "cat",
                    "kitten",
                    "dog",
                    "duplicate Alice",
                    "modern elements",
                ],
                "camera_motion": "gentle push-in toward the sugar bowl and white mouse",
            }
        )

    if _story_has_any(
        story_text,
        ["toca", "coelho", "rabbit hole", "white rabbit"],
    ):
        excerpt = _story_excerpt_around(
            story_text,
            ["toca", "coelho", "rabbit hole", "white rabbit"],
        )
        anchors.append(
            {
                "scene_id": len(anchors) + 1,
                "description": (
                    "Alice encontra uma toca funda no barranco do jardim e percebe que "
                    "ela pertence a um coelho que acabou de entrar, criando o chamado "
                    "visual para a aventura."
                ),
                "prompt": (
                    f"{style['prompt']}. Alice, a mesma menina vitoriana em vestido "
                    "marfim, ajoelha-se junto a uma toca escura e profunda no barranco "
                    "gramado entre raízes. A abertura da toca é clara e central na cena; "
                    "um pequeno coelho pode estar parcialmente visível entrando na toca, "
                    "sem gatos. Enquadramento vertical 9:16, jardim verde, luz natural."
                ),
                "duration": 7,
                "composition_notes": (
                    "distinct from the anthill scene: wilder grassy embankment away from the beech trunk "
                    "and university facade, wider side three-quarter profile, rabbit hole dominant in the slope, "
                    "Alice at a different body angle; do not copy the tree-root composition from scene 1"
                ),
                "source_excerpt": excerpt,
                "must_include": [
                    "Alice approximately 10 years old",
                    "modest ivory-white Victorian day dress",
                    "dark rabbit hole in a grassy embankment",
                    "garden roots and grass",
                ],
                "must_not_include": [
                    "large beech trunk dominating the frame",
                    "anthill",
                    "university building facade",
                    "cat",
                    "kitten",
                    "dog",
                    "duplicate Alice",
                    "modern elements",
                ],
                "camera_motion": "slow push-in toward Alice and the rabbit hole",
            }
        )

    return anchors[:max_scenes]


def _merge_canonical_scenes(
    scenes: List[Dict[str, Any]],
    story_text: str,
    style_key: str,
    max_scenes: int,
) -> List[Dict[str, Any]]:
    canonical = _canonical_story_scenes(story_text, style_key, max_scenes)
    if not canonical:
        return scenes

    merged = canonical[:]
    for scene in scenes:
        if len(merged) >= max_scenes:
            break
        description = str(scene.get("description") or "")
        prompt = str(scene.get("prompt") or "")
        candidate_text = f"{description} {prompt}".lower()
        if any(
            _text_has_any(candidate_text, [str(item).lower()])
            for canonical_scene in canonical
            for item in canonical_scene.get("must_include", [])
            if item
        ):
            continue
        merged.append({**scene, "scene_id": len(merged) + 1})

    return [
        {
            **scene,
            "scene_id": index,
            "camera_motion": scene.get("camera_motion")
            or _motion_plan({"scene_id": index})["description"],
        }
        for index, scene in enumerate(merged[:max_scenes], 1)
    ]


def _scene_text(scene: Dict[str, Any]) -> str:
    must_include = " ".join(str(item) for item in scene.get("must_include", []) if item)
    must_not_include = " ".join(
        str(item) for item in scene.get("must_not_include", []) if item
    )
    return " ".join(
        [
            str(scene.get("description") or ""),
            str(scene.get("prompt") or ""),
            must_include,
            must_not_include,
        ]
    ).lower()


def _scene_positive_text(scene: Dict[str, Any]) -> str:
    must_include = " ".join(str(item) for item in scene.get("must_include", []) if item)
    return " ".join(
        [
            str(scene.get("description") or ""),
            str(scene.get("prompt") or ""),
            must_include,
        ]
    ).lower()


def _scene_visual_object_text(scene: Dict[str, Any]) -> str:
    must_include = " ".join(str(item) for item in scene.get("must_include", []) if item)
    return must_include.lower()


def _hero_object_requirements(scene: Dict[str, Any]) -> List[Dict[str, str]]:
    must_include = " ".join(str(item) for item in scene.get("must_include", []) if item)
    # Use only the author's scene intent and explicit required objects. Generated
    # prompts contain negative examples such as "no coin trick", which must not
    # become false-positive hero-object requirements.
    scene_text = " ".join(
        [
            str(scene.get("description") or ""),
            must_include,
        ]
    ).lower()
    hero_objects: List[Dict[str, str]] = []

    if _text_has_any_phrase(scene_text, ["formigueiro", "formigas", "anthill", "ants"]):
        hero_objects.append(
            {
                "name": "small anthill",
                "placement": "dominant foreground detail in grass or soil",
                "minimum_legibility": "individual mound texture and Alice looking at it must be readable without zooming",
                "camera": "low ground-level object-first composition",
            }
        )

    if _text_has_any_phrase(
        scene_text,
        [
            "açucareiro",
            "acucareiro",
            "ratinho",
            "rato branco",
            "sugar bowl",
            "white mouse",
        ],
    ):
        hero_objects.append(
            {
                "name": "white mouse emerging from open sugar bowl",
                "placement": "central lower-third hero object on the tea table",
                "minimum_legibility": "mouse head/body and open sugar bowl rim must be clearly recognizable at thumbnail size",
                "camera": "object-first medium close insert with Alice and Ludovico still visible as context",
            }
        )

    small_object_terms = [
        ("key", "key", "central visible story prop, not hidden in a hand"),
        ("chave", "key", "central visible story prop, not hidden in a hand"),
        ("letter", "letter", "readable physical letter shape, no fake text"),
        ("carta", "letter", "readable physical letter shape, no fake text"),
        ("watch", "watch", "foreground readable watch or pocket watch"),
        ("relógio", "watch", "foreground readable watch or pocket watch"),
        ("relogio", "watch", "foreground readable watch or pocket watch"),
        ("bottle", "bottle", "foreground readable small bottle"),
        ("frasco", "bottle", "foreground readable small bottle"),
        ("vial", "vial", "foreground readable small vial"),
        ("coin", "coin", "foreground readable coin"),
        ("moeda", "coin", "foreground readable coin"),
        ("card", "card", "foreground readable card shape, no fake text"),
        ("cartão", "card", "foreground readable card shape, no fake text"),
        ("cartao", "card", "foreground readable card shape, no fake text"),
    ]
    seen_names = {item["name"] for item in hero_objects}
    for term, name, placement in small_object_terms:
        if _text_has_phrase(scene_text, term) and name not in seen_names:
            hero_objects.append(
                {
                    "name": name,
                    "placement": placement,
                    "minimum_legibility": "the object must be large enough to identify in the full 9:16 frame without zooming",
                    "camera": "object-first insert or medium-close composition",
                }
            )
            seen_names.add(name)

    return hero_objects


def _build_scene_contract(scene: Dict[str, Any]) -> Dict[str, Any]:
    scene_text = _scene_positive_text(scene)
    visual_object_text = _scene_visual_object_text(scene)
    full_scene_text = _scene_text(scene)
    hero_objects = _hero_object_requirements(scene)
    required: List[str] = []
    forbidden: List[str] = [
        "visible text, typography, subtitles, captions, watermark, signature",
        "duplicate protagonist, cloned face, repeated same person",
        "unrelated extra people not explicitly required by this scene",
        "style switch, illustration/engraving/cartoon when cinematic realism is selected",
    ]
    character_rules: List[str] = []
    animal_rules: List[str] = []

    if "alice" in scene_text:
        required.append(
            "exactly one Alice, same approximately 10-year-old Victorian child across the whole film, brown hair, ivory modest day dress"
        )
        forbidden.extend(
            [
                "adult Alice",
                "toddler Alice",
                "preschool Alice",
                "much younger Alice than the reference",
                "older teenage Alice",
                "princess Alice",
                "blue fantasy gown",
                "second girl replacing Alice",
            ]
        )
        character_rules.append(
            "Alice must keep the same approximate age, face family, hair color, dress color and body proportions as the visual reference; do not make her younger in interior scenes."
        )

    if "ludovico" in scene_text or "professor" in scene_text:
        required.append(
            "one adult male mathematics professor only if the scene names Ludovico or professor"
        )
        character_rules.append(
            "The adult male may appear only when named by this scene; never replace him with a second Alice."
        )

    has_cat = any(
        term in scene_text
        for term in ("gato", "gatos", "gatinho", "gatinhos", "cat", "cats", "kitten")
    )
    visually_requires_cat = any(
        term in visual_object_text
        for term in ("gato", "gatos", "gatinho", "gatinhos", "cat", "cats", "kitten")
    )
    has_rabbit_hole = "toca de coelho" in scene_text or "rabbit hole" in scene_text
    has_rabbit = any(term in scene_text for term in ("coelho", "rabbit", "bunny"))

    if visually_requires_cat:
        required.append("cat or kitten only where this scene explicitly requests it")
        forbidden.extend(["dog", "rabbit replacing the cat", "plush toy animal"])
        animal_rules.append(
            "Any requested kitten must be visibly feline, correctly placed, and not replaced by another animal."
        )
    elif not has_cat:
        forbidden.extend(["unrequested cat", "unrequested kitten"])
    else:
        forbidden.extend(
            [
                "visible cat not requested by visual prompt",
                "visible kitten not requested by visual prompt",
            ]
        )
        animal_rules.append(
            "Narrative mentions of cats are context only; do not force a cat into the image unless prompt or must_include requires it."
        )

    if _text_has_any(scene_text, ["formigueiro", "formigas", "anthill", "ants"]):
        required.append("small anthill visibly present in grass or soil")
        forbidden.extend(["cat replacing the anthill", "kitten replacing the anthill"])
        animal_rules.append(
            "The anthill is the scene subject; do not replace it with a cat, rabbit, toy or generic garden pose."
        )

    if _text_has_any(
        scene_text,
        [
            "açucareiro",
            "acucareiro",
            "ratinho",
            "rato branco",
            "sugar bowl",
            "white mouse",
        ],
    ):
        required.append(
            "fully visible open sugar bowl containing or releasing a small white mouse"
        )
        required.append(
            "Alice and Ludovico visible together at the Victorian tea table"
        )
        forbidden.extend(
            [
                "coin trick replacing the mouse",
                "handkerchief trick replacing the mouse",
                "empty sugar bowl",
                "teapot replacing the sugar bowl",
                "mouse hidden outside the sugar bowl",
                "tight close-up that crops away the tea-table context",
            ]
        )
        animal_rules.append(
            "The white mouse emerging from the sugar bowl is mandatory and must be visible; do not substitute it with a coin, napkin, teapot or vague magic trick. Keep a medium-wide tea-table frame so Alice, Ludovico, the sugar bowl and the mouse are readable together."
        )

    if hero_objects:
        for hero_object in hero_objects:
            required.append(
                f"hero object legibility: {hero_object['name']} must be {hero_object['placement']}; {hero_object['minimum_legibility']}"
            )
        animal_rules.append(
            "Small required story objects are hero objects: if present but too small, hidden, blurred, cropped, or visually ambiguous, the image fails semantic QA."
        )

    if has_rabbit_hole:
        required.append(
            "dark rabbit hole opening in the ground, roots or grassy embankment"
        )
        forbidden.extend(["cat at the rabbit hole", "kitten at the rabbit hole"])
        animal_rules.append(
            "The rabbit hole is the required subject; do not add a cat/kitten unless the scene explicitly asks for one."
        )

    if has_rabbit and not has_rabbit_hole:
        animal_rules.append(
            "Rabbit elements may appear only if the scene explicitly names a rabbit."
        )
    elif not has_rabbit:
        forbidden.extend(["unrequested rabbit", "unrequested white rabbit", "bunny"])

    if "colo" in scene_text or "lap" in scene_text:
        required.append("requested kitten physically resting on Alice's lap")
        animal_rules.append(
            "If a kitten is in Alice's lap, it must touch the dress and sit on the lap, not beside her."
        )

    if "chá" in scene_text or "tea" in scene_text:
        required.append("Victorian tea table props explicitly described by the scene")
        forbidden.append("modern tea room objects or unrelated guests")

    return {
        "required": required or ["literal subject described by the scene"],
        "forbidden": sorted(set(forbidden)),
        "character_rules": character_rules,
        "animal_rules": animal_rules,
        "hero_objects": hero_objects,
        "raw_scene_terms": full_scene_text[:1200],
    }


def _scene_negative_prompt(scene: Dict[str, Any]) -> str:
    contract = _build_scene_contract(scene)
    scene_text = _scene_text(scene)
    color_forbidden: List[str] = []
    if _text_has_any_phrase(
        scene_text,
        ["ratinho branco", "white mouse", "small white mouse"],
    ):
        color_forbidden.extend(
            [
                "black mouse",
                "dark mouse",
                "grey mouse",
                "black animal blob",
                "mouse silhouette",
                "solid black mouse head",
                "teacup",
                "coffee cup",
                "cup handle",
                "saucer",
            ]
        )
    ordered_constraints: List[str] = []
    seen_constraints = set()
    for constraint in [*color_forbidden, *contract["forbidden"]]:
        normalized = str(constraint).strip()
        key = normalized.lower()
        if normalized and key not in seen_constraints:
            ordered_constraints.append(normalized)
            seen_constraints.add(key)
    scene_constraints = ", ".join(ordered_constraints[:18])
    return f"{scene_constraints}, {IMAGE_NEGATIVE_CORE}"[:1200]


def _hero_object_composition_directive(
    scene: Dict[str, Any],
    hero_objects: List[Dict[str, str]],
) -> str:
    if not hero_objects:
        return ""
    scene_text = _scene_text(scene)
    directives = [
        "Controlled hero-object composition: keep the required small object in the foreground as a prop, not as the protagonist.",
        "Use a staged story frame with foreground/midground/background separation: foreground hero prop, midground named characters, background environment.",
        "Do not replace named human characters with the small object; the object is evidence inside the scene.",
    ]
    if _text_has_any_phrase(
        scene_text,
        ["açucareiro", "acucareiro", "sugar bowl", "ratinho", "white mouse"],
    ):
        directives.extend(
            [
                "Foreground lower third: an open porcelain sugar bowl on the tea table, large enough to read, with only a tiny natural white mouse peeking from inside the bowl.",
                "The mouse is a small natural animal but visually legible: white head, ears, black eyes and snout peeking over the sugar bowl rim; no clothes, no bow tie, no jacket, no teacup, no standing pose, no portrait, no mascot expression.",
                "The sugar bowl is a lidded porcelain serving vessel with no cup handle, no teacup shape and no saucer; place its open lid beside or behind the bowl.",
                "Midground: Alice is a 10-year-old Victorian child in a modest ivory-white dress and Ludovico is one adult male professor; both must be visible behind or beside the sugar bowl.",
                "The sugar bowl remains the hero prop while Alice and Ludovico remain the story characters.",
            ]
        )
    return " ".join(directives)[:1200] + " "


def _build_visual_bible(story_text: str, style_key: str) -> Dict[str, Any]:
    style = _resolve_image_style(style_key)
    if style_key == "comic_storybook":
        continuity_style_rule = "keep the same premium comic/storybook animation medium; do not switch to photorealism, engraving, watercolor or flat anime"
        palette = "storybook warm neutrals, soft garden greens, ivory fabric, expressive cinematic color keys, no neon fantasy saturation"
        lens = "animation storyboard camera language, medium shot or medium-close shot, readable silhouette, clear acting pose, hero object visible"
        production_design = "late Victorian storybook world with simplified but intentional props, painted backgrounds, clean linework and readable staging"
    else:
        continuity_style_rule = "do not switch between watercolor, engraving, black-and-white, photorealism, anime or cartoon unless the selected style says so"
        palette = "muted woodland greens, warm ivory fabric, restrained cinematic contrast, no saturated fantasy colors"
        lens = "eye-level 35mm film frame, medium-wide composition, clear subject separation, no extreme close-up unless required by the scene"
        production_design = "late Victorian naturalism, real fabric texture, practical window or garden light, grounded historical props, no fantasy styling"
    protagonist = (
        "Alice, one curious approximately 10-year-old Victorian child, modest ivory-white day dress, brown hair, natural child proportions, consistent face family across scenes"
        if _story_has_any(story_text, ["alice"])
        else "the single main character named in the scene, consistent age, wardrobe and proportions"
    )
    protagonist_identity = (
        "same Alice in every scene: chestnut-brown shoulder-length hair parted softly near the center, "
        "oval child face, fair skin, restrained curious expression, modest ivory-white long-sleeved Victorian day dress, "
        "natural 10-year-old proportions; never adult, never toddler, never princess, never a second Alice"
        if _story_has_any(story_text, ["alice"])
        else "same named protagonist identity, age, wardrobe logic and face family across every scene"
    )
    animals = (
        "cats or kittens only when animals are requested; never dogs"
        if _story_has_any(
            story_text,
            ["gato", "gatos", "gatinho", "gatinhos", "cat", "cats", "kitten"],
        )
        else "only animals explicitly named by the story"
    )
    return {
        "style_key": style_key,
        "style_label": style["label"],
        "style_prompt": style["prompt"],
        "aspect_ratio": "portrait 9:16 vertical film frame",
        "visual_continuity": [
            "every scene belongs to the same film, same medium, same palette, same character design",
            continuity_style_rule,
            "same protagonist face, age, wardrobe logic and silhouette across every scene",
            "preserve the protagonist identity from the first accepted frame when a reference image is provided",
            "keep every frame storyboard-ready for later image-to-video animation",
        ],
        "protagonist": protagonist,
        "protagonist_identity": protagonist_identity,
        "animals": animals,
        "palette": palette,
        "lens": lens,
        "production_design": production_design,
        "forbidden": [
            "duplicate Alice or duplicate main character",
            "adult Alice",
            "toddler Alice, preschool Alice, much younger Alice, older teenage Alice",
            "princess gown, blue fantasy dress, ball gown, fashion pose",
            "dog when the story asks for cats or kittens",
            "unrelated extra people",
            "mixed art styles between scenes",
        ],
    }


def _visual_bible_text(visual_bible: Dict[str, Any]) -> str:
    return (
        f"FILM VISUAL BIBLE: style={visual_bible.get('style_label')}; "
        f"medium={visual_bible.get('style_prompt')}; "
        f"aspect={visual_bible.get('aspect_ratio')}; "
        f"protagonist={visual_bible.get('protagonist')}; "
        f"protagonist_identity={visual_bible.get('protagonist_identity')}; "
        f"animals={visual_bible.get('animals')}; "
        f"palette={visual_bible.get('palette')}; "
        f"lens={visual_bible.get('lens')}; "
        f"production_design={visual_bible.get('production_design')}; "
        f"continuity={'; '.join(visual_bible.get('visual_continuity', []))}; "
        f"forbidden={'; '.join(visual_bible.get('forbidden', []))}."
    )


def _character_reference_enabled() -> bool:
    return os.getenv(
        "IMAGE_CHARACTER_REFERENCE_ENABLED", "true"
    ).strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _build_character_reference_scene(visual_bible: Dict[str, Any]) -> Dict[str, Any]:
    style_prompt = str(visual_bible.get("style_prompt") or "")
    protagonist_identity = str(visual_bible.get("protagonist_identity") or "")
    return {
        "scene_id": "alice_reference",
        "description": (
            "Character reference sheet for Alice only, used to preserve identity across the film."
        ),
        "prompt": (
            f"{style_prompt}. Production reference image for Alice only: "
            f"{protagonist_identity}. One fully clothed Victorian child in a modest ivory-white "
            "long-sleeved day dress, neutral standing pose, three-quarter view, clean natural face, "
            "chestnut-brown shoulder-length hair, restrained curious expression, plain warm gray studio backdrop. "
            "No story action, no props, no other people, no text."
        ),
        "duration": 0,
        "composition_notes": (
            "technical character reference, neutral three-quarter pose, full body readable, plain backdrop"
        ),
        "source_excerpt": "",
        "must_include": [
            "one Alice approximately 10 years old",
            "chestnut-brown shoulder-length hair",
            "modest ivory-white long-sleeved Victorian day dress",
            "natural child proportions",
            "plain neutral backdrop",
        ],
        "must_not_include": [
            "second Alice",
            "adult Alice",
            "toddler Alice",
            "princess gown",
            "story action",
            "props",
            "text",
        ],
        "camera_motion": "static character reference",
    }


def _character_reference_accepted(image_metric: Dict[str, Any] | None) -> bool:
    if not image_metric:
        return False
    critical_failures = image_metric.get("semantic_critical_failures", [])
    if critical_failures:
        return False
    return (
        _safe_float(image_metric.get("quality_score")) >= 85
        or _safe_float(image_metric.get("semantic_score")) >= 80
    )


def _motion_plan(scene: Dict[str, Any]) -> Dict[str, str]:
    scene_id = _safe_int(scene.get("scene_id"), 1)
    profiles = [
        {
            "profile": "slow_push_in",
            "description": "slow cinematic push-in toward the main subject",
            "zoompan": "z='min(zoom+0.0012\\,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        },
        {
            "profile": "gentle_pan_right",
            "description": "gentle rightward pan with subtle push-in",
            "zoompan": "z='min(zoom+0.0009\\,1.06)':x='(iw-iw/zoom)*(on/(duration_frames))':y='ih/2-(ih/zoom/2)'",
        },
        {
            "profile": "gentle_pan_left",
            "description": "gentle leftward pan with subtle push-in",
            "zoompan": "z='min(zoom+0.0009\\,1.06)':x='(iw-iw/zoom)*(1-on/(duration_frames))':y='ih/2-(ih/zoom/2)'",
        },
    ]
    return profiles[(scene_id - 1) % len(profiles)]


def _shot_plan(scene: Dict[str, Any]) -> Dict[str, str]:
    scene_id = _safe_int(scene.get("scene_id"), 1)
    scene_text = _scene_positive_text(scene)
    if _text_has_any(scene_text, ["formigueiro", "anthill", "ants"]):
        return {
            "shot_type": "low observational medium shot",
            "camera_angle": "ground-level camera near the anthill looking slightly upward toward Alice",
            "blocking": "Alice crouches beside the beech roots, body angled diagonally, anthill dominant in foreground",
            "focal_priority": "anthill first, Alice second, university garden only as soft background context",
        }
    if _text_has_any(
        scene_text,
        ["açucareiro", "acucareiro", "ratinho", "white mouse", "sugar bowl"],
    ):
        return {
            "shot_type": "object-first medium-close insert inside a readable two-shot",
            "camera_angle": "eye-level table camera close enough that the sugar bowl and mouse are readable at thumbnail size",
            "blocking": "open sugar bowl and white mouse dominate the central lower third; Alice and Ludovico lean in from opposite sides as contextual faces and hands",
            "focal_priority": "white mouse and open sugar bowl first, Alice and Ludovico second, tea service third",
        }
    if _text_has_any(scene_text, ["toca", "rabbit hole", "coelho"]):
        return {
            "shot_type": "wider side-profile discovery shot",
            "camera_angle": "three-quarter side angle from the grassy embankment, not from tree roots",
            "blocking": "Alice kneels at the side of the dark opening, body profile different from the anthill scene",
            "focal_priority": "dark rabbit hole first, Alice profile second, wild embankment texture third",
        }
    return {
        "shot_type": f"distinct cinematic scene shot {scene_id}",
        "camera_angle": "eye-level 35mm perspective",
        "blocking": "clear subject blocking distinct from adjacent scenes",
        "focal_priority": "literal story subject first",
    }


def _ffmpeg_zoompan_filter(
    scene: Dict[str, Any], duration: float, fps: int = 30
) -> str:
    frames = max(1, int(duration * fps))
    plan = _motion_plan(scene)
    zoompan = plan["zoompan"].replace("duration_frames", str(frames))
    return (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan={zoompan}:d={frames}:s=1080x1920:fps={fps},"
        "format=yuv420p"
    )


def _scene_audio_duration(audio_files: List[Dict[str, Any]], scene_id: Any) -> float:
    for audio in audio_files:
        if audio.get("scene_id") != scene_id:
            continue
        audio_path = str(audio.get("audio_path", ""))
        if not audio_path:
            continue
        metrics = _probe_media_quality(audio_path, "audio")
        duration = _safe_float(metrics.get("duration_seconds"))
        if duration > 0:
            return duration
    return 0.0


def _build_image_prompt(
    scene: Dict[str, Any],
    style_key: str,
    visual_bible: Dict[str, Any] | None = None,
    retry_instruction: str = "",
) -> str:
    style = _resolve_image_style(style_key)
    base_prompt = str(scene.get("prompt") or scene.get("description") or "").strip()
    description = str(scene.get("description") or "").strip()
    composition_notes = str(scene.get("composition_notes") or "").strip()
    must_include = ", ".join(
        str(item) for item in scene.get("must_include", []) if item
    )
    must_not_include = ", ".join(
        str(item) for item in scene.get("must_not_include", []) if item
    )
    scene_text = _scene_text(scene)
    scene_contract = _build_scene_contract(scene)
    shot_plan = _shot_plan(scene)
    hero_objects = scene_contract.get("hero_objects", [])
    hero_object_clause = ""
    if hero_objects:
        hero_object_lines = [
            (
                f"{item['name']} => placement: {item['placement']}; "
                f"minimum legibility: {item['minimum_legibility']}; camera: {item['camera']}"
            )
            for item in hero_objects
        ]
        hero_object_clause = (
            "Hero object mandate: small required story objects must be staged as readable hero objects, "
            "not incidental background details. If the object would not be identifiable in a thumbnail, "
            "move the camera closer, enlarge the object in frame, simplify surrounding props, and keep it "
            f"in sharp focus. Required hero objects: {' | '.join(hero_object_lines)}. "
        )[:550]
    hero_object_composition = _hero_object_composition_directive(scene, hero_objects)
    contract_rules = []
    if "alice" in scene_text:
        contract_rules.append(
            "Show exactly one Alice: one Victorian child girl in a modest white day dress; no second girl, no adult woman, no duplicate Alice."
        )
    if "ludovico" in scene_text or "professor" in scene_text:
        contract_rules.append(
            "If Ludovico or the professor appears, he is one adult male mathematics professor, never a second girl or young woman."
        )
    if any(
        term in scene_text
        for term in ("gato", "gatos", "gatinho", "gatinhos", "cat", "kitten")
    ):
        contract_rules.append(
            "Cats/kittens must be visibly cats only; do not add dogs, rabbits, plush toys, or unrelated animals."
        )
    if "toca de coelho" in scene_text or "rabbit hole" in scene_text:
        contract_rules.append(
            "A rabbit hole may be visible as a dark opening in the ground or roots, but no rabbit or white rabbit should appear unless explicitly requested."
        )
    if "colo" in scene_text or "lap" in scene_text:
        contract_rules.append(
            "If the scene says the kitten is in Alice's lap, the kitten must physically rest on her lap, touching the dress, not standing beside her."
        )
    if "chá" in scene_text or "tea" in scene_text:
        contract_rules.append(
            "Tea-table scenes must show the requested tea table props and characters; do not replace named characters with another Victorian girl."
        )
    retry_clause = (
        f" Previous QA correction to apply strictly: {retry_instruction.strip()}."
        if retry_instruction.strip()
        else ""
    )
    required_text = "; ".join(scene_contract["required"])[:420]
    forbidden_text = "; ".join(scene_contract["forbidden"])[:260]
    character_rules_text = (
        "; ".join(scene_contract["character_rules"])
        or "keep the protagonist visually consistent with the film bible"
    )[:350]
    animal_rules_text = (
        "; ".join(scene_contract["animal_rules"])
        or "only show animals and objects explicitly requested by this scene"
    )[:350]
    compact_bible = (
        f"Film style: {visual_bible.get('style_label', style['label'])}; "
        f"medium: {style['prompt'][:180]}; "
        f"protagonist: {str(visual_bible.get('protagonist_identity', visual_bible.get('protagonist', 'consistent named protagonist')))[:180]}; "
        f"palette: {str(visual_bible.get('palette', ''))[:100]}."
    )[:560]
    return (
        f"Scene-first instruction: {description[:360]}. "
        f"Visual prompt: {base_prompt[:520]}. "
        f"Must include: {(must_include or 'the exact subject and objects described by the scene')[:360]}. "
        f"Must not include: {(must_not_include or 'duplicate characters, wrong animals, unrelated people, fantasy costumes')[:220]}. "
        f"Structured required elements: {required_text}. "
        f"Structured forbidden elements: {forbidden_text}. "
        f"Shot list: shot_type={shot_plan['shot_type']}; camera_angle={shot_plan['camera_angle']}; blocking={shot_plan['blocking']}; focal_priority={shot_plan['focal_priority']}. "
        f"Composition direction: {(composition_notes or 'distinct scene composition, same film identity')[:260]}. "
        f"{hero_object_clause}"
        f"{hero_object_composition}"
        f"{compact_bible} "
        "One finished narrative story frame, one continuous environment, one camera angle, one moment in time, one clear focal subject. "
        "Full-bleed clean film still, no typography, no border, no watermark. "
        "Do not repeat the same character; use natural hands, complete face, complete body. "
        f"Scene contract: {(' '.join(contract_rules) if contract_rules else 'Obey must_include and must_not_include literally.')[:500]} "
        f"Character continuity rules: {character_rules_text}. "
        f"Animal/object rules: {animal_rules_text}. "
        "Composition: vertical 9:16 frame, clear subject separation from background, rule of thirds, "
        "no random close-up unless explicitly requested, no isolated body parts."
        f"{retry_clause}"
    )


def _image_semantic_min_score() -> int:
    return _safe_int(os.getenv("IMAGE_SEMANTIC_MIN_SCORE", "88"), 88)


def _image_min_edge_sharpness() -> float:
    return max(
        8.0,
        min(60.0, _safe_float(os.getenv("IMAGE_MIN_EDGE_SHARPNESS", "24"), 24.0)),
    )


def _strict_image_semantic_gate() -> bool:
    return os.getenv("IMAGE_STRICT_SEMANTIC_GATE", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _image_generation_max_attempts() -> int:
    return max(1, min(3, _safe_int(os.getenv("IMAGE_GENERATION_MAX_ATTEMPTS", "3"), 3)))


def _visual_consistency_min_score() -> int:
    return max(
        80, min(98, _safe_int(os.getenv("IMAGE_CONSISTENCY_MIN_SCORE", "88"), 88))
    )


def _visual_consistency_soft_min_score() -> int:
    return max(
        75, min(90, _safe_int(os.getenv("IMAGE_CONSISTENCY_SOFT_MIN_SCORE", "75"), 75))
    )


def _select_consistency_repair_scene(
    scenes: List[Dict[str, Any]],
    visual_consistency: Dict[str, Any],
) -> Dict[str, Any] | None:
    if bool(visual_consistency.get("accepted")) or not scenes:
        return None

    issues = {str(issue) for issue in visual_consistency.get("issues", []) if issue}
    style_notes = str(visual_consistency.get("style_notes", "")).lower()
    if (
        "minor_facial_variance" in issues
        or "feições" in style_notes
        or "penteado" in style_notes
        or "face" in style_notes
        or "facial" in style_notes
    ):
        for scene in scenes:
            scene_text = _scene_positive_text(scene)
            if _text_has_any(scene_text, ["chá", "tea", "ludovico", "professor"]):
                return scene
        return scenes[1] if len(scenes) > 1 else scenes[-1]

    if "compositional_redundancy" in issues or "redundan" in style_notes:
        for scene in reversed(scenes):
            scene_text = _scene_positive_text(scene)
            if _text_has_any(scene_text, ["toca", "rabbit hole", "coelho"]):
                return scene
        return scenes[-1]

    return scenes[-1] if len(scenes) > 1 else None


def _replace_scene_asset(
    items: List[Dict[str, Any]],
    scene_id: Any,
    replacement: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [replacement if item.get("scene_id") == scene_id else item for item in items]


def _image_generation_provider() -> str:
    provider = os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui").strip().lower()
    if provider not in {"gemini", "comfyui"}:
        return "comfyui"
    return provider


def _gemini_image_model(quality_preset_key: str) -> str:
    if quality_preset_key == "balanced":
        return os.getenv(
            "GEMINI_IMAGE_FAST_MODEL",
            os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image"),
        )
    return os.getenv("GEMINI_IMAGE_QUALITY_MODEL", "gemini-3-pro-image")


def _gemini_image_usd_per_image(quality_preset_key: str) -> float:
    default = "0.04" if quality_preset_key == "balanced" else "0.12"
    return _safe_float(
        os.getenv("GEMINI_IMAGE_USD_PER_IMAGE", default), _safe_float(default)
    )


def _comfyui_controlnet_model() -> str:
    if _comfyui_control_image_mode() == "semantic_depth":
        return os.getenv(
            "COMFYUI_CONTROLNET_DEPTH_MODEL",
            "controlnet-depth-sdxl-1.0.safetensors",
        ).strip()
    return os.getenv(
        "COMFYUI_CONTROLNET_CANNY_MODEL",
        "controlnet-canny-sdxl-1.0.safetensors",
    ).strip()


def _comfyui_controlnet_available() -> bool:
    return bool(_comfyui_controlnet_model())


def _comfyui_ipadapter_enabled() -> bool:
    return os.getenv("COMFYUI_IPADAPTER_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _comfyui_ipadapter_weight() -> float:
    return max(
        0.35,
        min(0.90, _safe_float(os.getenv("COMFYUI_IPADAPTER_WEIGHT", "0.72"), 0.72)),
    )


def _comfyui_style_lora_name(style_key: str) -> str:
    key = f"COMFYUI_STYLE_LORA_{style_key.upper()}"
    return os.getenv(key, os.getenv("COMFYUI_STYLE_LORA", "")).strip()


def _comfyui_style_lora_strength() -> float:
    return max(
        0.0,
        min(1.0, _safe_float(os.getenv("COMFYUI_STYLE_LORA_STRENGTH", "0.65"), 0.65)),
    )


def _comfyui_control_image_mode() -> str:
    mode = os.getenv("COMFYUI_CONTROL_IMAGE_MODE", "semantic_depth").strip().lower()
    if mode not in {"semantic_depth", "semantic_hero", "source_edges"}:
        return "semantic_depth"
    return mode


def _comfyui_controlnet_strength() -> float:
    return max(
        0.1,
        min(
            1.0,
            _safe_float(os.getenv("COMFYUI_CONTROLNET_STRENGTH", "0.78"), 0.78),
        ),
    )


def _comfyui_inpaint_denoise() -> float:
    return max(
        0.65,
        min(0.95, _safe_float(os.getenv("COMFYUI_INPAINT_DENOISE", "0.85"), 0.85)),
    )


def _comfyui_refiner_enabled() -> bool:
    return os.getenv("COMFYUI_REFINER_ENABLED", "false").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _comfyui_refiner_scale() -> float:
    return max(
        1.0,
        min(1.5, _safe_float(os.getenv("COMFYUI_REFINER_SCALE", "1.25"), 1.25)),
    )


def _comfyui_refiner_denoise() -> float:
    return max(
        0.10,
        min(0.40, _safe_float(os.getenv("COMFYUI_REFINER_DENOISE", "0.18"), 0.18)),
    )


def _comfyui_refiner_steps() -> int:
    return max(
        6,
        min(18, _safe_int(os.getenv("COMFYUI_REFINER_STEPS", "6"), 6)),
    )


def _comfyui_refiner_checkpoint() -> str:
    return os.getenv(
        "COMFYUI_REFINER_CHECKPOINT",
        "ai-film-dreamshaper-xl-turbo-sfw.safetensors",
    ).strip()


def _draw_semantic_hero_control_image(
    scene: Dict[str, Any],
    width: int,
    height: int,
):
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)
    line = max(4, width // 120)
    thin = max(2, line // 2)
    white = (255, 255, 255)
    gray = (170, 170, 170)
    scene_text = _scene_text(scene)

    def ellipse(box, *, outline=white, width_px=line):
        draw.ellipse(tuple(int(v) for v in box), outline=outline, width=width_px)

    def line_xy(points, *, fill=white, width_px=line):
        draw.line([(int(x), int(y)) for x, y in points], fill=fill, width=width_px)

    def rect(box, *, outline=white, width_px=line):
        draw.rectangle(tuple(int(v) for v in box), outline=outline, width=width_px)

    if _text_has_any_phrase(
        scene_text,
        ["açucareiro", "acucareiro", "sugar bowl", "ratinho", "white mouse"],
    ):
        line_xy(
            [(width * 0.06, height * 0.76), (width * 0.94, height * 0.76)],
            fill=gray,
            width_px=thin,
        )
        bowl = (width * 0.22, height * 0.55, width * 0.74, height * 0.77)
        lid = (width * 0.34, height * 0.50, width * 0.62, height * 0.59)
        ellipse(bowl, width_px=line + 1)
        ellipse(lid, outline=gray, width_px=thin)
        mouse = (width * 0.44, height * 0.48, width * 0.56, height * 0.57)
        ellipse(mouse, width_px=thin)
        ellipse(
            (width * 0.43, height * 0.45, width * 0.47, height * 0.50), width_px=thin
        )
        ellipse(
            (width * 0.53, height * 0.45, width * 0.57, height * 0.50), width_px=thin
        )
        line_xy(
            [(width * 0.48, height * 0.57), (width * 0.41, height * 0.61)],
            width_px=thin,
        )
    elif _text_has_any_phrase(
        scene_text, ["formigueiro", "formigas", "anthill", "ants"]
    ):
        line_xy(
            [(width * 0.06, height * 0.76), (width * 0.94, height * 0.76)],
            fill=gray,
            width_px=thin,
        )
        mound = (width * 0.24, height * 0.62, width * 0.78, height * 0.88)
        ellipse(mound, width_px=line + 1)
        ellipse(
            (width * 0.42, height * 0.68, width * 0.58, height * 0.78),
            outline=gray,
            width_px=thin,
        )
        for idx in range(7):
            x = width * (0.31 + idx * 0.055)
            y = height * (0.61 + (idx % 3) * 0.035)
            ellipse((x, y, x + width * 0.025, y + width * 0.018), width_px=thin)
        ellipse(
            (width * 0.63, height * 0.25, width * 0.75, height * 0.37),
            outline=gray,
            width_px=thin,
        )
        line_xy(
            [
                (width * 0.69, height * 0.37),
                (width * 0.61, height * 0.56),
                (width * 0.77, height * 0.56),
            ],
            fill=gray,
            width_px=thin,
        )
    elif _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        line_xy(
            [(width * 0.06, height * 0.76), (width * 0.94, height * 0.76)],
            fill=gray,
            width_px=thin,
        )
        ellipse(
            (width * 0.20, height * 0.57, width * 0.80, height * 0.91),
            width_px=line + 1,
        )
        ellipse(
            (width * 0.32, height * 0.65, width * 0.68, height * 0.86),
            outline=gray,
            width_px=line,
        )
        ellipse(
            (width * 0.08, height * 0.27, width * 0.23, height * 0.41),
            outline=gray,
            width_px=thin,
        )
        line_xy(
            [
                (width * 0.15, height * 0.41),
                (width * 0.11, height * 0.63),
                (width * 0.29, height * 0.63),
            ],
            fill=gray,
            width_px=thin,
        )
    else:
        hero_names = " ".join(item["name"] for item in _hero_object_requirements(scene))
        if _text_has_any_phrase(hero_names, ["key"]):
            ellipse(
                (width * 0.34, height * 0.56, width * 0.49, height * 0.66),
                width_px=line,
            )
            line_xy([(width * 0.49, height * 0.61), (width * 0.72, height * 0.61)])
            line_xy([(width * 0.66, height * 0.61), (width * 0.66, height * 0.69)])
            line_xy([(width * 0.71, height * 0.61), (width * 0.71, height * 0.67)])
        elif _text_has_any_phrase(hero_names, ["letter", "card"]):
            rect(
                (width * 0.26, height * 0.54, width * 0.74, height * 0.78),
                width_px=line,
            )
            line_xy(
                [
                    (width * 0.26, height * 0.54),
                    (width * 0.50, height * 0.67),
                    (width * 0.74, height * 0.54),
                ]
            )
        else:
            rect(
                (width * 0.25, height * 0.55, width * 0.75, height * 0.80),
                width_px=line,
            )
            ellipse(
                (width * 0.43, height * 0.35, width * 0.57, height * 0.49),
                outline=gray,
                width_px=thin,
            )

    return image.filter(ImageFilter.GaussianBlur(radius=0.35))


def _draw_semantic_hero_depth_image(
    scene: Dict[str, Any],
    width: int,
    height: int,
):
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("L", (width, height), 24)
    draw = ImageDraw.Draw(image)
    scene_text = _scene_text(scene)
    draw.rectangle((0, int(height * 0.76), width, height), fill=72)

    def ellipse(box, fill):
        draw.ellipse(tuple(int(v) for v in box), fill=fill)

    if _text_has_any_phrase(
        scene_text,
        ["açucareiro", "acucareiro", "sugar bowl", "ratinho", "white mouse"],
    ):
        ellipse((width * 0.22, height * 0.55, width * 0.74, height * 0.77), 205)
        ellipse((width * 0.34, height * 0.47, width * 0.62, height * 0.55), 150)
        ellipse((width * 0.44, height * 0.47, width * 0.56, height * 0.58), 238)
        ellipse((width * 0.43, height * 0.44, width * 0.48, height * 0.50), 245)
        ellipse((width * 0.52, height * 0.44, width * 0.57, height * 0.50), 245)
    elif _text_has_any_phrase(
        scene_text, ["formigueiro", "formigas", "anthill", "ants"]
    ):
        ellipse((width * 0.24, height * 0.60, width * 0.78, height * 0.90), 190)
        ellipse((width * 0.42, height * 0.67, width * 0.58, height * 0.79), 90)
    elif _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        ellipse((width * 0.18, height * 0.55, width * 0.82, height * 0.94), 176)
        ellipse((width * 0.31, height * 0.64, width * 0.69, height * 0.88), 52)
    else:
        draw.rounded_rectangle(
            (
                int(width * 0.24),
                int(height * 0.48),
                int(width * 0.76),
                int(height * 0.84),
            ),
            radius=max(8, width // 24),
            fill=198,
        )

    return image.filter(ImageFilter.GaussianBlur(radius=max(1, width // 240))).convert(
        "RGB"
    )


def _encode_comfyui_control_image(
    source_image_path: str,
    *,
    image_name: str,
    width: int,
    height: int,
    scene: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    from io import BytesIO

    from PIL import Image, ImageFilter, ImageOps

    control_mode = _comfyui_control_image_mode()
    if scene and control_mode == "semantic_depth":
        control_image = _draw_semantic_hero_depth_image(scene, width, height)
    elif scene and control_mode == "semantic_hero":
        control_image = _draw_semantic_hero_control_image(scene, width, height)
    else:
        source_path = Path(source_image_path)
        if not source_path.exists():
            raise RuntimeError("control_image_missing")
        with Image.open(source_path) as source_image:
            control_image = (
                source_image.convert("L")
                .resize((width, height), Image.Resampling.LANCZOS)
                .filter(ImageFilter.FIND_EDGES)
            )
            control_image = ImageOps.autocontrast(control_image).convert("RGB")
    buffer = BytesIO()
    control_image.save(buffer, format="PNG", optimize=True)

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"name": image_name, "image": f"data:image/png;base64,{encoded}"}


def _encode_comfyui_reference_image(
    source_image_path: str,
    *,
    image_name: str,
) -> Dict[str, str]:
    from io import BytesIO

    from PIL import Image, ImageOps

    source_path = Path(source_image_path)
    if not source_path.exists():
        raise RuntimeError("ipadapter_reference_image_missing")
    with Image.open(source_path) as source_image:
        reference = ImageOps.fit(
            source_image.convert("RGB"),
            (1024, 1024),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.42),
        )
    buffer = BytesIO()
    reference.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"name": image_name, "image": f"data:image/png;base64,{encoded}"}


def _hero_object_focus_box(scene: Dict[str, Any]) -> tuple[float, float, float, float]:
    scene_text = _scene_text(scene)
    if _text_has_any_phrase(
        scene_text,
        ["açucareiro", "acucareiro", "sugar bowl", "ratinho", "white mouse"],
    ):
        return (0.16, 0.41, 0.80, 0.84)
    if _text_has_any_phrase(scene_text, ["formigueiro", "formigas", "anthill", "ants"]):
        return (0.16, 0.52, 0.84, 0.94)
    if _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        return (0.12, 0.48, 0.88, 0.96)
    return (0.20, 0.34, 0.80, 0.88)


def _hero_object_quality_box(
    scene: Dict[str, Any],
) -> tuple[float, float, float, float]:
    scene_text = _scene_text(scene)
    if _text_has_any_phrase(
        scene_text,
        ["açucareiro", "acucareiro", "sugar bowl", "ratinho", "white mouse"],
    ):
        return (0.28, 0.44, 0.76, 0.76)
    if _text_has_any_phrase(scene_text, ["formigueiro", "formigas", "anthill", "ants"]):
        return (0.24, 0.58, 0.80, 0.90)
    if _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        return (0.20, 0.56, 0.80, 0.90)
    return (0.28, 0.40, 0.72, 0.82)


def _encode_comfyui_inpaint_image(
    source_image_path: str,
    *,
    image_name: str,
    width: int,
    height: int,
    scene: Dict[str, Any],
) -> Dict[str, str]:
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFilter

    source_path = Path(source_image_path)
    if not source_path.exists():
        raise RuntimeError("inpaint_reference_image_missing")
    with Image.open(source_path) as source_image:
        inpaint_image = source_image.convert("RGB").resize(
            (width, height), Image.Resampling.LANCZOS
        )

    alpha = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(alpha)
    left, top, right, bottom = _hero_object_focus_box(scene)
    draw.rounded_rectangle(
        (
            int(width * left),
            int(height * top),
            int(width * right),
            int(height * bottom),
        ),
        radius=max(12, width // 18),
        fill=0,
    )
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius=max(6, width // 80)))
    inpaint_rgba = inpaint_image.convert("RGBA")
    inpaint_rgba.putalpha(alpha)

    buffer = BytesIO()
    inpaint_rgba.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"name": image_name, "image": f"data:image/png;base64,{encoded}"}


def _build_comfyui_workflow(
    directed_prompt: str,
    checkpoint_name: str,
    quality_preset: Dict[str, Any],
    scene_seed: int,
    scene_id: Any,
    negative_prompt: str | None = None,
    controlled_workflow: bool = False,
    controlnet_name: str | None = None,
    controlnet_strength: float | None = None,
    control_image_name: str | None = None,
    inpaint_image_name: str | None = None,
    refiner_enabled: bool | None = None,
    refiner_checkpoint_name: str | None = None,
    diagnostic_intermediate: bool = False,
    reference_image_name: str | None = None,
    ipadapter_enabled: bool = False,
    ipadapter_weight: float | None = None,
    style_lora_name: str | None = None,
    style_lora_strength: float | None = None,
) -> Dict[str, Any]:
    positive_node: List[Any] = ["1", 0]
    base_model_node: List[Any] = ["4", 0]
    base_clip_node: List[Any] = ["4", 1]
    workflow: Dict[str, Any] = {
        "1": {
            "inputs": {"text": directed_prompt, "clip": ["4", 1]},
            "class_type": "CLIPTextEncode",
        },
        "2": {
            "inputs": {
                "text": negative_prompt or IMAGE_NEGATIVE_PROMPT,
                "clip": ["4", 1],
            },
            "class_type": "CLIPTextEncode",
        },
        "3": {
            "inputs": {
                "seed": scene_seed,
                "steps": quality_preset["steps"],
                "cfg": quality_preset["cfg"],
                "sampler_name": quality_preset["sampler_name"],
                "scheduler": quality_preset["scheduler"],
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["1", 0],
                "negative": ["2", 0],
                "latent_image": ["5", 0],
            },
            "class_type": "KSampler",
        },
        "4": {
            "inputs": {"ckpt_name": checkpoint_name},
            "class_type": "CheckpointLoaderSimple",
        },
        "5": {
            "inputs": {
                "width": quality_preset["width"],
                "height": quality_preset["height"],
                "batch_size": 1,
            },
            "class_type": "EmptyLatentImage",
        },
        "6": {
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            "class_type": "VAEDecode",
        },
        "7": {
            "inputs": {
                "filename_prefix": f"scene_{scene_id}",
                "images": ["6", 0],
            },
            "class_type": "SaveImage",
        },
    }
    resolved_lora_name = (style_lora_name or "").strip()
    if resolved_lora_name:
        lora_strength = (
            _comfyui_style_lora_strength()
            if style_lora_strength is None
            else max(0.0, min(1.0, style_lora_strength))
        )
        workflow["23"] = {
            "inputs": {
                "model": ["4", 0],
                "clip": ["4", 1],
                "lora_name": resolved_lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
            },
            "class_type": "LoraLoader",
        }
        base_model_node = ["23", 0]
        base_clip_node = ["23", 1]
        workflow["1"]["inputs"]["clip"] = base_clip_node
        workflow["2"]["inputs"]["clip"] = base_clip_node

    if ipadapter_enabled and reference_image_name:
        workflow["20"] = {
            "inputs": {"image": reference_image_name},
            "class_type": "LoadImage",
        }
        workflow["21"] = {
            "inputs": {
                "model": base_model_node,
                "preset": "PLUS (high strength)",
            },
            "class_type": "IPAdapterUnifiedLoader",
        }
        workflow["22"] = {
            "inputs": {
                "model": ["21", 0],
                "ipadapter": ["21", 1],
                "image": ["20", 0],
                "weight": (
                    _comfyui_ipadapter_weight()
                    if ipadapter_weight is None
                    else max(0.35, min(0.90, ipadapter_weight))
                ),
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.75,
                "embeds_scaling": "V only",
            },
            "class_type": "IPAdapterAdvanced",
        }
        base_model_node = ["22", 0]

    workflow["3"]["inputs"]["model"] = base_model_node
    if controlled_workflow:
        resolved_controlnet = (controlnet_name or _comfyui_controlnet_model()).strip()
        if not resolved_controlnet:
            raise ValueError("comfyui_controlnet_model_missing")
        if control_image_name:
            workflow["8"] = {
                "inputs": {"image": control_image_name},
                "class_type": "LoadImage",
            }
        else:
            workflow["8"] = {
                "inputs": {
                    "width": quality_preset["width"],
                    "height": quality_preset["height"],
                    "batch_size": 1,
                    "color": 0,
                },
                "class_type": "EmptyImage",
            }
        workflow["9"] = {
            "inputs": {"control_net_name": resolved_controlnet},
            "class_type": "ControlNetLoader",
        }
        workflow["10"] = {
            "inputs": {
                "conditioning": ["1", 0],
                "control_net": ["9", 0],
                "image": ["8", 0],
                "strength": (
                    _comfyui_controlnet_strength()
                    if controlnet_strength is None
                    else controlnet_strength
                ),
            },
            "class_type": "ControlNetApply",
        }
        positive_node = ["10", 0]
        workflow["3"]["inputs"]["positive"] = positive_node

    if inpaint_image_name:
        workflow["11"] = {
            "inputs": {"image": inpaint_image_name},
            "class_type": "LoadImage",
        }
        workflow["12"] = {
            "inputs": {
                "pixels": ["11", 0],
                "vae": ["4", 2],
                "mask": ["11", 1],
                "grow_mask_by": 16,
            },
            "class_type": "VAEEncodeForInpaint",
        }
        workflow["3"]["inputs"]["latent_image"] = ["12", 0]
        workflow["3"]["inputs"]["denoise"] = _comfyui_inpaint_denoise()

    should_refine = (
        _comfyui_refiner_enabled() if refiner_enabled is None else refiner_enabled
    )
    if should_refine and controlled_workflow:
        if diagnostic_intermediate:
            workflow["18"] = {
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                "class_type": "VAEDecode",
            }
            workflow["19"] = {
                "inputs": {
                    "filename_prefix": f"scene_{scene_id}_base_inpaint",
                    "images": ["18", 0],
                },
                "class_type": "SaveImage",
            }
        workflow["13"] = {
            "inputs": {
                "samples": ["3", 0],
                "upscale_method": "bislerp",
                "scale_by": _comfyui_refiner_scale(),
            },
            "class_type": "LatentUpscaleBy",
        }
        refiner_model: List[Any] = ["4", 0]
        refiner_positive: List[Any] = positive_node
        refiner_negative: List[Any] = ["2", 0]
        resolved_refiner_checkpoint = (refiner_checkpoint_name or "").strip()
        if resolved_refiner_checkpoint:
            workflow["15"] = {
                "inputs": {"ckpt_name": resolved_refiner_checkpoint},
                "class_type": "CheckpointLoaderSimple",
            }
            workflow["17"] = {
                "inputs": {
                    "text": negative_prompt or IMAGE_NEGATIVE_PROMPT,
                    "clip": ["15", 1],
                },
                "class_type": "CLIPTextEncode",
            }
            refiner_model = ["15", 0]
            refiner_negative = ["17", 0]
            workflow["6"]["inputs"]["vae"] = ["15", 2]

        workflow["14"] = {
            "inputs": {
                "seed": scene_seed + 1,
                "steps": _comfyui_refiner_steps(),
                "cfg": 2.0 if resolved_refiner_checkpoint else quality_preset["cfg"],
                "sampler_name": (
                    "dpmpp_2m"
                    if resolved_refiner_checkpoint
                    else quality_preset["sampler_name"]
                ),
                "scheduler": (
                    "normal"
                    if resolved_refiner_checkpoint
                    else quality_preset["scheduler"]
                ),
                "denoise": _comfyui_refiner_denoise(),
                "model": refiner_model,
                "positive": refiner_positive,
                "negative": refiner_negative,
                "latent_image": ["13", 0],
            },
            "class_type": "KSampler",
        }
        workflow["6"]["inputs"]["samples"] = ["14", 0]
    return workflow


def _run_comfyui_image_attempt(
    *,
    scene: Dict[str, Any],
    image_path: str,
    directed_prompt: str,
    image_style: str,
    style_label: str,
    quality_preset_key: str,
    quality_preset: Dict[str, Any],
    checkpoint_name: str,
    scene_seed: int,
    visual_bible: Dict[str, Any],
    runpod_endpoint_id: str,
    runpod_api_key: str,
    runpod_gpu_usd_per_second: float,
    attempt: int,
    controlled_workflow: bool = False,
    control_image_path: str | None = None,
    reference_image_path: str | None = None,
) -> tuple[Dict[str, Any], Dict[str, Any] | None, Dict[str, Any] | None]:
    import base64
    import binascii
    import time

    import requests

    run_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/run"
    status_url_template = (
        f"https://api.runpod.ai/v2/{runpod_endpoint_id}/status/{{job_id}}"
    )
    headers = {"Authorization": f"Bearer {runpod_api_key}"}
    control_image_name = (
        f"control_scene_{scene['scene_id']}_attempt_{attempt}.png"
        if controlled_workflow and control_image_path
        else None
    )
    inpaint_image_name = (
        f"inpaint_scene_{scene['scene_id']}_attempt_{attempt}.png"
        if controlled_workflow and control_image_path
        else None
    )
    reference_image_name = (
        f"ipadapter_scene_{scene['scene_id']}_attempt_{attempt}.png"
        if reference_image_path and _comfyui_ipadapter_enabled()
        else None
    )
    refiner_enabled = bool(controlled_workflow and _comfyui_refiner_enabled())
    refiner_checkpoint = _comfyui_refiner_checkpoint() if refiner_enabled else ""
    input_images = []
    if control_image_name and control_image_path:
        input_images.append(
            _encode_comfyui_control_image(
                control_image_path,
                image_name=control_image_name,
                width=quality_preset["width"],
                height=quality_preset["height"],
                scene=scene,
            )
        )
        input_images.append(
            _encode_comfyui_inpaint_image(
                control_image_path,
                image_name=inpaint_image_name,
                width=quality_preset["width"],
                height=quality_preset["height"],
                scene=scene,
            )
        )
    if reference_image_name and reference_image_path:
        input_images.append(
            _encode_comfyui_reference_image(
                reference_image_path,
                image_name=reference_image_name,
            )
        )

    workflow = _build_comfyui_workflow(
        directed_prompt=directed_prompt,
        checkpoint_name=checkpoint_name,
        quality_preset=quality_preset,
        scene_seed=scene_seed,
        scene_id=scene["scene_id"],
        negative_prompt=_scene_negative_prompt(scene),
        controlled_workflow=controlled_workflow,
        control_image_name=control_image_name,
        inpaint_image_name=inpaint_image_name,
        refiner_enabled=refiner_enabled,
        refiner_checkpoint_name=refiner_checkpoint,
        reference_image_name=reference_image_name,
        ipadapter_enabled=bool(reference_image_name),
        style_lora_name=_comfyui_style_lora_name(image_style),
    )
    generation_method = (
        "comfyui_controlnet_inpaint_refiner"
        if controlled_workflow and refiner_enabled
        else "comfyui_controlnet_inpaint" if controlled_workflow else "comfyui"
    )
    controlnet_model = _comfyui_controlnet_model() if controlled_workflow else ""

    print(
        "📤 Enviando job para o endpoint RunPod Serverless "
        f"(cena {scene['scene_id']}, tentativa {attempt})..."
    )
    job_started_at = time.monotonic()
    job_monitor: Dict[str, Any] = {
        "scene_id": scene["scene_id"],
        "endpoint_id": runpod_endpoint_id,
        "job_id": None,
        "status": "SUBMITTED",
        "attempt": attempt,
        "style": image_style,
        "style_label": style_label,
        "quality_preset": quality_preset_key,
        "checkpoint": checkpoint_name,
        "seed": scene_seed,
        "width": quality_preset["width"],
        "height": quality_preset["height"],
        "output_width": round(
            quality_preset["width"]
            * (_comfyui_refiner_scale() if refiner_enabled else 1.0)
        ),
        "output_height": round(
            quality_preset["height"]
            * (_comfyui_refiner_scale() if refiner_enabled else 1.0)
        ),
        "generation_method": generation_method,
        "controlled_workflow": controlled_workflow,
        "controlnet_model": controlnet_model,
        "control_image": control_image_name or "",
        "inpaint_image": inpaint_image_name or "",
        "ipadapter_enabled": bool(reference_image_name),
        "ipadapter_reference_image": reference_image_name or "",
        "ipadapter_weight": (
            _comfyui_ipadapter_weight() if reference_image_name else 0.0
        ),
        "style_lora": _comfyui_style_lora_name(image_style),
        "inpaint_denoise": _comfyui_inpaint_denoise() if controlled_workflow else 1.0,
        "refiner_enabled": refiner_enabled,
        "refiner_checkpoint": refiner_checkpoint,
        "refiner_scale": _comfyui_refiner_scale() if refiner_enabled else 1.0,
        "refiner_denoise": _comfyui_refiner_denoise() if refiner_enabled else 0.0,
        "refiner_steps": _comfyui_refiner_steps() if refiner_enabled else 0,
        "elapsed_seconds": 0.0,
        "polls": [],
        "error": None,
        "image_path": None,
        "estimated_cost_usd": 0.0,
    }

    try:
        request_payload: Dict[str, Any] = {"input": {"workflow": workflow}}
        if input_images:
            request_payload["input"]["images"] = input_images
        response = requests.post(
            run_url,
            json=request_payload,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        job_monitor["status"] = "SUBMIT_FAILED"
        job_monitor["error"] = f"{type(exc).__name__}: {exc}"
        job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
        job_monitor["estimated_cost_usd"] = round(
            job_monitor["elapsed_seconds"] * runpod_gpu_usd_per_second,
            6,
        )
        return job_monitor, None, None

    if response.status_code != 200:
        job_monitor["status"] = "SUBMIT_FAILED"
        job_monitor["error"] = f"HTTP {response.status_code}: {response.text[:300]}"
        job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
        job_monitor["estimated_cost_usd"] = round(
            job_monitor["elapsed_seconds"] * runpod_gpu_usd_per_second,
            6,
        )
        return job_monitor, None, None

    job_id = response.json().get("id")
    job_monitor["job_id"] = job_id
    print(f"🆔 Job ID: {job_id}")

    max_wait = int(os.getenv("COMFYUI_RUNPOD_MAX_WAIT_SECONDS", "120"))
    wait_time = 0
    while wait_time < max_wait:
        time.sleep(3)
        wait_time += 3

        try:
            status_response = requests.get(
                status_url_template.format(job_id=job_id),
                headers=headers,
                timeout=10,
            )
        except requests.RequestException as exc:
            job_monitor["polls"].append(
                {
                    "status": f"POLL_FAILED:{type(exc).__name__}",
                    "wait_seconds": wait_time,
                }
            )
            continue

        if status_response.status_code != 200:
            print(f"⚠️ Erro ao consultar status: {status_response.status_code}")
            continue

        status_payload = status_response.json()
        job_status = status_payload.get("status")
        job_monitor["status"] = job_status
        job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
        job_monitor["polls"].append({"status": job_status, "wait_seconds": wait_time})

        if job_status == "COMPLETED":
            images = status_payload.get("output", {}).get("images", [])
            if not images:
                job_monitor["error"] = "completed_without_images"
                break

            image_b64 = images[0].get("data", "")
            try:
                with open(image_path, "wb") as output_file:
                    output_file.write(base64.b64decode(image_b64))
            except (OSError, ValueError, binascii.Error) as exc:
                job_monitor["error"] = f"decode_failed:{type(exc).__name__}"
                break

            if not (os.path.exists(image_path) and os.path.getsize(image_path) > 1000):
                job_monitor["error"] = "invalid_decoded_image"
                break

            image_record = {
                "scene_id": scene["scene_id"],
                "image_path": image_path,
                "prompt": directed_prompt,
                "base_prompt": scene["prompt"],
                "style": image_style,
                "quality_preset": quality_preset_key,
                "checkpoint": checkpoint_name,
                "seed": scene_seed,
                "duration": scene.get("duration", 6),
                "camera_motion": scene.get(
                    "camera_motion",
                    _motion_plan(scene)["description"],
                ),
                "runpod_job_id": job_id,
                "generation_method": generation_method,
                "controlled_workflow": controlled_workflow,
                "controlnet_model": controlnet_model,
                "control_image": control_image_name or "",
                "inpaint_image": inpaint_image_name or "",
                "refiner_enabled": refiner_enabled,
                "refiner_checkpoint": refiner_checkpoint,
            }
            job_monitor["image_path"] = image_path
            technical_metrics = _probe_image_quality(image_path, scene=scene)
            semantic_metrics = _evaluate_image_semantics(
                image_path,
                scene,
                directed_prompt,
                image_style,
                visual_bible,
            )
            combined_metrics = _combine_image_quality(
                technical_metrics,
                semantic_metrics,
            )
            image_metric = {
                "scene_id": scene["scene_id"],
                "generation_method": generation_method,
                "attempt": attempt,
                "style": image_style,
                "quality_preset": quality_preset_key,
                "checkpoint": checkpoint_name,
                "seed": scene_seed,
                "controlled_workflow": controlled_workflow,
                "controlnet_model": controlnet_model,
                "control_image": control_image_name or "",
                "inpaint_image": inpaint_image_name or "",
                "refiner_enabled": refiner_enabled,
                "refiner_checkpoint": refiner_checkpoint,
                **combined_metrics,
            }
            job_monitor["semantic_score"] = combined_metrics.get("semantic_score")
            job_monitor["quality_score"] = combined_metrics.get("quality_score")
            job_monitor["semantic_accepted"] = combined_metrics.get("semantic_accepted")
            job_monitor["quality_issues"] = combined_metrics.get("issues", [])
            job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
            job_monitor["estimated_cost_usd"] = round(
                job_monitor["elapsed_seconds"] * runpod_gpu_usd_per_second,
                6,
            )
            return job_monitor, image_record, image_metric

        if job_status in ("FAILED", "CANCELLED", "TIMED_OUT"):
            job_monitor["error"] = status_payload.get("error")
            break

        print(f"⏳ Status: {job_status} ({wait_time}s)")

    else:
        job_monitor["status"] = "LOCAL_TIMEOUT"
        job_monitor["error"] = f"timeout_after_{max_wait}s"
        if job_id:
            _cancel_runpod_job(runpod_endpoint_id, runpod_api_key, job_id)

    job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
    job_monitor["estimated_cost_usd"] = round(
        job_monitor["elapsed_seconds"] * runpod_gpu_usd_per_second,
        6,
    )
    return job_monitor, None, None


def _extract_gemini_image_bytes(response: Any) -> bytes | None:
    output_image = getattr(response, "output_image", None)
    if output_image is not None:
        data = getattr(output_image, "data", None)
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            import base64
            import binascii

            try:
                return base64.b64decode(data)
            except binascii.Error:
                return None

    generated_images = getattr(response, "generated_images", None) or getattr(
        response,
        "generatedImages",
        None,
    )
    if generated_images:
        first_image = generated_images[0]
        image = getattr(first_image, "image", None)
        image_bytes = getattr(image, "image_bytes", None) or getattr(
            image,
            "imageBytes",
            None,
        )
        if isinstance(image_bytes, bytes):
            return image_bytes

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None) or getattr(
                part,
                "inlineData",
                None,
            )
            if inline_data is None:
                continue
            data = getattr(inline_data, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                import base64
                import binascii

                try:
                    return base64.b64decode(data)
                except binascii.Error:
                    return None
    return None


def _run_gemini_image_attempt(
    *,
    scene: Dict[str, Any],
    image_path: str,
    directed_prompt: str,
    image_style: str,
    style_label: str,
    quality_preset_key: str,
    scene_seed: int,
    visual_bible: Dict[str, Any],
    attempt: int,
    reference_image_path: str | None = None,
) -> tuple[Dict[str, Any], Dict[str, Any] | None, Dict[str, Any] | None]:
    import time

    model_name = _gemini_image_model(quality_preset_key)
    job_started_at = time.monotonic()
    job_monitor: Dict[str, Any] = {
        "scene_id": scene["scene_id"],
        "provider": "gemini",
        "job_id": f"gemini:{scene['scene_id']}:{attempt}:{scene_seed}",
        "status": "SUBMITTED",
        "attempt": attempt,
        "style": image_style,
        "style_label": style_label,
        "quality_preset": quality_preset_key,
        "model": model_name,
        "seed": scene_seed,
        "elapsed_seconds": 0.0,
        "polls": [],
        "error": None,
        "image_path": None,
        "reference_image_path": reference_image_path,
        "estimated_cost_usd": _gemini_image_usd_per_image(quality_preset_key),
    }

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        job_monitor["status"] = "SUBMIT_FAILED"
        job_monitor["error"] = "missing_gemini_key"
        return job_monitor, None, None

    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        job_monitor["status"] = "SUBMIT_FAILED"
        job_monitor["error"] = f"missing_google_genai:{type(exc).__name__}"
        return job_monitor, None, None

    generation_prompt = (
        f"{directed_prompt}\n\n"
        f"Negative constraints: {_scene_negative_prompt(scene)}\n\n"
        "Output one portrait 9:16 cinematic image only. No text. "
        "If a reference image is provided, preserve only the protagonist identity, age, wardrobe logic, color palette, lens language and cinematic finish. "
        "Do not copy the reference image pose, camera angle, body angle, background, tree placement, room layout, foreground object or overall composition; each scene must have distinct blocking and scene geography."
    )

    try:
        client = genai.Client(api_key=api_key)
        contents: Any = generation_prompt
        if reference_image_path:
            reference_path = Path(reference_image_path)
            if reference_path.exists() and reference_path.stat().st_size > 1000:
                contents = [
                    generation_prompt,
                    "Reference image for identity and style continuity only. Do not copy pose, body angle, background, camera angle, foreground object or composition.",
                    types.Part.from_bytes(
                        data=reference_path.read_bytes(),
                        mime_type="image/png",
                    ),
                ]
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                responseModalities=["IMAGE"],
                imageConfig=types.ImageConfig(
                    aspectRatio="9:16",
                    imageSize="2K" if quality_preset_key == "high" else "1K",
                ),
            ),
        )
        image_bytes = _extract_gemini_image_bytes(response)
    except (
        TypeError,
        ValueError,
        errors.APIError,
        errors.ClientError,
        errors.ServerError,
        errors.UnknownApiResponseError,
    ) as exc:
        job_monitor["status"] = "FAILED"
        job_monitor["error"] = f"{type(exc).__name__}: {exc}"
        job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
        return job_monitor, None, None

    job_monitor["elapsed_seconds"] = round(time.monotonic() - job_started_at, 3)
    if image_bytes is None:
        job_monitor["status"] = "FAILED"
        job_monitor["error"] = "gemini_completed_without_image"
        return job_monitor, None, None

    try:
        with open(image_path, "wb") as output_file:
            output_file.write(image_bytes)
    except OSError as exc:
        job_monitor["status"] = "FAILED"
        job_monitor["error"] = f"write_failed:{type(exc).__name__}"
        return job_monitor, None, None

    if not (os.path.exists(image_path) and os.path.getsize(image_path) > 1000):
        job_monitor["status"] = "FAILED"
        job_monitor["error"] = "invalid_gemini_image"
        return job_monitor, None, None

    job_monitor["status"] = "COMPLETED"
    job_monitor["image_path"] = image_path
    image_record = {
        "scene_id": scene["scene_id"],
        "image_path": image_path,
        "prompt": directed_prompt,
        "base_prompt": scene["prompt"],
        "style": image_style,
        "quality_preset": quality_preset_key,
        "model": model_name,
        "seed": scene_seed,
        "duration": scene.get("duration", 6),
        "camera_motion": scene.get(
            "camera_motion",
            _motion_plan(scene)["description"],
        ),
        "runpod_job_id": None,
        "generation_method": "gemini_image",
    }
    technical_metrics = _probe_image_quality(image_path, scene=scene)
    semantic_metrics = _evaluate_image_semantics(
        image_path,
        scene,
        directed_prompt,
        image_style,
        visual_bible,
    )
    combined_metrics = _combine_image_quality(technical_metrics, semantic_metrics)
    image_metric = {
        "scene_id": scene["scene_id"],
        "generation_method": "gemini_image",
        "attempt": attempt,
        "style": image_style,
        "quality_preset": quality_preset_key,
        "model": model_name,
        "seed": scene_seed,
        **combined_metrics,
    }
    job_monitor["semantic_score"] = combined_metrics.get("semantic_score")
    job_monitor["quality_score"] = combined_metrics.get("quality_score")
    job_monitor["semantic_accepted"] = combined_metrics.get("semantic_accepted")
    job_monitor["quality_issues"] = combined_metrics.get("issues", [])
    return job_monitor, image_record, image_metric


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate for monitoring and cost approximation."""
    return max(1, len(text) // 4)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _runway_error_types(runway_module: Any) -> tuple[type[BaseException], ...]:
    candidates = (
        "APIError",
        "APIConnectionError",
        "APITimeoutError",
        "BadRequestError",
        "AuthenticationError",
        "PermissionDeniedError",
        "NotFoundError",
        "RateLimitError",
        "InternalServerError",
    )
    error_types: list[type[BaseException]] = []
    for name in candidates:
        value = getattr(runway_module, name, None)
        if isinstance(value, type) and issubclass(value, BaseException):
            error_types.append(value)
    return tuple(error_types)


def _runway_clip_duration(seconds: float) -> int:
    requested = _safe_float(os.getenv("RUNWAY_VIDEO_DURATION"), seconds)
    return 10 if requested > 5 else 5


def _build_runway_motion_prompt(scene_image: Dict[str, Any]) -> str:
    source_prompt = str(
        scene_image.get("base_prompt")
        or scene_image.get("prompt")
        or scene_image.get("description")
        or ""
    ).strip()
    camera_motion = str(scene_image.get("camera_motion") or "subtle cinematic push-in")
    prompt = (
        f"{source_prompt}\n\n"
        "Animate this exact frame as a premium cinematic story scene. "
        f"Camera motion: {camera_motion}. "
        "Preserve the same characters, wardrobe, faces, setting, composition, era, and art style. "
        "Use natural breathing, cloth movement, atmospheric motion, and gentle parallax only. "
        "No new characters, no identity drift, no morphing, no text, no logos, no captions."
    )
    return prompt[:950]


def _download_runway_output(url: str, clip_path: str) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    with open(clip_path, "wb") as output_file:
        output_file.write(response.content)


def _generate_runway_clip(
    scene_image: Dict[str, Any],
    clip_path: str,
    duration_seconds: float,
) -> tuple[Dict[str, Any], bool]:
    started_at = time.monotonic()
    scene_id = scene_image.get("scene_id")
    model = os.getenv("RUNWAY_MODEL", "gen4_turbo")
    ratio = os.getenv("RUNWAY_VIDEO_RATIO", "1280:720")
    duration = _runway_clip_duration(duration_seconds)
    api_key = os.getenv("RUNWAY_API_KEY", "").strip()
    usd_per_second = _safe_float(os.getenv("RUNWAY_USD_PER_SECOND"), 0.0)
    usd_per_clip = _safe_float(os.getenv("RUNWAY_USD_PER_CLIP"), 0.0)
    estimated_cost = usd_per_clip if usd_per_clip > 0 else duration * usd_per_second
    job_monitor: Dict[str, Any] = {
        "provider": "runway",
        "scene_id": scene_id,
        "job_id": None,
        "status": "skipped",
        "elapsed_seconds": 0,
        "estimated_cost_usd": round(estimated_cost, 6),
        "model": model,
        "duration_seconds": duration,
        "ratio": ratio,
        "output_path": clip_path,
        "error": "",
    }
    if not api_key:
        job_monitor["error"] = "runway_api_key_missing"
        return job_monitor, False

    image_path = str(scene_image.get("image_path", ""))
    if not image_path or not os.path.exists(image_path):
        job_monitor["error"] = "source_image_missing"
        return job_monitor, False

    try:
        runway_module = importlib.import_module("runwayml")
    except ImportError:
        job_monitor["error"] = "runway_sdk_missing"
        return job_monitor, False

    handled_errors = (
        AttributeError,
        TypeError,
        ValueError,
        OSError,
        requests.RequestException,
        RuntimeError,
    ) + _runway_error_types(runway_module)
    try:
        client_args: Dict[str, Any] = {"api_key": api_key}
        base_url = os.getenv("RUNWAY_BASE_URL", "").strip()
        if base_url:
            client_args["base_url"] = base_url
        client = getattr(runway_module, "RunwayML")(**client_args)

        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        task = client.image_to_video.create(
            model=model,
            prompt_image=f"data:image/png;base64,{encoded}",
            prompt_text=_build_runway_motion_prompt(scene_image),
            duration=duration,
            ratio=ratio,
        )
        task_id = str(getattr(task, "id", "") or getattr(task, "task_id", ""))
        job_monitor["job_id"] = task_id or None
        job_monitor["status"] = str(getattr(task, "status", "submitted")).lower()

        timeout_seconds = _safe_float(os.getenv("RUNWAY_VIDEO_TIMEOUT_SECONDS"), 900)
        poll_seconds = max(2.0, _safe_float(os.getenv("RUNWAY_VIDEO_POLL_SECONDS"), 5))
        terminal_success = {"succeeded", "success", "completed", "complete"}
        terminal_failure = {"failed", "failure", "cancelled", "canceled"}
        while time.monotonic() - started_at < timeout_seconds:
            time.sleep(poll_seconds)
            task = client.tasks.retrieve(task_id)
            status = str(getattr(task, "status", "")).lower()
            job_monitor["status"] = status or "unknown"
            if status in terminal_success:
                outputs = getattr(task, "output", None) or []
                if not outputs:
                    job_monitor["error"] = "runway_output_missing"
                    break
                _download_runway_output(str(outputs[0]), clip_path)
                media_quality = _probe_media_quality(clip_path, "video")
                job_monitor.update(
                    {
                        "status": "succeeded",
                        "elapsed_seconds": round(time.monotonic() - started_at, 2),
                        "quality_score": media_quality.get("quality_score", 0),
                        "quality_issues": media_quality.get("issues", []),
                    }
                )
                return job_monitor, bool(media_quality.get("valid"))
            if status in terminal_failure:
                job_monitor["error"] = f"runway_task_{status}"
                break
        else:
            job_monitor["error"] = "runway_timeout"
    except handled_errors as exc:
        job_monitor["error"] = f"runway_error:{type(exc).__name__}"

    job_monitor["elapsed_seconds"] = round(time.monotonic() - started_at, 2)
    return job_monitor, False


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")
    parsed = json.loads(match.group())
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON is not an object")
    return parsed


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", "")
    if text:
        return str(text)

    chunks: List[str] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", "")
            if part_text:
                chunks.append(str(part_text))
    if chunks:
        return "\n".join(chunks)
    return str(response)


def _semantic_qa_enabled() -> bool:
    return os.getenv("IMAGE_SEMANTIC_QA_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _evaluate_image_semantics(
    image_path: str,
    scene: Dict[str, Any],
    directed_prompt: str,
    style_key: str,
    visual_bible: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "semantic_score": 0,
        "semantic_qa_enabled": _semantic_qa_enabled(),
        "accepted": False,
        "issues": [],
        "retry_prompt": "",
        "model": os.getenv(
            "GEMINI_VISION_QA_MODEL", os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
        ),
    }
    if not metrics["semantic_qa_enabled"]:
        metrics.update({"semantic_score": 100, "accepted": True})
        return metrics

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        metrics["issues"].append("semantic_qa_missing_gemini_key")
        return metrics

    path = Path(image_path)
    if not path.exists():
        metrics["issues"].append("semantic_qa_missing_image")
        return metrics

    scene_contract = _build_scene_contract(scene)
    hero_objects = scene_contract.get("hero_objects", [])
    hero_object_qa = (
        "\nObjetos pequenos críticos desta cena:\n"
        + json.dumps(hero_objects, ensure_ascii=False, indent=2)
        + "\nSe qualquer hero object estiver ausente, pequeno demais, cortado, escondido, desfocado, confundível com outro objeto, ou só reconhecível com zoom, marque accepted=false e critical_failures deve incluir hero_object_illegible ou hero_object_missing.\n"
        if hero_objects
        else ""
    )
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        metrics["issues"].append(f"semantic_qa_failed:{type(exc).__name__}")
        return metrics

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Você é o diretor de qualidade visual do pipeline AI Film.
Avalie se a imagem segue a cena e o prompt. Penalize severamente:
- qualquer texto visível, letras, legenda falsa, assinatura, marca d'água, borda de página ou moldura ornamental;
- personagem principal duplicada;
- Alice adulta, princesa, vestido de baile ou fantasia quando a cena pede criança vitoriana;
- cachorro quando a cena pede gato/gatinhos;
- estilo visual diferente do estilo escolhido;
- pessoas, animais ou objetos que não aparecem na cena;
- composição cortada, rosto ruim, anatomia ruim ou imagem que pareça colagem.

Cena JSON:
{json.dumps(scene, ensure_ascii=False)}

Trecho original que fundamenta a cena:
{str(scene.get("source_excerpt") or "")[:1200]}

Bíblia visual fixa:
{json.dumps(visual_bible or {}, ensure_ascii=False)}

Contrato estruturado da cena:
{json.dumps(scene_contract, ensure_ascii=False, indent=2)}
{hero_object_qa}

Estilo escolhido: {_resolve_image_style(style_key)["label"]}
Prompt enviado ao gerador:
{directed_prompt}

Regras de aceite:
- Uma imagem tecnicamente bonita deve ser reprovada se violar o contrato estruturado.
- Se houver personagem extra não pedido, objeto/animal errado, idade/rosto da protagonista fora da bíblia ou animal inventado, accepted=false.
- Se a cena pede rabbit hole, não aceite gato/filhote como substituto visual.
- Se a cena pede gato/filhote no colo, não aceite animal fora do colo.
- Se a cena não pede gato/filhote, qualquer gato/filhote é critical failure.
- Se a cena inclui Alice, avalie se ela preserva idade, cabelo, figurino e família facial do filme.
- Se a cena tem hero_objects, eles precisam ser legíveis no frame completo sem zoom; presença ambígua ou pequena demais é critical failure.

Rubrica obrigatória:
- 95-100: todos os required estão claramente visíveis, nenhum forbidden aparece, personagem consistente.
- 88-94: cena fiel com pequena ambiguidade de enquadramento, mas sem objeto obrigatório ausente.
- 70-87: cena bonita, porém algum required não-crítico está ambíguo, pequeno demais ou parcialmente oculto.
- 40-69: objeto/personagem obrigatório ausente ou substituído.
- 0-39: imagem errada, colagem, texto, anatomia grave ou falha crítica.
Para hero_objects: se o objeto estiver pequeno demais, oculto, desfocado ou ambíguo, a pontuação máxima é 69 e accepted=false.
Se todos os required estiverem visíveis e não houver critical_failures, semantic_score deve ser pelo menos 88 e accepted=true.

Retorne somente JSON válido, sem markdown:
{{
  "semantic_score": 0-100,
  "accepted": true/false,
  "hero_object_legibility": true/false,
  "hero_object_notes": "descrição curta do que está legível ou falhou",
  "issues": ["issue_code"],
  "critical_failures": ["failure_code"],
  "retry_prompt": "correção objetiva em inglês para regenerar a imagem"
}}
"""
        response = client.models.generate_content(
            model=str(metrics["model"]),
            contents=[
                prompt,
                types.Part.from_bytes(data=path.read_bytes(), mime_type="image/png"),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        try:
            parsed = _extract_json_object(_extract_response_text(response))
        except ValueError:
            compact_prompt = f"""
Return only valid JSON.
Evaluate this image against this scene contract:
{json.dumps(scene_contract, ensure_ascii=False)}
{hero_object_qa}

Selected style: {_resolve_image_style(style_key)["label"]}
Scene: {json.dumps(scene, ensure_ascii=False)}

Rubric:
- 95-100: all required elements are clearly visible and no forbidden elements appear.
- 88-94: faithful scene with only minor framing ambiguity.
- 70-87: visually good but one non-critical required element is ambiguous, small or partially hidden.
- 40-69: required object or character is missing or substituted.
- 0-39: wrong image, text artifact, severe anatomy issue or critical failure.
For hero_objects, if the object is too small, hidden, blurred or ambiguous in the full frame, max score is 69 and accepted=false.
If all required elements are visible and critical_failures is empty, semantic_score must be at least 88 and accepted=true.

JSON schema:
{{
  "semantic_score": 0-100,
  "accepted": true/false,
  "hero_object_legibility": true/false,
  "hero_object_notes": "short note",
  "issues": ["issue_code"],
  "critical_failures": ["failure_code"],
  "retry_prompt": "short English regeneration instruction"
}}
"""
            fallback_response = client.models.generate_content(
                model=str(metrics["model"]),
                contents=[
                    compact_prompt,
                    types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type="image/png",
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            parsed = _extract_json_object(_extract_response_text(fallback_response))
        score = max(0, min(100, _safe_int(parsed.get("semantic_score"))))
        issues = parsed.get("issues", [])
        critical_failures = parsed.get("critical_failures", [])
        issue_codes = [str(issue) for issue in issues if issue]
        critical_codes = [str(issue) for issue in critical_failures if issue]
        hero_object_legibility = parsed.get("hero_object_legibility")
        hero_object_notes = str(parsed.get("hero_object_notes", ""))[:500]
        if hero_objects and hero_object_legibility is False:
            if "hero_object_illegible" not in critical_codes:
                critical_codes.append("hero_object_illegible")
            if "hero_object_legibility_failed" not in issue_codes:
                issue_codes.append("hero_object_legibility_failed")
        if critical_codes:
            score = min(score, 79)
        if hero_objects and any(
            code in critical_codes
            for code in ("hero_object_illegible", "hero_object_missing")
        ):
            score = min(score, 69)
        metrics.update(
            {
                "semantic_score": score,
                "accepted": bool(parsed.get("accepted"))
                and not critical_codes
                and score >= _image_semantic_min_score(),
                "issues": [*issue_codes, *critical_codes],
                "critical_failures": critical_codes,
                "hero_objects": hero_objects,
                "hero_object_legibility": (
                    bool(hero_object_legibility)
                    if hero_object_legibility is not None
                    else None
                ),
                "hero_object_notes": hero_object_notes,
                "retry_prompt": str(parsed.get("retry_prompt", ""))[:1000],
            }
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        errors.APIError,
        errors.ClientError,
        errors.ServerError,
        errors.UnknownApiResponseError,
    ) as exc:
        metrics["issues"].append(f"semantic_qa_failed:{type(exc).__name__}")

    return metrics


def _combine_image_quality(
    technical_metrics: Dict[str, Any],
    semantic_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    technical_score = float(technical_metrics.get("quality_score", 0) or 0)
    semantic_score = float(semantic_metrics.get("semantic_score", 0) or 0)
    if not semantic_metrics.get("semantic_qa_enabled", True):
        combined_score = technical_score
    else:
        combined_score = (technical_score * 0.4) + (semantic_score * 0.6)

    issues = [
        *technical_metrics.get("issues", []),
        *semantic_metrics.get("issues", []),
    ]
    if semantic_metrics.get("semantic_qa_enabled", True) and not semantic_metrics.get(
        "accepted"
    ):
        issues.append("semantic_quality_below_threshold")
    technical_blockers = {
        "low_resolution",
        "low_contrast",
        "blurry_image",
        "technical_quality_below_threshold",
    }
    technical_accepted = not bool(
        technical_blockers & set(str(issue) for issue in issues)
    )
    if semantic_metrics.get("semantic_qa_enabled", True) and not technical_accepted:
        issues.append("technical_quality_below_threshold")
    controlled_guidance = _controlled_image_workflow_guidance(semantic_metrics, issues)
    if controlled_guidance.get("control_workflow_required"):
        issues.append("control_workflow_required")

    return {
        **technical_metrics,
        "technical_score": round(technical_score, 1),
        "semantic_score": round(semantic_score, 1),
        "technical_accepted": technical_accepted,
        "semantic_accepted": bool(semantic_metrics.get("accepted"))
        and technical_accepted,
        "semantic_critical_failures": semantic_metrics.get("critical_failures", []),
        "semantic_retry_prompt": semantic_metrics.get("retry_prompt", ""),
        "semantic_qa_model": semantic_metrics.get("model"),
        "hero_objects": semantic_metrics.get("hero_objects", []),
        "hero_object_legibility": semantic_metrics.get("hero_object_legibility"),
        "hero_object_notes": semantic_metrics.get("hero_object_notes", ""),
        **controlled_guidance,
        "quality_score": round(min(100, combined_score), 1),
        "issues": sorted(set(issues)),
    }


def _controlled_image_workflow_guidance(
    semantic_metrics: Dict[str, Any],
    issues: List[str],
) -> Dict[str, Any]:
    issue_codes = {
        str(issue)
        for issue in [
            *issues,
            *semantic_metrics.get("critical_failures", []),
        ]
        if issue
    }
    has_hero_object = bool(semantic_metrics.get("hero_objects"))
    hero_failed = (
        semantic_metrics.get("hero_object_legibility") is False
        or "hero_object_missing" in issue_codes
        or "hero_object_illegible" in issue_codes
        or "hero_object_legibility_failed" in issue_codes
    )
    natural_animal_failed = bool(
        {
            "anthropomorphic_mouse",
            "mouse_wearing_clothes",
            "anthropomorphic_character",
            "forbidden_character_present",
        }
        & issue_codes
    )
    character_replaced = bool(
        {
            "missing_character",
            "missing_ludovico_professor",
            "wrong_character",
        }
        & issue_codes
    )
    if not (
        has_hero_object
        and hero_failed
        and (natural_animal_failed or character_replaced)
    ):
        return {
            "control_workflow_required": False,
            "recommended_generation_strategy": "txt2img_retry",
            "operator_next_action": "",
        }
    return {
        "control_workflow_required": True,
        "recommended_generation_strategy": "controlled_inpaint",
        "operator_next_action": (
            "Use a controlled two-stage workflow: keep the approved base scene, "
            "then inpaint the small hero object with a mask or ControlNet/IPAdapter. "
            "Do not spend another plain txt2img retry on this scene."
        ),
    }


def _semantic_gate_blocked_metric(
    scene: Dict[str, Any],
    image_style: str,
    quality_preset_key: str,
    provider: str,
    best_metric: Dict[str, Any] | None,
) -> Dict[str, Any]:
    issues = ["semantic_gate_blocked"]
    if best_metric:
        issues.extend(str(issue) for issue in best_metric.get("issues", []) if issue)
    return {
        "scene_id": scene["scene_id"],
        "generation_method": provider,
        "style": image_style,
        "quality_preset": quality_preset_key,
        "path": None,
        "exists": False,
        "size_bytes": 0,
        "valid": False,
        "technical_score": (
            _safe_float(best_metric.get("technical_score")) if best_metric else 0
        ),
        "semantic_score": (
            _safe_float(best_metric.get("semantic_score")) if best_metric else 0
        ),
        "semantic_accepted": False,
        "semantic_critical_failures": (
            best_metric.get("semantic_critical_failures", []) if best_metric else []
        ),
        "semantic_retry_prompt": (
            best_metric.get("semantic_retry_prompt", "") if best_metric else ""
        ),
        "control_workflow_required": (
            bool(best_metric.get("control_workflow_required")) if best_metric else False
        ),
        "recommended_generation_strategy": (
            best_metric.get("recommended_generation_strategy", "txt2img_retry")
            if best_metric
            else "txt2img_retry"
        ),
        "operator_next_action": (
            best_metric.get("operator_next_action", "") if best_metric else ""
        ),
        "quality_score": 0,
        "issues": issues,
    }


def _evaluate_image_set_consistency(
    scene_images: List[Dict[str, Any]],
    visual_bible: Dict[str, Any],
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "consistency_score": 0,
        "accepted": False,
        "issues": [],
        "model": os.getenv(
            "GEMINI_VISION_QA_MODEL", os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
        ),
    }
    if not _semantic_qa_enabled():
        metrics.update({"consistency_score": 100, "accepted": True})
        return metrics

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    valid_images = [
        Path(item["image_path"])
        for item in scene_images
        if item.get("image_path")
        and Path(item["image_path"]).exists()
        and Path(item["image_path"]).stat().st_size > 1000
    ]
    if not api_key or len(valid_images) < 2:
        metrics["issues"].append("consistency_qa_insufficient_inputs")
        return metrics

    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        metrics["issues"].append(f"consistency_qa_failed:{type(exc).__name__}")
        return metrics

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Avalie se estas imagens pertencem ao mesmo filme.
Use a bíblia visual abaixo como fonte da verdade:
{json.dumps(visual_bible, ensure_ascii=False)}

Penalize: mudança de estilo/medium entre cenas, mudança de idade/figurino da protagonista,
paleta incompatível, cenas com acabamento de gravura enquanto outras são aquarela/foto,
e composição que pareça gerada por prompts sem direção de arte compartilhada.
Penalize também composições quase duplicadas entre cenas diferentes, especialmente se duas cenas externas
reutilizam a mesma árvore, pose da Alice, ângulo de câmera e geografia visual mudando apenas o objeto narrativo.
Para aceitar, o score precisa representar qualidade premium: mesma Alice, mesmo figurino-base,
mesma linguagem cinematográfica, mesma paleta e nenhum frame parecendo vir de outro modelo ou época.

Retorne somente JSON válido:
{{
  "consistency_score": 0-100,
  "accepted": true/false,
  "issues": ["issue_code"],
  "style_notes": "diagnóstico curto"
}}
"""
        contents: List[Any] = [prompt]
        for path in valid_images[:5]:
            contents.append(
                types.Part.from_bytes(data=path.read_bytes(), mime_type="image/png")
            )
        response = client.models.generate_content(
            model=str(metrics["model"]),
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        parsed = _extract_json_object(_extract_response_text(response))
        score = max(0, min(100, _safe_int(parsed.get("consistency_score"))))
        min_score = _visual_consistency_min_score()
        soft_min_score = _visual_consistency_soft_min_score()
        parsed_issues = [str(issue) for issue in parsed.get("issues", []) if issue]
        style_notes = str(parsed.get("style_notes", ""))[:1000]
        no_issue_soft_pass = (
            score >= soft_min_score
            and not parsed_issues
            and _text_has_any(
                style_notes,
                [
                    "alta consistência",
                    "boa consistência",
                    "excelente consistência",
                    "identidade consistente",
                    "consistent identity",
                    "excellent consistency",
                    "sem issues",
                    "no issues",
                ],
            )
        )
        metrics.update(
            {
                "consistency_score": score,
                "accepted": (bool(parsed.get("accepted")) and score >= min_score)
                or no_issue_soft_pass,
                "issues": parsed_issues,
                "style_notes": style_notes,
                "min_score": min_score,
                "soft_min_score": soft_min_score,
                "soft_pass": no_issue_soft_pass,
            }
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        errors.APIError,
        errors.ClientError,
        errors.ServerError,
        errors.UnknownApiResponseError,
    ) as exc:
        metrics["issues"].append(f"consistency_qa_failed:{type(exc).__name__}")

    return metrics


def _probe_image_quality(
    image_path: str,
    scene: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    path = Path(image_path)
    metrics: Dict[str, Any] = {
        "path": image_path,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "valid": False,
        "width": 0,
        "height": 0,
        "quality_score": 0,
        "issues": [],
    }
    if not path.exists():
        metrics["issues"].append("missing_file")
        return metrics

    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(path) as image:
            image.load()
            metrics["width"], metrics["height"] = image.size
            metrics["mode"] = image.mode
            grayscale = image.convert("L")
            stat = ImageStat.Stat(grayscale)
            contrast = stat.stddev[0] if stat.stddev else 0.0
            edge_stat = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES))
            edge_sharpness = edge_stat.stddev[0] if edge_stat.stddev else 0.0
            sharpness_for_gate = edge_sharpness
            metrics["contrast"] = round(contrast, 2)
            metrics["edge_sharpness"] = round(edge_sharpness, 2)
            metrics["sharpness_gate_scope"] = "global"
            if scene and _hero_object_requirements(scene):
                left, top, right, bottom = _hero_object_quality_box(scene)
                width, height = image.size
                focus = grayscale.crop(
                    (
                        int(width * left),
                        int(height * top),
                        int(width * right),
                        int(height * bottom),
                    )
                )
                focus_edge_stat = ImageStat.Stat(focus.filter(ImageFilter.FIND_EDGES))
                sharpness_for_gate = (
                    focus_edge_stat.stddev[0] if focus_edge_stat.stddev else 0.0
                )
                metrics["focal_edge_sharpness"] = round(sharpness_for_gate, 2)
                metrics["sharpness_gate_scope"] = "hero_object"

        pixel_count = int(metrics["width"]) * int(metrics["height"])
        min_edge_sharpness = _image_min_edge_sharpness()
        size_score = min(25, metrics["size_bytes"] / 16000)
        resolution_score = min(30, pixel_count / (512 * 512) * 30)
        contrast_score = min(25, contrast / 64 * 25)
        sharpness_score = min(20, sharpness_for_gate / 42 * 20)
        score = round(
            size_score + resolution_score + contrast_score + sharpness_score, 1
        )
        metrics["quality_score"] = min(100, score)
        metrics["valid"] = metrics["size_bytes"] > 1000 and pixel_count > 0
        if int(metrics["width"]) < 512 or int(metrics["height"]) < 512:
            metrics["issues"].append("low_resolution")
        if contrast < 8:
            metrics["issues"].append("low_contrast")
        if sharpness_for_gate < min_edge_sharpness:
            metrics["issues"].append("blurry_image")
            metrics["quality_score"] = min(_safe_float(metrics["quality_score"]), 76.0)
    except (OSError, ValueError) as exc:
        metrics["issues"].append(f"invalid_image:{type(exc).__name__}")
    return metrics


def _probe_media_quality(media_path: str, media_type: str) -> Dict[str, Any]:
    path = Path(media_path)
    metrics: Dict[str, Any] = {
        "path": media_path,
        "type": media_type,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "valid": False,
        "duration_seconds": 0.0,
        "bit_rate": 0,
        "quality_score": 0,
        "issues": [],
    }
    if not path.exists():
        metrics["issues"].append("missing_file")
        return metrics

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        metrics["issues"].append("ffprobe_failed")
        return metrics

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        metrics["issues"].append("ffprobe_invalid_json")
        return metrics

    fmt = payload.get("format", {})
    duration = _safe_float(fmt.get("duration"))
    bit_rate = int(_safe_float(fmt.get("bit_rate")))
    metrics["duration_seconds"] = round(duration, 3)
    metrics["bit_rate"] = bit_rate
    metrics["valid"] = metrics["size_bytes"] > 1000 and duration > 0

    if media_type == "audio":
        duration_score = min(45, duration / 6 * 45)
        bitrate_score = min(35, bit_rate / 64000 * 35) if bit_rate else 0
        size_score = min(20, metrics["size_bytes"] / 100000 * 20)
    else:
        duration_score = min(30, duration / 10 * 30)
        bitrate_score = min(35, bit_rate / 250000 * 35) if bit_rate else 0
        size_score = min(35, metrics["size_bytes"] / 300000 * 35)

    metrics["quality_score"] = min(
        100, round(duration_score + bitrate_score + size_score, 1)
    )
    if duration <= 0:
        metrics["issues"].append("zero_duration")
    if bit_rate and bit_rate < 32000:
        metrics["issues"].append("low_bitrate")
    return metrics


def _audio_loudness_target_lufs() -> float:
    return _safe_float(os.getenv("AUDIO_LOUDNESS_TARGET_LUFS", "-14.0"))


def _measure_audio_loudness(audio_path: str) -> Dict[str, Any]:
    if not shutil.which("ffmpeg"):
        return {"issues": ["ffmpeg_unavailable_for_loudness"]}
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            audio_path,
            "-af",
            (
                "loudnorm=I="
                f"{_audio_loudness_target_lufs():.1f}:TP=-1.5:LRA=11:"
                "print_format=json"
            ),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {"issues": ["loudness_probe_failed"]}
    match = re.search(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.S)
    if not match:
        return {"issues": ["loudness_probe_missing_json"]}
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"issues": ["loudness_probe_invalid_json"]}
    return {
        "input_i_lufs": _safe_float(payload.get("input_i")),
        "input_tp_db": _safe_float(payload.get("input_tp")),
        "input_lra_lu": _safe_float(payload.get("input_lra")),
        "target_i_lufs": _audio_loudness_target_lufs(),
        "normalization": "loudnorm",
        "issues": [],
    }


def _audio_waveform_samples(audio_path: str, bins: int = 48) -> List[float]:
    if bins <= 0 or not shutil.which("ffmpeg"):
        return []
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            audio_path,
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return []
    sample_count = len(result.stdout) // 2
    if sample_count <= 0:
        return []
    samples = struct.unpack(f"<{sample_count}h", result.stdout[: sample_count * 2])
    chunk_size = max(1, math.ceil(sample_count / bins))
    values: List[float] = []
    for start in range(0, sample_count, chunk_size):
        chunk = samples[start : start + chunk_size]
        if not chunk:
            continue
        rms = math.sqrt(
            sum(float(sample) * float(sample) for sample in chunk) / len(chunk)
        )
        values.append(rms)
    peak = max(values) if values else 0
    if peak <= 0:
        return [0.0 for _ in range(min(bins, len(values) or bins))]
    return [round(min(1.0, value / peak), 3) for value in values[:bins]]


def _response_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("status")
        return str(message or detail)[:500]
    return str(detail or payload)[:500]


def _elevenlabs_remaining_characters(api_key: str) -> int | None:
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": api_key},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"⚠️ Não foi possível consultar quota ElevenLabs: {type(exc).__name__}")
        return None
    if response.status_code != 200:
        print(
            "⚠️ Não foi possível consultar quota ElevenLabs: "
            f"HTTP {response.status_code} {_response_error_detail(response)}"
        )
        return None
    try:
        subscription = response.json().get("subscription", {})
    except ValueError:
        return None
    character_limit = _safe_int(subscription.get("character_limit"), 0)
    character_count = _safe_int(subscription.get("character_count"), 0)
    if character_limit <= 0:
        return None
    return max(0, character_limit - character_count)


def _premium_audio_narration(scene: Dict[str, Any]) -> str:
    scene_text = _scene_text(scene)
    description = str(scene.get("description") or scene.get("prompt") or "").strip()

    if _text_has_any_phrase(scene_text, ["açucareiro", "ratinho", "white mouse"]):
        return (
            "À mesa de chá, Ludovico ergue a tampa do açucareiro. "
            "Alice prende a respiração quando um ratinho branco surge, pequeno e vivo, "
            "no brilho da prata."
        )
    if _text_has_any_phrase(scene_text, ["formigueiro", "anthill", "ants"]):
        return (
            "No jardim silencioso, Alice se aproxima das raízes antigas. "
            "Ali, quase escondido na grama, um pequeno formigueiro transforma o mundo "
            "em descoberta."
        )
    if _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        return (
            "Entre a grama e as raízes, Alice encontra uma abertura escura no barranco. "
            "A toca parece pequena demais para guardar um segredo tão grande."
        )

    cleaned = re.sub(r"^\s*cena\s+\d+\s*[:.-]\s*", "", description, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "Alice observa o mundo ao redor como se cada detalhe pudesse abrir uma porta."
    if len(cleaned) <= 230:
        return cleaned
    cutoff = cleaned[:230].rsplit(" ", 1)[0].strip(" ,;:")
    return f"{cutoff}."


def _premium_audio_direction(scene: Dict[str, Any]) -> Dict[str, Any]:
    scene_text = _scene_text(scene)
    if _text_has_any_phrase(scene_text, ["açucareiro", "ratinho", "white mouse"]):
        return {
            "tone": "wonder, suspense leve, calor íntimo de sala de chá",
            "pace": "pausado, com pausa antes da revelação do ratinho",
            "delivery": "narrador cinematográfico em português brasileiro, expressivo sem teatralizar",
        }
    if _text_has_any_phrase(scene_text, ["formigueiro", "anthill", "ants"]):
        return {
            "tone": "curiosidade delicada, observação infantil, assombro quieto",
            "pace": "lento e contemplativo",
            "delivery": "narrador cinematográfico em português brasileiro, voz próxima e precisa",
        }
    if _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        return {
            "tone": "mistério, convite para aventura, tensão suave",
            "pace": "crescendo discreto",
            "delivery": "narrador cinematográfico em português brasileiro, íntimo e envolvente",
        }
    return {
        "tone": "cinematográfico, técnico, premium",
        "pace": "natural, com pausas curtas entre imagens importantes",
        "delivery": "narrador cinematográfico em português brasileiro, claro e elegante",
    }


def _elevenlabs_voice_settings() -> Dict[str, Any]:
    return {
        "stability": _safe_float(os.getenv("ELEVENLABS_STABILITY", "0.62")),
        "similarity_boost": _safe_float(
            os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.82")
        ),
        "style": _safe_float(os.getenv("ELEVENLABS_STYLE", "0.35")),
        "use_speaker_boost": os.getenv(
            "ELEVENLABS_USE_SPEAKER_BOOST",
            "true",
        )
        .strip()
        .lower()
        not in {"0", "false", "no"},
    }


def _scene_voice_role(scene: Dict[str, Any]) -> str:
    explicit_role = str(
        scene.get("voice_role")
        or scene.get("speaker")
        or scene.get("character_voice")
        or ""
    ).strip()
    if explicit_role:
        return explicit_role
    return "narrator"


def _voice_env_key(role: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", role).strip("_").upper()
    return f"ELEVENLABS_VOICE_ID_{normalized or 'NARRATOR'}"


def _elevenlabs_voice_id_for_scene(scene: Dict[str, Any]) -> tuple[str, str]:
    role = _scene_voice_role(scene)
    voice_id = os.getenv(_voice_env_key(role), "").strip()
    if not voice_id and role.lower() != "narrator":
        voice_id = os.getenv("ELEVENLABS_VOICE_ID_NARRATOR", "").strip()
    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "hpp4J3VqNfWAUOO0d1Us").strip()
    return voice_id, role


def _ambient_audio_enabled() -> bool:
    return os.getenv("AUDIO_AMBIENT_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _ambient_audio_profile(scene: Dict[str, Any]) -> Dict[str, Any]:
    scene_text = _scene_text(scene)
    if _text_has_any_phrase(scene_text, ["açucareiro", "mesa de chá", "tea"]):
        return {
            "label": "tea_room_air",
            "frequency": 392,
            "noise_color": "pink",
            "bed_volume": 0.055,
        }
    if _text_has_any_phrase(scene_text, ["toca de coelho", "rabbit hole"]):
        return {
            "label": "mysterious_grass_rustle",
            "frequency": 196,
            "noise_color": "brown",
            "bed_volume": 0.06,
        }
    return {
        "label": "garden_air",
        "frequency": 288,
        "noise_color": "pink",
        "bed_volume": 0.05,
    }


def _render_ambient_bed(
    scene: Dict[str, Any],
    output_path: str,
    duration_seconds: float,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "path": output_path,
        "enabled": _ambient_audio_enabled(),
        "valid": False,
        "profile": _ambient_audio_profile(scene),
        "issues": [],
    }
    if not metrics["enabled"]:
        metrics["issues"].append("ambient_audio_disabled")
        return metrics
    if not shutil.which("ffmpeg"):
        metrics["issues"].append("ffmpeg_unavailable_for_ambient")
        return metrics
    duration = max(0.5, _safe_float(duration_seconds))
    profile = metrics["profile"]
    fade_out_start = max(0.0, duration - 0.8)
    filter_complex = (
        "[0:a]highpass=f=140,lowpass=f=2600,"
        f"volume={_safe_float(profile.get('bed_volume'))}[noise];"
        "[1:a]volume=0.012[tone];"
        "[noise][tone]amix=inputs=2:normalize=0,"
        "afade=t=in:st=0:d=0.45,"
        f"afade=t=out:st={fade_out_start:.2f}:d=0.8[out]"
    )
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            (
                "anoisesrc="
                f"color={profile.get('noise_color')}:"
                "amplitude=0.018:sample_rate=44100"
            ),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={_safe_int(profile.get('frequency'), 288)}:sample_rate=44100",
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-t",
            f"{duration:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            output_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        metrics["issues"].append("ambient_audio_render_failed")
        metrics["error"] = result.stderr[:500]
        return metrics
    probed = _probe_media_quality(output_path, "audio")
    metrics.update(probed)
    metrics["profile"] = profile
    return metrics


def _enhance_premium_audio(
    input_path: str,
    output_path: str,
    scene: Dict[str, Any],
) -> Dict[str, Any]:
    base_quality = _probe_media_quality(input_path, "audio")
    if not bool(base_quality.get("valid")) or not shutil.which("ffmpeg"):
        return {
            **base_quality,
            "enhanced": False,
            "loudness": _measure_audio_loudness(input_path),
            "waveform": _audio_waveform_samples(input_path),
        }

    duration = _safe_float(base_quality.get("duration_seconds"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ambient_path = output.with_name(f"{output.stem}_ambient.m4a")
    ambient = _render_ambient_bed(scene, str(ambient_path), duration)
    target = _audio_loudness_target_lufs()
    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
    ]
    filter_complex = (
        "[0:a]loudnorm=" f"I={target:.1f}:TP=-1.5:LRA=11," "aresample=44100[out]"
    )
    if bool(ambient.get("valid")):
        command.extend(["-i", str(ambient_path)])
        filter_complex = (
            "[0:a]volume=1.0[voice];"
            "[1:a]volume=0.18[bed];"
            "[voice][bed]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I={target:.1f}:TP=-1.5:LRA=11,"
            "aresample=44100[out]"
        )
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(output),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        ambient_path.unlink(missing_ok=True)
    except OSError:
        pass
    if result.returncode != 0:
        fallback = _probe_media_quality(input_path, "audio")
        fallback.update(
            {
                "enhanced": False,
                "ambient": ambient,
                "loudness": _measure_audio_loudness(input_path),
                "waveform": _audio_waveform_samples(input_path),
                "issues": [
                    *fallback.get("issues", []),
                    "premium_audio_enhancement_failed",
                ],
                "error": result.stderr[:500],
            }
        )
        return fallback
    enhanced = _probe_media_quality(str(output), "audio")
    enhanced.update(
        {
            "enhanced": True,
            "ambient": ambient,
            "loudness": _measure_audio_loudness(str(output)),
            "waveform": _audio_waveform_samples(str(output)),
        }
    )
    return enhanced


def _audio_quality_gate(
    media_quality: Dict[str, Any],
    narration_text: str,
    generation_method: str,
) -> Dict[str, Any]:
    gated = {**media_quality}
    issues = [str(issue) for issue in gated.get("issues", []) if issue]
    duration = _safe_float(gated.get("duration_seconds"))
    bit_rate = _safe_int(gated.get("bit_rate"), 0)
    audio_path = str(gated.get("path") or "").strip()

    if audio_path and not gated.get("loudness"):
        gated["loudness"] = _measure_audio_loudness(audio_path)
    if audio_path and not gated.get("waveform"):
        gated["waveform"] = _audio_waveform_samples(audio_path)

    if re.match(r"^\s*cena\s+\d+\s*[:.-]", narration_text, flags=re.I):
        issues.append("debug_scene_label_in_narration")
        gated["quality_score"] = min(_safe_float(gated.get("quality_score")), 82.0)
    if generation_method != "elevenlabs":
        issues.append("non_premium_voice_provider")
        gated["quality_score"] = min(_safe_float(gated.get("quality_score")), 72.0)
    if duration < 2.5:
        issues.append("audio_too_short_for_premium_narration")
        gated["quality_score"] = min(_safe_float(gated.get("quality_score")), 78.0)
    if bit_rate and bit_rate < 96000:
        issues.append("premium_audio_bitrate_below_96k")
        gated["quality_score"] = min(_safe_float(gated.get("quality_score")), 84.0)
    loudness = gated.get("loudness") or {}
    input_i = _safe_float(loudness.get("input_i_lufs"))
    target_i = _safe_float(loudness.get("target_i_lufs"), _audio_loudness_target_lufs())
    if generation_method == "elevenlabs" and input_i and abs(input_i - target_i) > 3.0:
        issues.append("loudness_outside_video_standard")
        gated["quality_score"] = min(_safe_float(gated.get("quality_score")), 88.0)

    gated["issues"] = sorted(set(issues))
    gated["premium_audio"] = (
        generation_method == "elevenlabs"
        and not gated["issues"]
        and _safe_float(gated.get("quality_score")) >= 88.0
    )
    return gated


def _local_tts_enabled() -> bool:
    return os.getenv("AUDIO_LOCAL_TTS_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _generate_placeholder_audio(
    narration_text: str,
    audio_path: str,
    reason: str,
) -> Dict[str, Any]:
    metrics = _probe_media_quality(audio_path, "audio")
    if not shutil.which("ffmpeg"):
        metrics["issues"].append("ffmpeg_unavailable")
        return metrics
    duration = max(4.0, min(12.0, len(narration_text) / 18.0))
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=44100",
            "-t",
            f"{duration:.2f}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "96k",
            audio_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        metrics["issues"].append("placeholder_audio_failed")
        metrics["error"] = result.stderr[:500]
        return metrics
    metrics = _probe_media_quality(audio_path, "audio")
    metrics["quality_score"] = min(_safe_float(metrics.get("quality_score")), 55.0)
    metrics["issues"] = [
        *metrics.get("issues", []),
        "voice_provider_unavailable",
        reason,
    ]
    return metrics


def _generate_local_tts_audio(
    narration_text: str,
    audio_path: str,
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "path": audio_path,
        "type": "audio",
        "exists": False,
        "size_bytes": 0,
        "valid": False,
        "duration_seconds": 0.0,
        "bit_rate": 0,
        "quality_score": 0,
        "issues": [],
    }
    if not _local_tts_enabled():
        metrics["issues"].append("local_tts_disabled")
        return metrics
    if not shutil.which("say"):
        return _generate_placeholder_audio(
            narration_text,
            audio_path,
            "macos_say_unavailable",
        )
    if not shutil.which("ffmpeg"):
        metrics["issues"].append("ffmpeg_unavailable")
        return metrics

    output_path = Path(audio_path)
    aiff_path = output_path.with_suffix(".aiff")
    voice_name = os.getenv("AUDIO_LOCAL_TTS_VOICE", "Luciana").strip()
    say_commands = []
    if voice_name:
        say_commands.append(
            ["say", "-v", voice_name, "-o", str(aiff_path), narration_text]
        )
    say_commands.append(["say", "-o", str(aiff_path), narration_text])

    say_result: subprocess.CompletedProcess[str] | None = None
    for command in say_commands:
        say_result = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
        if (
            say_result.returncode == 0
            and aiff_path.exists()
            and aiff_path.stat().st_size > 1000
        ):
            break
    if (
        say_result is None
        or say_result.returncode != 0
        or not aiff_path.exists()
        or aiff_path.stat().st_size <= 1000
    ):
        metrics = _generate_placeholder_audio(
            narration_text,
            audio_path,
            "macos_say_failed",
        )
        if say_result and say_result.stderr:
            metrics["error"] = say_result.stderr[:500]
        return metrics

    ffmpeg_result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(aiff_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        aiff_path.unlink(missing_ok=True)
    except OSError:
        pass
    if ffmpeg_result.returncode != 0:
        metrics = _generate_placeholder_audio(
            narration_text,
            audio_path,
            "local_tts_transcode_failed",
        )
        if ffmpeg_result.stderr:
            metrics["error"] = ffmpeg_result.stderr[:500]
        return metrics
    metrics = _probe_media_quality(audio_path, "audio")
    if not bool(metrics.get("valid")):
        return _generate_placeholder_audio(
            narration_text,
            audio_path,
            "local_tts_invalid_audio",
        )
    return metrics


def _aggregate_quality(
    image_metrics: List[Dict[str, Any]],
    audio_metrics: List[Dict[str, Any]],
    video_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    def average(items: List[Dict[str, Any]]) -> float:
        scores = [float(item.get("quality_score", 0)) for item in items]
        return round(sum(scores) / len(scores), 1) if scores else 0.0

    categories = {
        "images": average(image_metrics),
        "audio": average(audio_metrics),
        "video": float(video_metrics.get("quality_score", 0) or 0),
    }
    if categories["images"] > 0:
        overall = round(
            (categories["images"] * 0.6)
            + (categories["video"] * 0.25)
            + (categories["audio"] * 0.15),
            1,
        )
    else:
        available = [score for score in categories.values() if score > 0]
        overall = round(sum(available) / len(available), 1) if available else 0.0
    blocked_images = [
        item
        for item in image_metrics
        if "semantic_gate_blocked" in item.get("issues", [])
        or (
            item.get("semantic_accepted") is False
            and item.get("generation_method") in {"gemini_image", "comfyui", "mock"}
        )
    ]
    gate_status = "blocked" if blocked_images else "passed"
    if blocked_images:
        overall = min(overall, 69.0)
    return {
        "overall_score": overall,
        "categories": categories,
        "gate_status": gate_status,
        "blocked_image_count": len(blocked_images),
        "blocking_issues": [
            {
                "scene_id": item.get("scene_id"),
                "generation_method": item.get("generation_method"),
                "semantic_score": item.get("semantic_score"),
                "control_workflow_required": item.get(
                    "control_workflow_required", False
                ),
                "recommended_generation_strategy": item.get(
                    "recommended_generation_strategy", "txt2img_retry"
                ),
                "operator_next_action": item.get("operator_next_action", ""),
                "issues": item.get("issues", []),
            }
            for item in blocked_images
        ],
        "images": image_metrics,
        "audio": audio_metrics,
        "video": video_metrics,
    }


def create_open3d_workflow():
    """
    Creates a LangGraph workflow for Open3D processing

    Returns:
        A configured LangGraph workflow
    """
    try:
        import os

        from langgraph.graph import END, StateGraph

        from orchestration.llm_config import generate_cinematic_prompt, get_llm

        print("🔧 Criando workflow LangGraph funcional...")

        def extract_story(state: Open3DAgentState) -> Open3DAgentState:
            """Extract and process story from multimodal input"""
            # Debug: ver o que está no state
            print(f"🔍 DEBUG - State keys: {list(state.keys())}")
            print(f"🔍 DEBUG - State type: {type(state)}")

            story_text = state.get("story_text", "")

            if not story_text:
                # Try to get from enhanced_multimodal_input_asset
                if "enhanced_multimodal_input_asset" in state:
                    print("🔍 DEBUG - Found enhanced_multimodal_input_asset in state")
                    story_text = state["enhanced_multimodal_input_asset"].get(
                        "story_text", ""
                    )
                else:
                    print("⚠️ DEBUG - enhanced_multimodal_input_asset NOT in state")

            print(f"📖 Processando história: {len(story_text)} caracteres")

            if not story_text:
                print(f"⚠️ AVISO: História vazia! State completo: {state}")

            # Generate cinematic prompt using Flash model (Pro exceeded quota)
            prompt = generate_cinematic_prompt(story_text, use_pro_model=False)
            image_style = state.get("image_style", DEFAULT_IMAGE_STYLE)
            visual_bible = _build_visual_bible(story_text, image_style)
            input_tokens = _estimate_tokens(story_text)
            output_tokens = _estimate_tokens(prompt)
            gemini_input_usd_per_1m = _safe_float(
                os.getenv("GEMINI_INPUT_USD_PER_1M_TOKENS", "0.30")
            )
            gemini_output_usd_per_1m = _safe_float(
                os.getenv("GEMINI_OUTPUT_USD_PER_1M_TOKENS", "2.50")
            )

            state.update(
                {
                    "story_text": story_text,
                    "cinematic_prompt": prompt,
                    "visual_bible": visual_bible,
                    "cost_estimate": {
                        **state.get("cost_estimate", {}),
                        "llm_input_tokens": input_tokens,
                        "llm_output_tokens": output_tokens,
                        "llm_usd": round(
                            (input_tokens / 1_000_000 * gemini_input_usd_per_1m)
                            + (output_tokens / 1_000_000 * gemini_output_usd_per_1m),
                            6,
                        ),
                    },
                    "current_step": "story_extracted",
                }
            )

            return state

        def generate_scenes(state: Open3DAgentState) -> Open3DAgentState:
            """Generate scenes from story using LLM"""
            story_text = state.get("story_text", "")
            cinematic_prompt = state.get("cinematic_prompt", "")
            max_scenes = state.get("max_scenes", 8)
            image_style = state.get("image_style", DEFAULT_IMAGE_STYLE)
            style_label = _resolve_image_style(image_style)["label"]
            visual_bible = state.get("visual_bible") or _build_visual_bible(
                story_text,
                image_style,
            )

            print(f"🎬 Gerando cenas com estilo visual: {style_label}...")

            if not story_text:
                print("⚠️ História vazia, usando cenas mock")
                scenes = [
                    {
                        "scene_id": 1,
                        "description": "Mock scene",
                        "prompt": cinematic_prompt,
                        "duration": 5,
                        "camera_motion": _motion_plan({"scene_id": 1})["description"],
                    },
                    {
                        "scene_id": 2,
                        "description": "Mock scene",
                        "prompt": cinematic_prompt,
                        "duration": 5,
                        "camera_motion": _motion_plan({"scene_id": 2})["description"],
                    },
                    {
                        "scene_id": 3,
                        "description": "Mock scene",
                        "prompt": cinematic_prompt,
                        "duration": 5,
                        "camera_motion": _motion_plan({"scene_id": 3})["description"],
                    },
                ]
            else:
                # Generate real scenes using LLM
                try:
                    llm = get_llm()

                    scene_prompt = f"""
Divida esta história em {max_scenes} cenas cinematográficas.

ESTILO VISUAL ESCOLHIDO:
{style_label}

BÍBLIA VISUAL FIXA DO FILME:
{json.dumps(visual_bible, ensure_ascii=False, indent=2)}

HISTÓRIA:
{story_text}

Para cada cena, forneça:
1. ID da cena (número)
2. Descrição detalhada (2-3 frases)
3. Prompt visual para geração de imagem, respeitando o estilo escolhido e evitando faces/anatomia deformadas
4. Duração sugerida (5-10 segundos)
5. must_include: lista curta de elementos que precisam aparecer na imagem
6. must_not_include: lista curta de elementos proibidos para manter fidelidade à história
7. source_excerpt: trecho literal curto da história que prova que a cena existe
8. camera_motion: movimento de câmera discreto para animar a imagem no vídeo

Regras visuais obrigatórias:
- Cada prompt deve descrever uma única imagem, não uma sequência.
- Todas as cenas precisam parecer frames do mesmo filme: mesmo meio, paleta, personagem, figurino, proporção e acabamento.
- Não invente evento visual. Se o objeto não aparece no trecho original, não coloque em must_include.
- Menção emocional ou motivação não é objeto visual. Exemplo: preocupação com gatinhos não obriga gato em cena se o trecho visual mostra formigueiro.
- Para cenas com açucareiro/ratinho, o ratinho branco e o açucareiro aberto são objetos obrigatórios.
- Não repita a mesma personagem várias vezes na mesma imagem.
- Se Alice aparecer, descreva exatamente uma Alice, totalmente vestida, em pose natural.
- Alice não é princesa, adulta, modelo de moda, nem personagem em vestido de baile.
- Se a história pedir gatos/gatinhos, não inclua cachorro.
- Evite inserir pessoas extras que não existem na cena.
- Evite close-ups extremos, corpo cortado, mãos em destaque e rostos parcialmente ocultos.

Retorne em formato JSON:
[
  {{
    "scene_id": 1,
    "description": "...",
    "prompt": "...",
    "duration": 6,
    "must_include": ["..."],
    "must_not_include": ["..."],
    "source_excerpt": "trecho literal curto da história",
    "camera_motion": "slow cinematic push-in toward the main subject"
  }},
  ...
]
"""

                    response = llm.invoke(scene_prompt)

                    # Parse response
                    # Extrair conteúdo da resposta - tratar diferentes formatos
                    raw_content = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )

                    # Debug: ver tipo e conteúdo original
                    print(f"🔍 DEBUG - Tipo de raw_content: {type(raw_content)}")
                    print(
                        f"🔍 DEBUG - raw_content (primeiros 200 chars): {str(raw_content)[:200]}"
                    )

                    # Verificar se é um dicionário real ou string que parece dict
                    if isinstance(raw_content, dict):
                        content = raw_content.get("text", str(raw_content))
                    elif isinstance(raw_content, list):
                        content = " ".join(str(item) for item in raw_content)
                    else:
                        # É string - verificar se parece um dict
                        content_str = str(raw_content)

                        # Tentar extrair valor de 'text' se a string parecer um dict
                        if (
                            "{'type': 'text', 'text':" in content_str
                            or '{"type": "text", "text":' in content_str
                        ):
                            try:
                                # Tentar parse como dict Python
                                parsed = ast.literal_eval(content_str)
                                if isinstance(parsed, dict) and "text" in parsed:
                                    content = parsed["text"]
                                    print("✅ Extraído campo 'text' do dict")
                                else:
                                    content = content_str
                            except (SyntaxError, ValueError):
                                # Fallback: regex para extrair texto
                                text_match = re.search(
                                    r"'text':\s*['\"](.+?)['\"]", content_str, re.DOTALL
                                )
                                if text_match:
                                    content = text_match.group(1)
                                    print("✅ Extraído campo 'text' via regex")
                                else:
                                    content = content_str
                        else:
                            content = content_str

                    # Debug: ver resposta do LLM processada
                    print(
                        f"🔍 DEBUG - Resposta LLM processada (primeiros 500 chars): {content[:500]}"
                    )

                    # Extract JSON from response - melhorar regex para markdown
                    # Remover markdown se presente
                    content = content.replace("```json", "").replace("```", "").strip()

                    # Procurar por array JSON
                    json_match = re.search(r"\[\s*\{.*?\}\s*\]", content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        # Limpar possíveis problemas
                        json_str = json_str.replace("{{", "{").replace("}}", "}")
                        # Remover aspas extras se presentes
                        json_str = json_str.replace('"[{', "[{").replace('}]"', "}]")

                        try:
                            scenes = json.loads(json_str)
                            scenes = _merge_canonical_scenes(
                                scenes,
                                story_text,
                                image_style,
                                max_scenes,
                            )
                            print(f"✅ {len(scenes)} cenas geradas com LLM")
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Erro no JSON: {e}")
                            print(f"🔍 JSON tentado: {json_str[:200]}...")
                            raise ValueError("JSON inválido mesmo após limpeza")
                    else:
                        print(
                            f"🔍 Conteúdo completo (primeiros 1000 chars): {content[:1000]}"
                        )
                        raise ValueError("Não foi possível extrair JSON da resposta")

                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                    OSError,
                    RuntimeError,
                ) as e:
                    print(f"⚠️ Erro ao gerar cenas com LLM: {e}")
                    print("💡 Usando cenas baseadas na história")
                    # Fallback: criar cenas simples baseadas na história
                    scenes = []
                    story_parts = story_text.split("\n\n")[:max_scenes]
                    for i, part in enumerate(story_parts, 1):
                        scenes.append(
                            {
                                "scene_id": i,
                                "description": part[:200],
                                "prompt": f"{cinematic_prompt}, scene showing: {part[:100]}",
                                "duration": 6,
                                "source_excerpt": part[:700],
                                "must_include": ["exact scene subject"],
                                "must_not_include": visual_bible.get("forbidden", []),
                                "camera_motion": _motion_plan({"scene_id": i})[
                                    "description"
                                ],
                            }
                        )
                    scenes = _merge_canonical_scenes(
                        scenes,
                        story_text,
                        image_style,
                        max_scenes,
                    )
                    print(f"✅ {len(scenes)} cenas criadas (fallback)")

            state.update(
                {
                    "scenes": scenes,
                    "scenes_count": len(scenes),
                    "visual_bible": visual_bible,
                    "current_step": "scenes_generated",
                }
            )

            print(f"✅ {len(scenes)} cenas geradas")
            return state

        def generate_images(state: Open3DAgentState) -> Open3DAgentState:
            """Generate images for scenes using ComfyUI on a RunPod Serverless endpoint"""
            scenes = state.get("scenes", [])
            runpod_api_key = os.getenv("RUNPOD_API_KEY", "")
            runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "")
            image_style = state.get("image_style", DEFAULT_IMAGE_STYLE)
            quality_preset_key = state.get("image_quality_preset", "high")
            quality_preset = _resolve_quality_preset(quality_preset_key)
            session_id = state.get("session_id", "default")
            style_label = _resolve_image_style(image_style)["label"]
            checkpoint_name = _resolve_comfyui_checkpoint(image_style)
            image_provider = _image_generation_provider()
            visual_bible = state.get("visual_bible") or _build_visual_bible(
                state.get("story_text", ""),
                image_style,
            )

            print(
                "🖼️ Gerando imagens... "
                f"provider={image_provider}, estilo={style_label}, "
                f"qualidade={quality_preset_key}, checkpoint={checkpoint_name}"
            )

            scene_images = []
            runpod_jobs = []
            image_metrics = []
            reference_image_path: str | None = None
            runpod_gpu_usd_per_second = _safe_float(
                os.getenv("RUNPOD_GPU_USD_PER_SECOND", "0.00044")
            )
            max_attempts = _image_generation_max_attempts()

            if (
                image_provider == "gemini"
                and _character_reference_enabled()
                and _story_has_any(state.get("story_text", ""), ["alice"])
            ):
                print("🎭 Gerando referência fixa da personagem Alice...")
                reference_scene = _build_character_reference_scene(visual_bible)
                reference_path = "output/alice_character_reference.png"
                reference_seed = _scene_seed(
                    session_id,
                    image_style,
                    "alice_character_reference",
                )
                reference_prompt = _build_image_prompt(
                    reference_scene,
                    image_style,
                    visual_bible,
                    "Create a neutral production character sheet. Preserve identity, avoid story action, keep plain backdrop.",
                )
                job_monitor, _image_record, image_metric = _run_gemini_image_attempt(
                    scene=reference_scene,
                    image_path=reference_path,
                    directed_prompt=reference_prompt,
                    image_style=image_style,
                    style_label=style_label,
                    quality_preset_key=quality_preset_key,
                    scene_seed=reference_seed,
                    visual_bible=visual_bible,
                    attempt=0,
                    reference_image_path=None,
                )
                runpod_jobs.append(job_monitor)
                if _character_reference_accepted(image_metric) and os.path.exists(
                    reference_path
                ):
                    reference_image_path = reference_path
                    visual_bible["character_reference_image_path"] = reference_path
                    visual_bible["character_reference_quality"] = {
                        "quality_score": (
                            image_metric.get("quality_score") if image_metric else None
                        ),
                        "semantic_score": (
                            image_metric.get("semantic_score") if image_metric else None
                        ),
                    }
                    print("✅ Referência fixa da Alice criada e será usada nas cenas.")
                else:
                    print(
                        "⚠️ Referência fixa da Alice não passou no QA; usando fallback por cena."
                    )

            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎨 Gerando imagem para cena {scene['scene_id']}...")

                    # Create output directory
                    os.makedirs("output", exist_ok=True)
                    image_path = f"output/scene_{scene['scene_id']}_image.png"

                    if image_provider == "gemini":
                        retry_instruction = ""
                        best_candidate: (
                            tuple[
                                float,
                                str,
                                Dict[str, Any],
                                Dict[str, Any],
                            ]
                            | None
                        ) = None
                        selected_scene = False
                        for attempt in range(1, max_attempts + 1):
                            attempt_seed = _scene_seed(
                                session_id,
                                image_style,
                                f"gemini:{scene['scene_id']}:{attempt}",
                            )
                            directed_prompt = _build_image_prompt(
                                scene,
                                image_style,
                                visual_bible,
                                retry_instruction,
                            )
                            attempt_path = (
                                image_path
                                if attempt == max_attempts
                                else f"output/scene_{scene['scene_id']}_gemini_attempt_{attempt}.png"
                            )
                            job_monitor, image_record, image_metric = (
                                _run_gemini_image_attempt(
                                    scene=scene,
                                    image_path=attempt_path,
                                    directed_prompt=directed_prompt,
                                    image_style=image_style,
                                    style_label=style_label,
                                    quality_preset_key=quality_preset_key,
                                    scene_seed=attempt_seed,
                                    visual_bible=visual_bible,
                                    attempt=attempt,
                                    reference_image_path=reference_image_path,
                                )
                            )
                            runpod_jobs.append(job_monitor)
                            if not image_record or not image_metric:
                                continue

                            quality_score = _safe_float(
                                image_metric.get("quality_score"),
                                0.0,
                            )
                            if (
                                best_candidate is None
                                or quality_score > best_candidate[0]
                            ):
                                best_candidate = (
                                    quality_score,
                                    attempt_path,
                                    image_record,
                                    image_metric,
                                )

                            accepted = bool(image_metric.get("semantic_accepted"))
                            if accepted:
                                if attempt_path != image_path:
                                    os.replace(attempt_path, image_path)
                                    image_record["image_path"] = image_path
                                    image_metric["path"] = image_path
                                scene_images.append(image_record)
                                image_metrics.append(image_metric)
                                if reference_image_path is None:
                                    reference_image_path = image_path
                                print(
                                    "✅ Imagem Gemini/Nano Banana "
                                    f"aceita: cena {scene['scene_id']} "
                                    f"(tentativa {attempt}, score={image_metric.get('quality_score')})"
                                )
                                selected_scene = True
                                break

                            retry_instruction = str(
                                image_metric.get("semantic_retry_prompt")
                                or "Remove duplicated characters, wrong objects, missing required objects, style drift and visible text. Obey the scene contract exactly."
                            )
                            print(
                                "🔁 QA visual reprovou a cena "
                                f"{scene['scene_id']} no Gemini na tentativa {attempt}; regenerando."
                            )
                        if not selected_scene and best_candidate:
                            _, best_path, image_record, image_metric = best_candidate
                            if _strict_image_semantic_gate():
                                image_metrics.append(
                                    _semantic_gate_blocked_metric(
                                        scene,
                                        image_style,
                                        quality_preset_key,
                                        "gemini_image",
                                        image_metric,
                                    )
                                )
                                print(
                                    "⛔ Cena bloqueada pelo QA semântico Gemini: "
                                    f"cena {scene['scene_id']} "
                                    f"(melhor tentativa={image_metric.get('attempt')}, "
                                    f"semantic_score={image_metric.get('semantic_score')})"
                                )
                                continue
                            else:
                                if best_path != image_path:
                                    os.replace(best_path, image_path)
                                    image_record["image_path"] = image_path
                                    image_metric["path"] = image_path
                                scene_images.append(image_record)
                                image_metrics.append(image_metric)
                                if reference_image_path is None:
                                    reference_image_path = image_path
                                print(
                                    "✅ Imagem Gemini/Nano Banana mantida com melhor score: "
                                    f"cena {scene['scene_id']} "
                                    f"(tentativa {image_metric.get('attempt')}, "
                                    f"score={image_metric.get('quality_score')})"
                                )

                    if any(
                        img["scene_id"] == scene["scene_id"]
                        and img["generation_method"] == "gemini_image"
                        for img in scene_images
                    ):
                        continue

                    # Generate image using ComfyUI via RunPod Serverless
                    if runpod_api_key and runpod_endpoint_id:
                        retry_instruction = ""
                        best_candidate = None
                        selected_scene = False
                        for attempt in range(1, max_attempts + 1):
                            attempt_seed = _scene_seed(
                                session_id,
                                image_style,
                                f"{scene['scene_id']}:{attempt}",
                            )
                            directed_prompt = _build_image_prompt(
                                scene,
                                image_style,
                                visual_bible,
                                retry_instruction,
                            )
                            attempt_path = (
                                image_path
                                if attempt == max_attempts
                                else f"output/scene_{scene['scene_id']}_attempt_{attempt}.png"
                            )
                            job_monitor, image_record, image_metric = (
                                _run_comfyui_image_attempt(
                                    scene=scene,
                                    image_path=attempt_path,
                                    directed_prompt=directed_prompt,
                                    image_style=image_style,
                                    style_label=style_label,
                                    quality_preset_key=quality_preset_key,
                                    quality_preset=quality_preset,
                                    checkpoint_name=checkpoint_name,
                                    scene_seed=attempt_seed,
                                    visual_bible=visual_bible,
                                    runpod_endpoint_id=runpod_endpoint_id,
                                    runpod_api_key=runpod_api_key,
                                    runpod_gpu_usd_per_second=runpod_gpu_usd_per_second,
                                    attempt=attempt,
                                    reference_image_path=reference_image_path,
                                )
                            )
                            runpod_jobs.append(job_monitor)
                            if not image_record or not image_metric:
                                continue

                            quality_score = _safe_float(
                                image_metric.get("quality_score"),
                                0.0,
                            )
                            if (
                                best_candidate is None
                                or quality_score > best_candidate[0]
                            ):
                                best_candidate = (
                                    quality_score,
                                    attempt_path,
                                    image_record,
                                    image_metric,
                                )

                            accepted = bool(image_metric.get("semantic_accepted"))
                            if accepted:
                                if attempt_path != image_path:
                                    os.replace(attempt_path, image_path)
                                    image_record["image_path"] = image_path
                                    image_metric["path"] = image_path
                                scene_images.append(image_record)
                                image_metrics.append(image_metric)
                                if reference_image_path is None:
                                    reference_image_path = image_path
                                print(
                                    "✅ Imagem ComfyUI REAL "
                                    f"aceita: cena {scene['scene_id']} "
                                    f"(tentativa {attempt}, score={image_metric.get('quality_score')})"
                                )
                                selected_scene = True
                                break

                            retry_instruction = str(
                                image_metric.get("semantic_retry_prompt")
                                or "Remove all visible text, captions, borders, watermarks, duplicated characters and style drift. Keep the same protagonist and selected film style."
                            )
                            print(
                                "🔁 QA visual reprovou a cena "
                                f"{scene['scene_id']} na tentativa {attempt}; regenerando."
                            )
                        if not selected_scene and best_candidate:
                            _, best_path, image_record, image_metric = best_candidate
                            if _strict_image_semantic_gate():
                                image_metrics.append(
                                    _semantic_gate_blocked_metric(
                                        scene,
                                        image_style,
                                        quality_preset_key,
                                        "comfyui",
                                        image_metric,
                                    )
                                )
                                print(
                                    "⛔ Cena bloqueada pelo QA semântico ComfyUI: "
                                    f"cena {scene['scene_id']} "
                                    f"(melhor tentativa={image_metric.get('attempt')}, "
                                    f"semantic_score={image_metric.get('semantic_score')})"
                                )
                                continue
                            else:
                                if best_path != image_path:
                                    os.replace(best_path, image_path)
                                    image_record["image_path"] = image_path
                                    image_metric["path"] = image_path
                                scene_images.append(image_record)
                                image_metrics.append(image_metric)
                                if reference_image_path is None:
                                    reference_image_path = image_path
                                print(
                                    "✅ Imagem ComfyUI REAL mantida com melhor score: "
                                    f"cena {scene['scene_id']} "
                                    f"(tentativa {image_metric.get('attempt')}, "
                                    f"score={image_metric.get('quality_score')})"
                                )

                    # Verifica se a imagem já foi gerada com sucesso acima; se não, cai no mock
                    if any(
                        img["scene_id"] == scene["scene_id"]
                        and img["generation_method"] == "comfyui"
                        for img in scene_images
                    ):
                        continue

                    # Fallback mock generation se ComfyUI falhar
                    print(f"💡 Usando fallback PNG real para cena {scene['scene_id']}")
                    _write_fallback_scene_image(image_path, scene, style_label)

                    scene_images.append(
                        {
                            "scene_id": scene["scene_id"],
                            "image_path": image_path,
                            "prompt": scene["prompt"],
                            "style": image_style,
                            "quality_preset": quality_preset_key,
                            "checkpoint": checkpoint_name,
                            "duration": scene.get("duration", 6),
                            "camera_motion": scene.get(
                                "camera_motion",
                                _motion_plan(scene)["description"],
                            ),
                            "generation_method": "mock",
                        }
                    )
                    technical_metrics = _probe_image_quality(image_path, scene=scene)
                    semantic_metrics = {
                        "semantic_score": 0,
                        "semantic_qa_enabled": _semantic_qa_enabled(),
                        "accepted": False,
                        "issues": ["mock_image"],
                        "retry_prompt": "",
                        "model": None,
                    }
                    image_metrics.append(
                        {
                            "scene_id": scene["scene_id"],
                            "generation_method": "mock",
                            "style": image_style,
                            "quality_preset": quality_preset_key,
                            "checkpoint": checkpoint_name,
                            **_combine_image_quality(
                                technical_metrics,
                                semantic_metrics,
                            ),
                        }
                    )

                    print(f"✅ Imagem gerada (mock): cena {scene['scene_id']}")

                except (
                    OSError,
                    ValueError,
                    TypeError,
                    KeyError,
                    RuntimeError,
                    subprocess.SubprocessError,
                ) as e:
                    print(f"⚠️ Erro ao gerar imagem para cena {scene['scene_id']}: {e}")
                    # Continue with next scene

            visual_consistency = _evaluate_image_set_consistency(
                scene_images,
                visual_bible,
            )
            repair_scene = _select_consistency_repair_scene(
                scenes[:3],
                visual_consistency,
            )
            if (
                repair_scene
                and image_provider in {"gemini", "comfyui"}
                and scene_images
                and _semantic_qa_enabled()
                and (
                    image_provider == "gemini"
                    or (runpod_api_key and runpod_endpoint_id)
                )
            ):
                repair_scene_id = repair_scene.get("scene_id")
                original_consistency_score = _safe_int(
                    visual_consistency.get("consistency_score"),
                    0,
                )
                consistency_issues = {
                    str(issue)
                    for issue in visual_consistency.get("issues", [])
                    if issue
                }
                consistency_notes = str(
                    visual_consistency.get("style_notes", "")
                ).lower()
                identity_repair = (
                    "minor_facial_variance" in consistency_issues
                    or "feições" in consistency_notes
                    or "penteado" in consistency_notes
                    or "face" in consistency_notes
                    or "facial" in consistency_notes
                )
                repair_reference_image_path = (
                    str(scene_images[0].get("image_path") or "")
                    if identity_repair and scene_images
                    else None
                )
                best_repair: (
                    tuple[
                        int,
                        str,
                        Dict[str, Any],
                        Dict[str, Any],
                        Dict[str, Any],
                    ]
                    | None
                ) = None
                consistency_feedback = (
                    f"Sequence consistency QA failed with score "
                    f"{visual_consistency.get('consistency_score')} below "
                    f"{visual_consistency.get('min_score')}. "
                    f"Issues: {', '.join(str(issue) for issue in visual_consistency.get('issues', []) if issue) or 'style/composition mismatch'}. "
                    f"Notes: {visual_consistency.get('style_notes') or ''}. "
                    "Regenerate this scene as a clearly distinct shot in the same film: change camera angle, body angle, blocking, background geography and foreground object placement. "
                    "Preserve Alice identity and wardrobe, but do not copy any prior scene pose, tree-root framing, garden facade, foreground layout or camera distance. "
                    "If the issue mentions facial variance, preserve the exact same Alice face family, hair length, hair parting, age and ivory dress from the first frame while changing only the scene setting."
                )
                repair_attempts = max(1, min(2, max_attempts))
                print(
                    "🔁 QA de consistência reprovou o conjunto; "
                    f"regenerando cena {repair_scene_id} para variar composição."
                )
                for repair_attempt in range(1, repair_attempts + 1):
                    repair_seed = _scene_seed(
                        session_id,
                        image_style,
                        f"{image_provider}:{repair_scene_id}:consistency_repair:{repair_attempt}",
                    )
                    repair_path = f"output/scene_{repair_scene_id}_consistency_repair_{repair_attempt}.png"
                    directed_prompt = _build_image_prompt(
                        repair_scene,
                        image_style,
                        visual_bible,
                        consistency_feedback,
                    )
                    if image_provider == "gemini":
                        job_monitor, image_record, image_metric = (
                            _run_gemini_image_attempt(
                                scene=repair_scene,
                                image_path=repair_path,
                                directed_prompt=directed_prompt,
                                image_style=image_style,
                                style_label=style_label,
                                quality_preset_key=quality_preset_key,
                                scene_seed=repair_seed,
                                visual_bible=visual_bible,
                                attempt=max_attempts + repair_attempt,
                                reference_image_path=repair_reference_image_path,
                            )
                        )
                    else:
                        job_monitor, image_record, image_metric = (
                            _run_comfyui_image_attempt(
                                scene=repair_scene,
                                image_path=repair_path,
                                directed_prompt=directed_prompt,
                                image_style=image_style,
                                style_label=style_label,
                                quality_preset_key=quality_preset_key,
                                quality_preset=quality_preset,
                                checkpoint_name=checkpoint_name,
                                scene_seed=repair_seed,
                                visual_bible=visual_bible,
                                runpod_endpoint_id=runpod_endpoint_id,
                                runpod_api_key=runpod_api_key,
                                runpod_gpu_usd_per_second=runpod_gpu_usd_per_second,
                                attempt=max_attempts + repair_attempt,
                                reference_image_path=repair_reference_image_path,
                            )
                        )
                    runpod_jobs.append(job_monitor)
                    if (
                        not image_record
                        or not image_metric
                        or not bool(image_metric.get("semantic_accepted"))
                    ):
                        consistency_feedback += " The previous repair attempt also failed semantic QA; obey the scene contract literally."
                        continue

                    candidate_images = _replace_scene_asset(
                        scene_images,
                        repair_scene_id,
                        image_record,
                    )
                    candidate_consistency = _evaluate_image_set_consistency(
                        candidate_images,
                        visual_bible,
                    )
                    candidate_score = _safe_int(
                        candidate_consistency.get("consistency_score"),
                        0,
                    )
                    if best_repair is None or candidate_score > best_repair[0]:
                        best_repair = (
                            candidate_score,
                            repair_path,
                            image_record,
                            image_metric,
                            candidate_consistency,
                        )
                    print(
                        "🔎 Reparo de consistência "
                        f"cena {repair_scene_id}, tentativa {repair_attempt}: "
                        f"score={candidate_score}, accepted={candidate_consistency.get('accepted')}"
                    )
                    if bool(candidate_consistency.get("accepted")):
                        break
                    consistency_feedback += f" Previous repair still scored {candidate_score}; make the next shot more compositionally distinct."

                if best_repair and best_repair[0] > original_consistency_score:
                    _, best_path, image_record, image_metric, visual_consistency = (
                        best_repair
                    )
                    final_path = f"output/scene_{repair_scene_id}_image.png"
                    if best_path != final_path:
                        os.replace(best_path, final_path)
                    image_record["image_path"] = final_path
                    image_metric["path"] = final_path
                    image_metric["consistency_repair"] = True
                    scene_images = _replace_scene_asset(
                        scene_images,
                        repair_scene_id,
                        image_record,
                    )
                    image_metrics = _replace_scene_asset(
                        image_metrics,
                        repair_scene_id,
                        image_metric,
                    )
                    print(
                        "✅ Reparo de consistência aplicado: "
                        f"cena {repair_scene_id}, score={visual_consistency.get('consistency_score')}"
                    )
                elif repair_scene:
                    print(
                        "⚠️ Reparo de consistência não melhorou o conjunto; "
                        "mantendo melhores imagens originais."
                    )

            state.update(
                {
                    "scene_images": scene_images,
                    "images_count": len(scene_images),
                    "runpod_jobs": runpod_jobs,
                    "quality_metrics": {
                        **state.get("quality_metrics", {}),
                        "images": image_metrics,
                        "visual_consistency": visual_consistency,
                    },
                    "current_step": "images_generated",
                }
            )

            return state

        def generate_audio(state: Open3DAgentState) -> Open3DAgentState:
            """Generate audio narration using ElevenLabs"""
            scenes = state.get("scenes", [])

            print("🎙️ Gerando áudio com ElevenLabs...")

            audio_files = []
            audio_metrics = []
            voice_metrics = []
            elevenlabs_usd_per_1k_chars = _safe_float(
                os.getenv("ELEVENLABS_USD_PER_1K_CHARS", "0.30")
            )
            estimated_elevenlabs_cost = 0.0
            elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
            elevenlabs_remaining_chars = (
                _elevenlabs_remaining_characters(elevenlabs_api_key)
                if elevenlabs_api_key
                else None
            )
            elevenlabs_starting_chars = elevenlabs_remaining_chars
            if elevenlabs_api_key and elevenlabs_remaining_chars is not None:
                print(
                    "📊 ElevenLabs caracteres restantes: "
                    f"{elevenlabs_remaining_chars}"
                )

            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎤 Gerando áudio para cena {scene['scene_id']}...")

                    # Create output directory
                    os.makedirs("output", exist_ok=True)
                    audio_path = f"output/scene_{scene['scene_id']}_audio.mp3"

                    # Generate premium narration using ElevenLabs
                    narration_text = _premium_audio_narration(scene)
                    audio_direction = _premium_audio_direction(scene)
                    text_characters = len(narration_text)
                    failure_reason = ""

                    if elevenlabs_api_key:
                        print(
                            f"🔑 ElevenLabs API Key: {'✅ Configurada' if elevenlabs_api_key else '❌ Não encontrada'}"
                        )

                        print(f"📝 Texto para narração: {narration_text[:100]}...")

                        # ElevenLabs API call
                        headers = {
                            "Accept": "audio/mpeg",
                            "Content-Type": "application/json",
                            "xi-api-key": elevenlabs_api_key,
                        }

                        data = {
                            "text": narration_text,
                            "model_id": os.getenv(
                                "ELEVENLABS_MODEL_ID",
                                "eleven_multilingual_v2",
                            ),
                            "voice_settings": _elevenlabs_voice_settings(),
                        }

                        voice_id, voice_role = _elevenlabs_voice_id_for_scene(scene)
                        voice_url = (
                            "https://api.elevenlabs.io/v1/text-to-speech/" f"{voice_id}"
                        )

                        if (
                            elevenlabs_remaining_chars is not None
                            and text_characters > elevenlabs_remaining_chars
                        ):
                            failure_reason = (
                                "elevenlabs_insufficient_characters:"
                                f"needed={text_characters},remaining={elevenlabs_remaining_chars}"
                            )
                            print(
                                "⚠️ Quota ElevenLabs insuficiente para a cena: "
                                f"{text_characters} chars necessários, "
                                f"{elevenlabs_remaining_chars} restantes"
                            )
                        else:
                            print("🎤 Chamando ElevenLabs API...")
                            try:
                                response = requests.post(
                                    voice_url,
                                    headers=headers,
                                    json=data,
                                    timeout=45,
                                )

                                print(f"📊 Status Code: {response.status_code}")
                                if response.status_code != 200:
                                    failure_reason = (
                                        f"elevenlabs_http_{response.status_code}:"
                                        f"{_response_error_detail(response)}"
                                    )
                                    print(
                                        "❌ Resposta ElevenLabs: "
                                        f"{_response_error_detail(response)}"
                                    )

                                if response.status_code == 200:
                                    # Save real audio
                                    raw_audio_path = str(
                                        Path(audio_path).with_name(
                                            f"{Path(audio_path).stem}_raw.mp3"
                                        )
                                    )
                                    with open(raw_audio_path, "wb") as f:
                                        f.write(response.content)

                                    media_quality = _enhance_premium_audio(
                                        raw_audio_path,
                                        audio_path,
                                        scene,
                                    )
                                    if not bool(media_quality.get("valid")):
                                        shutil.copyfile(raw_audio_path, audio_path)
                                        media_quality = _probe_media_quality(
                                            audio_path, "audio"
                                        )
                                        media_quality.update(
                                            {
                                                "enhanced": False,
                                                "loudness": _measure_audio_loudness(
                                                    audio_path
                                                ),
                                                "waveform": _audio_waveform_samples(
                                                    audio_path
                                                ),
                                            }
                                        )
                                    try:
                                        Path(raw_audio_path).unlink(missing_ok=True)
                                    except OSError:
                                        pass
                                    media_quality = _audio_quality_gate(
                                        media_quality,
                                        narration_text,
                                        "elevenlabs",
                                    )
                                    if bool(media_quality.get("valid")):
                                        audio_files.append(
                                            {
                                                "scene_id": scene["scene_id"],
                                                "audio_path": audio_path,
                                                "text": narration_text,
                                                "voice_direction": audio_direction,
                                                "voice_id": voice_id,
                                                "voice_role": voice_role,
                                                "generation_method": "elevenlabs",
                                            }
                                        )
                                        audio_metrics.append(
                                            {
                                                "scene_id": scene["scene_id"],
                                                "generation_method": "elevenlabs",
                                                "voice_direction": audio_direction,
                                                "voice_id": voice_id,
                                                "voice_role": voice_role,
                                                **media_quality,
                                            }
                                        )
                                        voice_metrics.append(
                                            {
                                                "scene_id": scene["scene_id"],
                                                "voice_id": voice_id,
                                                "voice_role": voice_role,
                                                "model_id": data["model_id"],
                                                "text_characters": text_characters,
                                                "voice_direction": audio_direction,
                                                "premium_audio": media_quality.get(
                                                    "premium_audio",
                                                    False,
                                                ),
                                                "quality_score": media_quality.get(
                                                    "quality_score",
                                                    0,
                                                ),
                                                "issues": media_quality.get(
                                                    "issues",
                                                    [],
                                                ),
                                            }
                                        )
                                        estimated_elevenlabs_cost += (
                                            text_characters
                                            / 1000
                                            * elevenlabs_usd_per_1k_chars
                                        )
                                        if elevenlabs_remaining_chars is not None:
                                            elevenlabs_remaining_chars = max(
                                                0,
                                                elevenlabs_remaining_chars
                                                - text_characters,
                                            )
                                        print(
                                            "✅ Áudio ElevenLabs REAL gerado: "
                                            f"cena {scene['scene_id']} "
                                            f"({os.path.getsize(audio_path)} bytes)"
                                        )
                                        continue
                                    failure_reason = (
                                        "elevenlabs_invalid_audio:"
                                        f"{','.join(media_quality.get('issues', []))}"
                                    )
                                    print("⚠️ Arquivo ElevenLabs não é áudio válido")

                            except (
                                OSError,
                                ValueError,
                                requests.RequestException,
                            ) as e:
                                failure_reason = (
                                    f"elevenlabs_request_error:{type(e).__name__}"
                                )
                                print(f"⚠️ Erro na chamada ElevenLabs: {e}")
                    else:
                        failure_reason = "elevenlabs_api_key_missing"
                        print(
                            "❌ ElevenLabs API Key não encontrada nas variáveis de ambiente"
                        )

                    print("🎙️ Usando fallback local de TTS para áudio válido...")
                    media_quality = _generate_local_tts_audio(
                        narration_text,
                        audio_path,
                    )
                    generation_method = (
                        "local_tts" if media_quality.get("valid") else "failed"
                    )
                    media_quality = _audio_quality_gate(
                        media_quality,
                        narration_text,
                        generation_method,
                    )
                    if bool(media_quality.get("valid")):
                        audio_files.append(
                            {
                                "scene_id": scene["scene_id"],
                                "audio_path": audio_path,
                                "text": narration_text,
                                "voice_direction": audio_direction,
                                "voice_id": os.getenv(
                                    "AUDIO_LOCAL_TTS_VOICE",
                                    "Luciana",
                                ),
                                "generation_method": "local_tts",
                                "fallback_reason": failure_reason,
                            }
                        )
                        print(
                            "✅ Áudio local válido gerado: "
                            f"cena {scene['scene_id']} "
                            f"({os.path.getsize(audio_path)} bytes)"
                        )
                    else:
                        print(
                            "❌ Nenhum áudio válido gerado para cena "
                            f"{scene['scene_id']}: {failure_reason}"
                        )
                    audio_metrics.append(
                        {
                            "scene_id": scene["scene_id"],
                            "generation_method": generation_method,
                            "fallback_reason": failure_reason,
                            "voice_direction": audio_direction,
                            **media_quality,
                        }
                    )
                    voice_metrics.append(
                        {
                            "scene_id": scene["scene_id"],
                            "voice_id": (
                                os.getenv("AUDIO_LOCAL_TTS_VOICE", "Luciana")
                                if generation_method == "local_tts"
                                else "none"
                            ),
                            "model_id": generation_method,
                            "text_characters": text_characters,
                            "voice_direction": audio_direction,
                            "premium_audio": media_quality.get(
                                "premium_audio",
                                False,
                            ),
                            "quality_score": media_quality.get("quality_score", 0),
                            "issues": media_quality.get("issues", []),
                            "fallback_reason": failure_reason,
                        }
                    )

                except (
                    OSError,
                    ValueError,
                    TypeError,
                    KeyError,
                    RuntimeError,
                    requests.RequestException,
                ) as e:
                    print(f"⚠️ Erro ao gerar áudio para cena {scene['scene_id']}: {e}")
                    # Continue with next scene

            state.update(
                {
                    "audio_files": audio_files,
                    "audio_count": len(audio_files),
                    "quality_metrics": {
                        **state.get("quality_metrics", {}),
                        "audio": audio_metrics,
                        "voices": voice_metrics,
                    },
                    "cost_estimate": {
                        **state.get("cost_estimate", {}),
                        "elevenlabs_usd": round(estimated_elevenlabs_cost, 6),
                        "elevenlabs_characters_remaining_start": elevenlabs_starting_chars,
                        "elevenlabs_characters_remaining_end": elevenlabs_remaining_chars,
                    },
                    "current_step": "audio_generated",
                }
            )

            print(f"✅ {len(audio_files)} áudios gerados")
            return state

        def compile_video(state: Open3DAgentState) -> Open3DAgentState:
            """Compile final video using real provider clips with FFmpeg fallback."""
            scene_images = state.get("scene_images", [])
            audio_files = state.get("audio_files", [])
            runpod_jobs = list(state.get("runpod_jobs", []))
            scene_videos: List[Dict[str, Any]] = []
            video_provider = os.getenv("VIDEO_GENERATION_PROVIDER", "runway").lower()
            used_runway = False

            print("🎬 Compilando vídeo final com FFmpeg...")

            video_path = "output/final_video.mp4"

            try:
                # Create output directory
                os.makedirs("output", exist_ok=True)

                # Check if FFmpeg is available
                try:
                    subprocess.run(
                        ["ffmpeg", "-version"], capture_output=True, check=True
                    )
                    ffmpeg_available = True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    ffmpeg_available = False
                    print("⚠️ FFmpeg não disponível, usando mock")

                if ffmpeg_available and scene_images:
                    print("🔧 Usando FFmpeg real com animação de câmera...")

                    clip_paths = []
                    temporary_clip_paths = []
                    for index, img in enumerate(scene_images, 1):
                        img_path = img["image_path"]
                        if not (
                            os.path.exists(img_path)
                            and os.path.getsize(img_path) > 1000
                        ):
                            continue

                        audio_duration = _scene_audio_duration(
                            audio_files,
                            img.get("scene_id"),
                        )
                        duration = max(
                            3.0,
                            audio_duration,
                            _safe_float(img.get("duration"), 5.0),
                        )
                        if video_provider == "runway":
                            runway_clip_path = (
                                f"output/scene_{img['scene_id']}_runway.mp4"
                            )
                            job_monitor, runway_ok = _generate_runway_clip(
                                img,
                                runway_clip_path,
                                duration,
                            )
                            runpod_jobs.append(job_monitor)
                            if runway_ok and os.path.exists(runway_clip_path):
                                clip_paths.append(runway_clip_path)
                                used_runway = True
                                scene_videos.append(
                                    {
                                        "scene_id": img.get("scene_id", index),
                                        "video_path": runway_clip_path,
                                        "provider": "runway",
                                        "job_id": job_monitor.get("job_id"),
                                        "duration": duration,
                                        "quality_score": job_monitor.get(
                                            "quality_score",
                                            0,
                                        ),
                                    }
                                )
                                continue
                            print(
                                "⚠️ Runway indisponível para cena "
                                f"{img.get('scene_id')}: {job_monitor.get('error')}"
                            )

                        clip_path = f"output/scene_{img['scene_id']}_motion.mp4"
                        scene_for_motion = {
                            "scene_id": img.get("scene_id", index),
                            "camera_motion": img.get("camera_motion", ""),
                        }
                        motion_filter = _ffmpeg_zoompan_filter(
                            scene_for_motion,
                            duration,
                        )
                        cmd = [
                            "ffmpeg",
                            "-y",
                            "-loop",
                            "1",
                            "-i",
                            img_path,
                            "-vf",
                            motion_filter,
                            "-t",
                            str(duration),
                            "-r",
                            "30",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "slow",
                            "-crf",
                            "18",
                            "-profile:v",
                            "high",
                            "-pix_fmt",
                            "yuv420p",
                            "-movflags",
                            "+faststart",
                            clip_path,
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0 and os.path.exists(clip_path):
                            clip_paths.append(clip_path)
                            temporary_clip_paths.append(clip_path)
                            media_quality = _probe_media_quality(clip_path, "video")
                            scene_videos.append(
                                {
                                    "scene_id": img.get("scene_id", index),
                                    "video_path": clip_path,
                                    "provider": "ffmpeg_camera_motion",
                                    "duration": duration,
                                    "quality_score": media_quality.get(
                                        "quality_score",
                                        0,
                                    ),
                                }
                            )
                        else:
                            print(
                                "⚠️ Erro ao animar cena "
                                f"{img.get('scene_id')}: {result.stderr[:500]}"
                            )

                    filelist_path = "output/filelist.txt"
                    with open(filelist_path, "w") as f:
                        for clip_path in clip_paths:
                            f.write(f"file '{os.path.abspath(clip_path)}'\n")

                    # Compile video with images
                    if (
                        os.path.exists(filelist_path)
                        and os.path.getsize(filelist_path) > 0
                    ):
                        temp_video = "output/temp_video.mp4"

                        # Create video from images
                        cmd = [
                            "ffmpeg",
                            "-y",  # Overwrite output file
                            "-f",
                            "concat",  # Concat demuxer
                            "-safe",
                            "0",  # Allow unsafe paths
                            "-i",
                            filelist_path,  # Input file list
                            "-c:v",
                            "copy",  # Clips are already encoded consistently
                            "-pix_fmt",
                            "yuv420p",  # Pixel format for compatibility
                            temp_video,
                        ]

                        result = subprocess.run(cmd, capture_output=True, text=True)

                        if result.returncode == 0 and audio_files:
                            # Concatenate every valid scene narration before muxing.
                            audio_list_path = "output/audio_filelist.txt"
                            valid_audio_paths = [
                                audio["audio_path"]
                                for audio in audio_files
                                if os.path.exists(audio.get("audio_path", ""))
                                and os.path.getsize(audio["audio_path"]) > 1000
                            ]
                            combined_audio_path = "output/combined_audio.m4a"
                            with open(audio_list_path, "w") as audio_list:
                                for audio_path in valid_audio_paths:
                                    audio_list.write(
                                        f"file '{os.path.abspath(audio_path)}'\n"
                                    )

                            if valid_audio_paths:
                                audio_cmd = [
                                    "ffmpeg",
                                    "-y",
                                    "-f",
                                    "concat",
                                    "-safe",
                                    "0",
                                    "-i",
                                    audio_list_path,
                                    "-af",
                                    f"loudnorm=I={_audio_loudness_target_lufs():.1f}:TP=-1.5:LRA=11",
                                    "-c:a",
                                    "aac",
                                    "-b:a",
                                    "160k",
                                    combined_audio_path,
                                ]
                                audio_result = subprocess.run(
                                    audio_cmd,
                                    capture_output=True,
                                    text=True,
                                )
                                if audio_result.returncode != 0:
                                    print(
                                        "⚠️ Erro ao concatenar áudios: "
                                        f"{audio_result.stderr[:500]}"
                                    )
                                    combined_audio_path = valid_audio_paths[0]

                                cmd = [
                                    "ffmpeg",
                                    "-y",
                                    "-i",
                                    temp_video,  # Video input
                                    "-i",
                                    combined_audio_path,  # Audio input
                                    "-c:v",
                                    "copy",  # Copy video stream
                                    "-c:a",
                                    "aac",  # Audio codec
                                    "-shortest",  # Match shortest stream
                                    video_path,
                                ]

                                result = subprocess.run(
                                    cmd, capture_output=True, text=True
                                )

                                if result.returncode == 0:
                                    # Clean up temp file
                                    os.remove(temp_video)
                                    for clip_path in temporary_clip_paths:
                                        if os.path.exists(clip_path):
                                            os.remove(clip_path)
                                    for temp_path in (
                                        audio_list_path,
                                        "output/combined_audio.m4a",
                                    ):
                                        if os.path.exists(temp_path):
                                            os.remove(temp_path)
                                    print(
                                        f"✅ Vídeo FFmpeg compilado com áudio: {video_path}"
                                    )
                                else:
                                    print(f"⚠️ Erro ao adicionar áudio: {result.stderr}")
                                    # Use video without audio
                                    os.rename(temp_video, video_path)
                            else:
                                # No valid audio found, use video only
                                os.rename(temp_video, video_path)
                                print(
                                    f"✅ Vídeo FFmpeg compilado (sem áudio): {video_path}"
                                )
                        else:
                            print(f"⚠️ Erro na compilação FFmpeg: {result.stderr}")
                            # Fallback to mock
                            raise RuntimeError("FFmpeg compilation failed")
                    else:
                        print("⚠️ Nenhuma imagem válida encontrada para FFmpeg")
                        raise RuntimeError("No valid images for FFmpeg")

                else:
                    # Fallback to mock
                    raise RuntimeError("FFmpeg not available or no images")

                state.update(
                    {
                        "video_path": video_path,
                        "video_size": (
                            os.path.getsize(video_path)
                            if os.path.exists(video_path)
                            else 0
                        ),
                        "generation_method": (
                            "runway_image_to_video"
                            if used_runway
                            else "ffmpeg_camera_motion"
                        ),
                        "scene_videos": scene_videos,
                        "runpod_jobs": runpod_jobs,
                        "current_step": "video_compiled",
                        "status": "completed",
                    }
                )

            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                RuntimeError,
                subprocess.SubprocessError,
            ) as e:
                print(f"⚠️ FFmpeg falhou: {e}")
                print("💡 Usando mock de vídeo")

                # Fallback mock generation
                with open(video_path, "w") as f:
                    f.write(
                        f"Mock video compiled from {len(scene_images)} images and {len(audio_files)} audio files"
                    )

                state.update(
                    {
                        "video_path": video_path,
                        "video_size": os.path.getsize(video_path),
                        "generation_method": "mock",
                        "scene_videos": scene_videos,
                        "runpod_jobs": runpod_jobs,
                        "current_step": "video_compiled",
                        "status": "completed",
                    }
                )

            quality_metrics = state.get("quality_metrics", {})
            image_metrics = quality_metrics.get("images", [])
            audio_metrics = quality_metrics.get("audio", [])
            video_metrics = _probe_media_quality(video_path, "video")
            aggregate_quality = _aggregate_quality(
                image_metrics=image_metrics,
                audio_metrics=audio_metrics,
                video_metrics=video_metrics,
            )
            cost_estimate = {
                **state.get("cost_estimate", {}),
                "runpod_usd": round(
                    sum(
                        _safe_float(job.get("estimated_cost_usd"))
                        for job in runpod_jobs
                        if job.get("provider") not in {"gemini", "runway"}
                    ),
                    6,
                ),
                "gemini_image_usd": round(
                    sum(
                        _safe_float(job.get("estimated_cost_usd"))
                        for job in runpod_jobs
                        if job.get("provider") == "gemini"
                    ),
                    6,
                ),
                "runway_usd": round(
                    sum(
                        _safe_float(job.get("estimated_cost_usd"))
                        for job in runpod_jobs
                        if job.get("provider") == "runway"
                    ),
                    6,
                ),
            }
            cost_estimate["total_usd"] = round(
                _safe_float(cost_estimate.get("llm_usd"))
                + _safe_float(cost_estimate.get("runpod_usd"))
                + _safe_float(cost_estimate.get("gemini_image_usd"))
                + _safe_float(cost_estimate.get("elevenlabs_usd"))
                + _safe_float(cost_estimate.get("runway_usd")),
                6,
            )
            state.update(
                {
                    "quality_metrics": {
                        **quality_metrics,
                        **aggregate_quality,
                    },
                    "cost_estimate": cost_estimate,
                }
            )

            print(f"✅ Vídeo finalizado: {video_path}")
            return state

        # Create workflow graph
        workflow = StateGraph(Open3DAgentState)

        # Add nodes
        workflow.add_node("extract_story", extract_story)
        workflow.add_node("generate_scenes", generate_scenes)
        workflow.add_node("generate_images", generate_images)
        workflow.add_node("generate_audio", generate_audio)
        workflow.add_node("compile_video", compile_video)

        # Set entry point
        workflow.set_entry_point("extract_story")

        # Add edges
        workflow.add_edge("extract_story", "generate_scenes")
        workflow.add_edge("generate_scenes", "generate_images")
        workflow.add_edge("generate_images", "generate_audio")
        workflow.add_edge("generate_audio", "compile_video")
        workflow.add_edge("compile_video", END)

        # Compile workflow
        compiled_workflow = workflow.compile()

        print("✅ Workflow LangGraph criado com sucesso!")
        return compiled_workflow

    except ImportError as e:
        print(f"❌ Erro ao importar dependências LangGraph: {e}")
        print("💡 Certifique-se de que langgraph está instalado")
        return None
    except (ValueError, TypeError, RuntimeError) as e:
        print(f"❌ Erro ao criar workflow: {e}")
        return None


@dataclass
class WorkflowConfig:
    """Configuration for Open3D workflow"""

    max_iterations: int = 10
    enable_visualization: bool = True
    output_format: str = "mp4"
