"""Validated dramatic scene contracts for dialogue-driven animated films."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Mapping, Sequence, TypedDict


class DialogueTurn(TypedDict, total=False):
    turn_id: str
    speaker_id: str
    speaker_name: str
    text_pt_br: str
    emotion: str
    delivery: str
    action: str
    addressee_id: str | None
    mode: str
    lip_sync_required: bool


NARRATOR_ALIASES = frozenset(
    {
        "narrador",
        "narradora",
        "narrator",
        "voice_over",
        "voiceover",
        "voz_off",
        "voz_em_off",
    }
)

_ENGLISH_DIALOGUE_MARKERS = (
    " the ",
    " and ",
    " you ",
    " are ",
    " is ",
    " with ",
    " what ",
    " where ",
    " look ",
    " come ",
    " let's ",
    " don't ",
)

_DIALOGUE_VISUAL_ANCHORS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("açucareiro", "acucareiro"), ("açucareiro", "acucareiro", "sugar bowl")),
    (("ratinho", "rato branco"), ("ratinho", "rato branco", "white mouse")),
    (("formigueiro", "formigas"), ("formigueiro", "formigas", "anthill", "ants")),
    (("gatinho", "gatinhos", "gato"), ("gatinho", "gatinhos", "gato", "kitten", "cat")),
    (("porta",), ("porta", "door")),
    (("xadrez",), ("xadrez", "chess")),
    (("toca", "coelho"), ("toca", "coelho", "rabbit hole", "rabbit")),
)

_LEGACY_VISUAL_PT_BR = {
    "alice approximately 10 years old": "Alice com cerca de 10 anos",
    "adult male ludovico mathematics professor": "Ludovico, professor adulto de matemática",
    "modest ivory-white victorian day dress": "vestido vitoriano diurno modesto em marfim",
    "ivory-white day dress": "vestido diurno em marfim",
    "dark charcoal frock coat": "sobrecasaca em carvão escuro",
    "giant ancient beech tree roots": "raízes gigantes de uma faia antiga",
    "ancient beech trees": "faias antigas",
    "small anthill in the grass": "pequeno formigueiro na grama",
    "university garden": "jardim da universidade",
    "victorian tea table": "mesa de chá vitoriana",
    "tea table": "mesa de chá",
    "fully visible sugar bowl with open lid": "açucareiro totalmente visível com a tampa aberta",
    "small white mouse emerging from the sugar bowl": "pequeno ratinho branco saindo do açucareiro",
    "alice and ludovico upper bodies and hands visible": "torsos e mãos de Alice e Ludovico visíveis",
    "dark rabbit hole in a grassy embankment": "toca escura de coelho em um barranco gramado",
    "garden roots and grass": "raízes e grama do jardim",
    "dusty rose dress": "vestido rosa antigo",
    "half-open door": "porta entreaberta",
    "chessboard": "tabuleiro de xadrez",
    "chess pieces": "peças de xadrez",
    "wicker basket": "cesta de vime",
    "plum pies": "tortas de ameixa",
    "window": "janela",
}

_LEGACY_MAIN_ACTION_PT_BR = {
    (
        "alice searches the vast university garden for a safe place to hide the "
        "kittens, standing near ancient beech trees with thick, wrinkled trunks."
    ): (
        "Alice procura no vasto jardim da universidade um lugar seguro para "
        "esconder os gatinhos, perto de faias antigas com troncos grossos e "
        "enrugados."
    ),
    (
        "alice and her little sister edith peek through a half-open wooden door, "
        "spying on the adults having tea in the dining room."
    ): (
        "Alice e sua irmã mais nova, Edith, espiam pela porta de madeira "
        "entreaberta enquanto os adultos tomam chá na sala de jantar."
    ),
    (
        "professor ludovico sits at the tea table, turning his head with a warm, "
        "surprised smile as he notices the children peeking in."
    ): (
        "O professor Ludovico está sentado à mesa de chá e vira a cabeça com um "
        "sorriso caloroso e surpreso ao notar as meninas espiando."
    ),
    (
        "alice and professor ludovico sit across a wooden table playing a lively "
        "game of chess, surrounded by warm, cozy indoor lighting."
    ): (
        "Alice e o professor Ludovico jogam uma partida animada de xadrez em "
        "lados opostos de uma mesa de madeira, sob uma iluminação interna quente "
        "e acolhedora."
    ),
    (
        "alice stands near a window holding a basket of plum pies, looking out at "
        "the warm afternoon light, excited for tomorrow's boat trip."
    ): (
        "Alice está perto da janela com uma cesta de tortas de ameixa e observa "
        "a luz quente da tarde, animada para o passeio de barco do dia seguinte."
    ),
}


def normalize_character_id(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def is_narrator_role(value: object) -> bool:
    return normalize_character_id(value) in NARRATOR_ALIASES


def dialogue_turn_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "turn_id": {"type": "string", "minLength": 2},
            "speaker_id": {"type": "string", "minLength": 2},
            "speaker_name": {"type": "string", "minLength": 2},
            "text_pt_br": {"type": "string", "minLength": 2, "maxLength": 180},
            "emotion": {"type": "string", "minLength": 2},
            "delivery": {"type": "string", "minLength": 2},
            "action": {"type": "string", "minLength": 2},
            "addressee_id": {"type": ["string", "null"]},
            "mode": {"type": "string", "enum": ["dialogue", "internal_thought"]},
            "lip_sync_required": {"type": "boolean"},
        },
        "required": [
            "turn_id",
            "speaker_id",
            "speaker_name",
            "text_pt_br",
            "emotion",
            "delivery",
            "action",
            "addressee_id",
            "mode",
            "lip_sync_required",
        ],
    }


def scene_performance_schema() -> Dict[str, Any]:
    return {
        "location": {"type": "string", "minLength": 3},
        "main_action": {"type": "string", "minLength": 3},
        "dominant_emotion": {"type": "string", "minLength": 2},
        "characters_present": {
            "type": "array",
            "items": {"type": "string", "minLength": 2},
            "minItems": 1,
            "maxItems": 8,
        },
        "required_visual_elements": {
            "type": "array",
            "items": {"type": "string", "minLength": 2},
            "minItems": 1,
            "maxItems": 16,
        },
        "dialogue": {
            "type": "array",
            "items": dialogue_turn_schema(),
            "minItems": 1,
            "maxItems": 8,
        },
        "language": {"type": "string", "enum": ["pt-BR"]},
        "narration_allowed": {"type": "boolean", "enum": [False]},
    }


def _contains_english_dialogue(text: str) -> bool:
    padded = f" {text.lower()} "
    hits = sum(marker in padded for marker in _ENGLISH_DIALOGUE_MARKERS)
    return hits >= 2


def _canonical_dialogue(scene_text: str) -> List[DialogueTurn]:
    lowered = scene_text.lower()
    if any(
        term in lowered
        for term in ("açucareiro", "acucareiro", "sugar bowl", "ratinho")
    ):
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "ludovico",
                "speaker_name": "Ludovico",
                "text_pt_br": "Observe com atenção, Alice. O segredo está dentro do açucareiro.",
                "emotion": "divertido e misterioso",
                "delivery": "calmo, caloroso, com uma pausa antes de açucareiro",
                "action": "Ludovico ergue a tampa e olha para Alice",
                "addressee_id": "alice",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
            {
                "turn_id": "turn_2",
                "speaker_id": "alice",
                "speaker_name": "Alice",
                "text_pt_br": "Um ratinho branco! Como ele foi parar aí?",
                "emotion": "maravilhada",
                "delivery": "surpresa infantil, clara e natural",
                "action": "Alice se inclina para ver o ratinho e encara Ludovico",
                "addressee_id": "ludovico",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
        ]
    if any(term in lowered for term in ("formigueiro", "anthill", "formigas")):
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "alice",
                "speaker_name": "Alice",
                "text_pt_br": "Que cidade tão pequena... e todas parecem saber para onde vão.",
                "emotion": "curiosa e encantada",
                "delivery": "pensamento baixo, íntimo e contemplativo",
                "action": "Alice observa as formigas sem tocar no formigueiro",
                "addressee_id": None,
                "mode": "internal_thought",
                "lip_sync_required": False,
            }
        ]
    if any(term in lowered for term in ("toca de coelho", "rabbit hole", "barranco")):
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "alice",
                "speaker_name": "Alice",
                "text_pt_br": "Essa toca parece guardar um caminho que ninguém conhece.",
                "emotion": "intrigada e cautelosa",
                "delivery": "pensamento breve, curioso e contido",
                "action": "Alice se ajoelha e examina a abertura escura",
                "addressee_id": None,
                "mode": "internal_thought",
                "lip_sync_required": False,
            }
        ]
    if "xadrez" in lowered or "chess" in lowered:
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "ludovico",
                "speaker_name": "Ludovico",
                "text_pt_br": "Cuidado, Alice. Esse cavalo está procurando uma saída.",
                "emotion": "divertido e concentrado",
                "delivery": "brincalhão, baixo e preciso",
                "action": "Ludovico move o cavalo no tabuleiro e observa Alice",
                "addressee_id": "alice",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
            {
                "turn_id": "turn_2",
                "speaker_id": "alice",
                "speaker_name": "Alice",
                "text_pt_br": "Então minha rainha vai fechar o caminho dele!",
                "emotion": "animada e confiante",
                "delivery": "rápida, sorridente e competitiva",
                "action": "Alice move a rainha e sorri para Ludovico",
                "addressee_id": "ludovico",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
        ]
    if "ludovico" in lowered and any(
        term in lowered for term in ("tea table", "mesa de chá", "children", "crianças")
    ):
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "ludovico",
                "speaker_name": "Ludovico",
                "text_pt_br": "Podem entrar, meninas. Há lugar para todas à mesa.",
                "emotion": "acolhedor e surpreso",
                "delivery": "caloroso, gentil e convidativo",
                "action": "Ludovico se vira para a porta e sorri para as meninas",
                "addressee_id": None,
                "mode": "dialogue",
                "lip_sync_required": True,
            }
        ]
    if "edith" in lowered or "irmã" in lowered or "irma" in lowered:
        return [
            {
                "turn_id": "turn_1",
                "speaker_id": "edith",
                "speaker_name": "Edith",
                "text_pt_br": "Alice, venha devagar. Acho que eles ainda não nos viram.",
                "emotion": "cúmplice e cautelosa",
                "delivery": "sussurro claro e natural",
                "action": "Edith se aproxima de Alice e aponta discretamente para a porta",
                "addressee_id": "alice",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
            {
                "turn_id": "turn_2",
                "speaker_id": "alice",
                "speaker_name": "Alice",
                "text_pt_br": "Vamos só espiar um instante.",
                "emotion": "curiosa e travessa",
                "delivery": "baixo, rápido e sorridente",
                "action": "Alice concorda e olha pela porta entreaberta",
                "addressee_id": "edith",
                "mode": "dialogue",
                "lip_sync_required": True,
            },
        ]
    speaker_id = "alice" if "alice" in lowered else "protagonista"
    speaker_name = "Alice" if speaker_id == "alice" else "Protagonista"
    return [
        {
            "turn_id": "turn_1",
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
            "text_pt_br": "Preciso olhar mais de perto para entender o que está acontecendo.",
            "emotion": "atenta e curiosa",
            "delivery": "pensamento breve, natural e infantil",
            "action": f"{speaker_name} observa o elemento principal da cena",
            "addressee_id": None,
            "mode": "internal_thought",
            "lip_sync_required": False,
        }
    ]


def enrich_scene_performance(scene: Mapping[str, Any]) -> Dict[str, Any]:
    enriched = dict(scene)
    scene_text = " ".join(
        str(value or "")
        for value in (
            scene.get("description"),
            scene.get("prompt"),
            " ".join(str(item) for item in scene.get("must_include", []) if item),
        )
    )
    dialogue = scene.get("dialogue")
    legacy_dialogue = not isinstance(dialogue, list) or not dialogue
    if legacy_dialogue:
        dialogue = _canonical_dialogue(scene_text)
    characters = scene.get("characters_present")
    if not isinstance(characters, list) or not characters:
        characters = list(
            dict.fromkeys(
                str(turn.get("speaker_name") or turn.get("speaker_id"))
                for turn in dialogue
                if isinstance(turn, dict)
            )
        )
        lowered = scene_text.lower()
        for name in ("Alice", "Ludovico", "Edith"):
            if name.lower() in lowered and name not in characters:
                characters.append(name)
    required_visuals = scene.get("required_visual_elements")
    if not isinstance(required_visuals, list) or not required_visuals:
        required_visuals = [
            str(item) for item in scene.get("must_include", []) if str(item).strip()
        ] or [str(scene.get("description") or "ação principal da cena")[:180]]
    required_visuals = [
        _LEGACY_VISUAL_PT_BR.get(str(item).strip().lower(), str(item).strip())
        for item in required_visuals
        if str(item).strip()
    ]
    if legacy_dialogue:
        required_blob = " ".join(str(item).lower() for item in required_visuals)
        for turn in dialogue:
            speaker_name = str(
                turn.get("speaker_name") or turn.get("speaker_id") or ""
            ).strip()
            if speaker_name and speaker_name.lower() not in required_blob:
                required_visuals.append(speaker_name)
                required_blob += f" {speaker_name.lower()}"
    main_action = str(
        scene.get("main_action") or scene.get("description") or "ação da cena"
    )[:300]
    main_action = _LEGACY_MAIN_ACTION_PT_BR.get(main_action.lower(), main_action)
    enriched.update(
        {
            "location": str(scene.get("location") or "ambiente descrito na cena"),
            "main_action": main_action,
            "dominant_emotion": str(
                scene.get("dominant_emotion")
                or dialogue[0].get("emotion")
                or "curiosidade"
            ),
            "characters_present": characters,
            "required_visual_elements": required_visuals,
            "dialogue": dialogue,
            "language": "pt-BR",
            "narration_allowed": False,
        }
    )
    return enriched


def dialogue_turns(scene: Mapping[str, Any]) -> List[DialogueTurn]:
    enriched = enrich_scene_performance(scene)
    return [
        dict(turn) for turn in enriched.get("dialogue", []) if isinstance(turn, dict)
    ]


def validate_scene_performance(scene: Mapping[str, Any]) -> Dict[str, Any]:
    enriched = enrich_scene_performance(scene)
    blockers: List[str] = []
    turns = dialogue_turns(enriched)
    present = {
        normalize_character_id(character)
        for character in enriched.get("characters_present", [])
    }
    visual_evidence = " ".join(
        [
            str(enriched.get("description") or ""),
            str(enriched.get("main_action") or ""),
            " ".join(
                str(item)
                for item in enriched.get("required_visual_elements", [])
                if item
            ),
        ]
    ).lower()
    if enriched.get("language") != "pt-BR":
        blockers.append("scene_language_not_pt_br")
    if enriched.get("narration_allowed") is not False:
        blockers.append("narration_must_be_disabled")
    for field in ("location", "main_action", "dominant_emotion"):
        if _contains_english_dialogue(str(enriched.get(field) or "")):
            blockers.append(f"scene_{field}_language_not_pt_br")
    required_visuals_text = " ".join(
        str(item) for item in enriched.get("required_visual_elements", []) if item
    )
    if _contains_english_dialogue(required_visuals_text):
        blockers.append("scene_required_visuals_language_not_pt_br")
    if not turns:
        blockers.append("scene_dialogue_missing")
    seen_voices: set[str] = set()
    for index, turn in enumerate(turns, 1):
        speaker_id = normalize_character_id(turn.get("speaker_id"))
        text = str(turn.get("text_pt_br") or "").strip()
        mode = str(turn.get("mode") or "dialogue")
        speaker_name = str(turn.get("speaker_name") or "").strip()
        action = str(turn.get("action") or "").strip()
        addressee_id = normalize_character_id(turn.get("addressee_id"))
        if not speaker_id:
            blockers.append(f"turn_{index}_speaker_missing")
        elif is_narrator_role(speaker_id):
            blockers.append(f"turn_{index}_narrator_forbidden")
        elif speaker_id not in present:
            blockers.append(f"turn_{index}_speaker_not_in_scene:{speaker_id}")
        elif not any(
            candidate and candidate in visual_evidence
            for candidate in (speaker_id.replace("_", " "), speaker_name.lower())
        ):
            blockers.append(f"turn_{index}_speaker_not_visually_required:{speaker_id}")
        if addressee_id and addressee_id not in present:
            blockers.append(f"turn_{index}_addressee_not_in_scene:{addressee_id}")
        if not text:
            blockers.append(f"turn_{index}_text_missing")
        elif _contains_english_dialogue(text):
            blockers.append(f"turn_{index}_language_not_pt_br")
        if mode not in {"dialogue", "internal_thought"}:
            blockers.append(f"turn_{index}_mode_invalid")
        if not action:
            blockers.append(f"turn_{index}_visible_action_missing")
        elif not any(
            candidate and candidate in action.lower()
            for candidate in (speaker_id.replace("_", " "), speaker_name.lower())
        ):
            blockers.append(f"turn_{index}_action_not_bound_to_speaker")
        if mode == "dialogue" and turn.get("lip_sync_required") is not True:
            blockers.append(f"turn_{index}_lipsync_required")
        if mode == "internal_thought" and turn.get("lip_sync_required") is not False:
            blockers.append(f"turn_{index}_internal_thought_must_not_move_mouth")
        for spoken_terms, visual_terms in _DIALOGUE_VISUAL_ANCHORS:
            if any(term in text.lower() for term in spoken_terms) and not any(
                term in visual_evidence for term in visual_terms
            ):
                blockers.append(
                    f"turn_{index}_spoken_object_not_visually_required:"
                    f"{spoken_terms[0]}"
                )
        seen_voices.add(speaker_id)
    return {
        "passed": not blockers,
        "blockers": blockers,
        "language": enriched.get("language"),
        "narration_absent": not any("narrator" in item for item in blockers),
        "speaker_count": len(seen_voices),
        "turn_count": len(turns),
        "required_visual_elements": enriched.get("required_visual_elements", []),
    }


def build_speaker_motion_prompt(
    scene: Mapping[str, Any], turn: Mapping[str, Any]
) -> str:
    speaker = str(turn.get("speaker_name") or turn.get("speaker_id") or "personagem")
    emotion = str(turn.get("emotion") or "natural")
    action = str(turn.get("action") or scene.get("main_action") or "reage à cena")
    mode = str(turn.get("mode") or "dialogue")
    if mode == "internal_thought":
        performance = (
            f"{speaker} keeps the mouth fully closed and expresses {emotion} only through eyes, "
            f"brows, breathing and body language while {action}. No character speaks on camera."
        )
    else:
        performance = (
            f"Only {speaker} speaks and moves the mouth, with a clear unobstructed face and {emotion} expression, "
            f"while {action}. Every listener keeps the mouth fully closed, reacts only with eyes and body language, "
            "and stays in profile, three-quarter background, or over-the-shoulder framing."
        )
    return (
        f"{performance} Preserve the approved identities, wardrobe, props, setting and art direction exactly. "
        "Natural restrained acting, smooth cinematic motion, no extra dialogue, no subtitles, no text."
    )[:1200]


def production_dialogue_gate(
    scenes: Sequence[Mapping[str, Any]],
    audio_files: Sequence[Mapping[str, Any]],
    scene_videos: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    blockers: List[str] = []
    scene_results: List[Dict[str, Any]] = []
    audio_by_scene = {str(item.get("scene_id")): item for item in audio_files}
    video_by_scene = {str(item.get("scene_id")): item for item in scene_videos}
    video_validation_requested = bool(scene_videos)
    for scene in scenes:
        scene_id = str(scene.get("scene_id"))
        contract = validate_scene_performance(scene)
        scene_blockers = list(contract["blockers"])
        audio = audio_by_scene.get(scene_id, {})
        video = video_by_scene.get(scene_id, {})
        expected_turns = dialogue_turns(scene)
        rendered_turns = audio.get("dialogue_turns", [])
        video_segments = video.get("dialogue_segments", [])
        if len(rendered_turns) != len(expected_turns):
            scene_blockers.append("dialogue_audio_turn_count_mismatch")
        if video_validation_requested and not video:
            scene_blockers.append("dialogue_scene_video_missing")
        elif video and len(video_segments) != len(expected_turns):
            scene_blockers.append("dialogue_video_segment_count_mismatch")
        for index, turn in enumerate(rendered_turns, 1):
            if is_narrator_role(turn.get("voice_role") or turn.get("speaker_id")):
                scene_blockers.append(f"turn_{index}_narrator_audio_forbidden")
            if not turn.get("voice_id"):
                scene_blockers.append(f"turn_{index}_character_voice_missing")
        if scene_blockers:
            blockers.extend(f"scene_{scene_id}:{item}" for item in scene_blockers)
        scene_results.append(
            {
                "scene_id": scene_id,
                "passed": not scene_blockers,
                "blockers": scene_blockers,
                "turn_count": len(expected_turns),
            }
        )
    return {
        "passed": not blockers,
        "blockers": blockers,
        "scenes": scene_results,
        "narration_absent": not any("narrator" in item for item in blockers),
        "language": "pt-BR",
    }
