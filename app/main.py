from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from uuid import uuid4

import torch
from diffusers import StableDiffusionInstructPix2PixPipeline
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = STATIC_DIR / "generated"
MODEL_ID = "timbrooks/instruct-pix2pix"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_EDGE = 512
MAX_PROMPT_TOKENS = 77
STYLES = {
    "Modern": "modern clean lines",
    "Scandinavian": "Scandinavian light wood",
    "Japandi": "Japandi warm wood",
    "Minimalist": "minimalist open space",
    "Bohemian": "bohemian earthy textiles",
    "Mid-century": "mid-century walnut",
}
WALL_COLORS = {
    "warm-white": "warm ivory",
    "soft-sage": "soft sage green",
    "powder-blue": "pale powder blue",
    "blush-pink": "soft blush pink",
    "lavender": "pale lavender",
    "buttercream": "buttercream yellow",
    "pale-peach": "pale peach",
}
ROOM_MOODS = {
    "calm": "calm, airy",
    "cozy": "warm, cozy",
    "elegant": "quietly elegant",
    "lively": "bright, lively",
    "natural": "organic, nature-inspired",
}
FLOORING = {
    "keep": "existing floor",
    "light-oak": "light oak",
    "warm-oak": "warm oak",
    "stone": "stone tile",
    "concrete": "matte concrete",
}
LIGHTING = {
    "preserve": "daylight",
    "warm-layered": "soft warm light",
    "bright-daylight": "bright daylight",
    "evening": "warm evening light",
}
ROOM_TYPES = {
    "living room": "living room",
    "bedroom": "bedroom",
    "kitchen": "kitchen",
    "dining room": "dining room",
    "bathroom": "bathroom",
    "home office": "home office",
}
EDIT_STRENGTHS = {
    "subtle": 2.0,
    "balanced": 1.5,
    "bold": 1.0,
}
FURNITURE_CHANGES = {
    "sofa": "sofa",
    "bed": "bed",
    "dining": "dining",
    "tables": "tables",
    "storage": "storage",
    "desk": "desk",
    "lighting": "lamp",
    "textiles": "mat/rug/curtains",
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
generation_lock = Lock()

app = FastAPI(title="Room Re-Design", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def disable_browser_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@lru_cache(maxsize=1)
def load_pipeline() -> StableDiffusionInstructPix2PixPipeline:
    pipeline = StableDiffusionInstructPix2PixPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float32,
        safety_checker=None,
        requires_safety_checker=False,
    )
    pipeline.to("cpu")
    pipeline.enable_attention_slicing()
    return pipeline


def prepare_image(data: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=413,
                    detail="Image dimensions must be 20 megapixels or smaller.",
                )
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=415, detail="Upload a valid image file.") from exc

    scale = min(1, MAX_IMAGE_EDGE / max(image.size))
    width = max(64, round(image.width * scale / 8) * 8)
    height = max(64, round(image.height * scale / 8) * 8)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def build_redesign_prompt(
    tokenizer,
    room_description: str,
    style: str,
    wall_color: str,
    room_mood: str,
    flooring: str,
    lighting: str,
    furniture_changes: list[str],
    instructions: str,
) -> str:
    prompt = (
        f"Photorealistic {room_description}, {STYLES[style]}; {ROOM_MOODS[room_mood]}. "
        f"{WALL_COLORS[wall_color]} walls; {FLOORING[flooring]}; {LIGHTING[lighting]}. "
        "Preserve room geometry, windows, doors. Realistic materials, scale, shadows."
    )
    if furniture_changes:
        selected_furniture = ", ".join(
            FURNITURE_CHANGES[item] for item in dict.fromkeys(furniture_changes)
        )
        prompt += f" Furniture: {selected_furniture}. Update if present; add if missing."

    user_brief = " ".join(instructions.split())
    if not user_brief:
        return prompt

    fixed_prompt = prompt
    brief_prefix = " User preferences: "
    max_tokens = min(MAX_PROMPT_TOKENS, tokenizer.model_max_length)
    brief_tokens = []
    for word in user_brief.split():
        brief_tokens.extend(tokenizer.encode(f"{word} ", add_special_tokens=False))
    brief_tokens = brief_tokens[:max_tokens]

    def count_prompt_tokens(text: str) -> int:
        content_tokens = sum(
            len(tokenizer.encode(f"{word} ", add_special_tokens=False))
            for word in text.split()
        )
        return content_tokens + tokenizer.num_special_tokens_to_add(pair=False)

    while brief_tokens:
        candidate = fixed_prompt + brief_prefix + tokenizer.decode(
            brief_tokens, skip_special_tokens=True
        ).strip()
        if count_prompt_tokens(candidate) <= max_tokens:
            return candidate
        brief_tokens.pop()
    return fixed_prompt


@app.get("/")
def home() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": MODEL_ID, "device": "cpu"}


@app.post("/api/redesign")
def redesign(
    image: UploadFile = File(...),
    style: str = Form("Modern"),
    room_type: str = Form("auto"),
    wall_color: str = Form("warm-white"),
    room_mood: str = Form("calm"),
    flooring: str = Form("keep"),
    lighting: str = Form("preserve"),
    edit_strength: str = Form("balanced"),
    furniture_changes: list[str] = Form(default=[]),
    instructions: str = Form("", max_length=500),
) -> dict[str, str]:
    if style not in STYLES:
        raise HTTPException(status_code=422, detail="Choose a listed design style.")
    if room_type != "auto" and room_type not in ROOM_TYPES:
        raise HTTPException(status_code=422, detail="Choose a listed room type.")
    if wall_color not in WALL_COLORS:
        raise HTTPException(status_code=422, detail="Choose a listed wall color.")
    if room_mood not in ROOM_MOODS:
        raise HTTPException(status_code=422, detail="Choose a listed room mood.")
    if flooring not in FLOORING:
        raise HTTPException(status_code=422, detail="Choose a listed flooring option.")
    if lighting not in LIGHTING:
        raise HTTPException(status_code=422, detail="Choose a listed lighting option.")
    if edit_strength not in EDIT_STRENGTHS:
        raise HTTPException(status_code=422, detail="Choose a listed redesign strength.")
    if any(item not in FURNITURE_CHANGES for item in furniture_changes):
        raise HTTPException(status_code=422, detail="Choose listed furniture to change.")

    image_data = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(image_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 12 MB or smaller.")
    source_image = prepare_image(image_data)

    output_name = f"{uuid4().hex}.png"
    output_path = OUTPUT_DIR / output_name
    try:
        with generation_lock:
            pipeline = load_pipeline()
            prompt = build_redesign_prompt(
                tokenizer=pipeline.tokenizer,
                room_description=ROOM_TYPES.get(room_type, "room"),
                style=style,
                wall_color=wall_color,
                room_mood=room_mood,
                flooring=flooring,
                lighting=lighting,
                furniture_changes=furniture_changes,
                instructions=instructions,
            )
            result = pipeline(
                prompt=prompt,
                image=source_image,
                num_inference_steps=20,
                guidance_scale=7.5,
                image_guidance_scale=EDIT_STRENGTHS[edit_strength],
            ).images[0]
            result.save(output_path, format="PNG")
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Model generation failed: {exc}",
        ) from exc

    return {
        "image_url": f"/static/generated/{output_name}",
        "download_name": f"room-redesign-{style.lower()}.png",
        "model": MODEL_ID,
    }
