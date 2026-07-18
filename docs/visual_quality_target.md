# Visual Quality Target

Reference direction: storyboard-led animated short films for children and family
stories, with original comic/storybook characters, readable acting, consistent
identity and real image-to-video motion.

The target is not to copy any studio, brand, character or video. The target is
the production standard:

- Storyboard first: every scene must have clear staging, subject, action,
  camera distance and emotional beat before image generation.
- Character continuity: the protagonist keeps the same age, face family,
  wardrobe logic, silhouette and color language across scenes.
- Original premium animation look: expressive comic/storybook characters,
  painted backgrounds, clean linework, warm theatrical lighting and no brand
  imitation.
- Hero objects are readable: small story objects must be large enough to
  identify in a thumbnail and must not become incidental background noise.
- No generated text: frames must not contain captions, watermarks, fake UI,
  typography, credits or signs unless explicitly required by the story.
- Video readiness: still images should be composed for later animation, with
  clear foreground/background separation and motion intent per scene.
- Cost discipline: use self-hosted ComfyUI/RunPod FLUX.2 Klein as the first
  image tier; keep SDXL/IP-Adapter as a measured fallback and escalate to paid
  APIs only after a recorded semantic failure.

Current first model target:

- Provider: ComfyUI on RunPod Serverless
- Model family: FLUX.2 Klein Base 4B
- Diffusion filename: `flux-2-klein-base-4b.safetensors`
- Text encoder: `qwen_3_4b.safetensors`
- VAE: `flux2-vae.safetensors`
- Core loaders: `UNETLoader`, `CLIPLoader(type=flux2)`, `VAELoader`
- Intended visual style: `comic_storybook`
- License: Apache 2.0 for the 4B model family

Fallback and reference-control stack:

- FLUX.2 native image editing and multi-reference conditioning are the target
  continuity layer after the text-to-image semantic gate passes.
- IP-Adapter Plus SDXL remains the rollback path for approved references.
- ControlNet Depth controls staging and hero-object placement.
- Inpainting limits object repairs to the rejected region.
- An optional original/licensed style LoRA may stabilize the film's visual
  language. It is never used as a replacement for the base model or for
  object-specific references.
- Treat all model and training-data choices as commercial-use choices. Do not
  use non-commercial checkpoints in publishable or monetizable runs.

Rollout gate:

- Keep `COMFYUI_MODEL_FAMILY=sdxl` in the active environment until a temporary
  FLUX.2 endpoint passes the semantic smoke.
- Run `scripts/smoke_comfyui_flux2_klein.py` against that endpoint.
- Switch the active endpoint and set `COMFYUI_MODEL_FAMILY=flux2_klein` only
  after the generated frame passes both automated semantic QA and human review.

Acceptance bar for the next image test:

- Each scene must visibly match the scene contract.
- Main character identity must remain coherent across scenes.
- Required small object must be legible without zooming.
- No text/artifacts/watermarks.
- Style must stay comic/storybook across all scenes.
- Quality score should stay above the configured semantic gate before publish.
