# Roomform

A small local web app that redesigns a room photo with Hugging Face's public
`timbrooks/instruct-pix2pix` model. The model runs on your computer's CPU;
there is no API key, hosted inference service, or GPU requirement.

## Run on Windows

Open PowerShell in this folder and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open <http://127.0.0.1:8001>.

If you do not already have a virtual environment, create one first:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## First run

The first redesign downloads the public model weights from Hugging Face (several
GB) into the normal Hugging Face cache. No Hugging Face account or token is
needed. Allow a few minutes for the first download and for CPU image generation.
Later runs reuse the downloaded model. Upload a room photo (up to 12 MB), choose
a room type and one of six styles, then set the wall color, room mood, floor
finish, lighting, and edit strength. You can also select furniture to update
and describe any other preferences.

The app uses 512-pixel images and 20 inference steps to balance image quality
with CPU use. Results can take several minutes and may vary; InstructPix2Pix is a
general image-editing model, so it may not preserve every architectural detail.
Generated images are saved under `static/generated`.

The style and room-type options are converted into instructions for
InstructPix2Pix. The edit-strength setting controls how closely generation
follows the source photo; a bolder edit may change more of the original scene.

## Model

The app uses [InstructPix2Pix](https://huggingface.co/timbrooks/instruct-pix2pix)
through the open-source Diffusers library. Review the model card and its license
before using generated results commercially.
