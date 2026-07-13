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
- Cost discipline: use ComfyUI/RunPod SDXL as the first image tier; escalate to
  more expensive providers only after a measurable failure case.

Current first model target:

- Provider: ComfyUI on RunPod Serverless
- Model family: SDXL checkpoint
- Checkpoint filename: `ai-film-comic-storybook-xl.safetensors`
- Loader: `CheckpointLoaderSimple`
- Initial Hugging Face source alias: `comic-sdxl`
- Intended visual style: `comic_storybook`

Reference-control stack:

- IP-Adapter Plus SDXL preserves approved character/object appearance from a
  reference frame without replacing the scene prompt.
- ControlNet Depth controls staging and hero-object placement.
- Inpainting limits object repairs to the rejected region.
- An optional original/licensed style LoRA may stabilize the film's visual
  language. It is never used as a replacement for the base model or for
  object-specific references.
- Treat all model and training-data choices as commercial-use choices. Do not
  use non-commercial checkpoints in publishable or monetizable runs.

Acceptance bar for the next image test:

- Each scene must visibly match the scene contract.
- Main character identity must remain coherent across scenes.
- Required small object must be legible without zooming.
- No text/artifacts/watermarks.
- Style must stay comic/storybook across all scenes.
- Quality score should stay above the configured semantic gate before publish.
