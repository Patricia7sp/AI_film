# Product

## Register

product

## Users

Creators and technical operators building AI-assisted short films from written stories. They work in a production console where they need to upload or select a story, run the pipeline, inspect images/audio/video, monitor provider jobs, and decide whether a generated scene is good enough to keep.

## Product Purpose

AI Film Pipeline turns a story into a short generated film through an orchestrated workflow: scene planning, image generation, voice narration, video assembly, quality telemetry, and optional publishing. Success means the operator can trust each run, see where quality failed, retry selectively, and produce assets that feel intentional rather than random.

## Brand Personality

Cinematic, technical, premium. The interface should feel like a production cockpit for serious creative work: precise, calm, dark-first, and visually disciplined.

## Anti-references

Avoid generic SaaS dashboards, toy demo UIs, uninspected AI output galleries, decorative controls that do not affect generation, and local-only ComfyUI screens as the primary operating surface. Avoid image outputs that look like generic SD 1.5 samples, malformed portraits, inconsistent character identity, or prompts without art direction.

## Design Principles

1. Show the pipeline as a production system, not a demo script.
2. Every generated asset must carry provenance: provider, job id, prompt, style, timing, quality, and cost.
3. Creative controls should be explicit and inspectable, especially style and quality settings.
4. The operator should be able to reject, retry, and compare outputs without guessing what changed.
5. Orchestration belongs to Dagster; creative execution belongs to LangGraph and provider adapters.

## Accessibility & Inclusion

Target WCAG AA for UI text and controls. Keep the dark-first UI readable in long monitoring sessions, preserve keyboard-accessible controls, avoid color-only status encoding, and support reduced-motion behavior for any future animation.
