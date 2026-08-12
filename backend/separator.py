"""Demucs wrapper: separate a song into 4 stems, and combine stems into one file.

The htdemucs model splits audio into: drums, bass, other, vocals.
Stems are additive — summing all four reconstructs (approximately) the original,
and summing any subset yields that subset's mix with no clipping issues.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

# The four stems htdemucs produces. Order here is just for reference; the actual
# source order is read from the model at runtime.
STEMS = ["vocals", "drums", "bass", "other"]

_model = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _get_model():
    """Load the htdemucs model once and cache it."""
    global _model
    if _model is None:
        from demucs.pretrained import get_model

        _model = get_model("htdemucs")
        _model.to(_device)
        _model.eval()
    return _model


def separate(input_path: Path, stems_dir: Path) -> list[str]:
    """Separate ``input_path`` into stem WAVs under ``stems_dir``.

    Returns the list of stem names written (e.g. ["drums", "bass", "other", "vocals"]).
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile, save_audio

    model = _get_model()
    stems_dir.mkdir(parents=True, exist_ok=True)

    # Read/resample the input to the model's expected samplerate and channels.
    wav = AudioFile(str(input_path)).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )
    # Normalize like Demucs' CLI does (helps consistency), then de-normalize output.
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    wav = (wav - mean) / (std + 1e-8)

    with torch.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device=_device,
            split=True,
            overlap=0.25,
            progress=False,
        )[0]
    sources = sources * std + mean

    written: list[str] = []
    for name, source in zip(model.sources, sources):
        out = stems_dir / f"{name}.wav"
        save_audio(source, str(out), samplerate=model.samplerate)
        written.append(name)
    return written


def combine(
    stems_dir: Path,
    stem_names: list[str],
    out_path: Path,
    fmt: str = "wav",
) -> Path:
    """Sum the given stems and write a single file at ``out_path``.

    ``fmt`` is "wav" (16-bit PCM) or "mp3" (320 kbps via ffmpeg).
    Returns the written path.
    """
    if not stem_names:
        raise ValueError("no stems selected")

    mix = None
    samplerate = None
    for name in stem_names:
        stem_file = stems_dir / f"{name}.wav"
        if not stem_file.exists():
            raise FileNotFoundError(f"missing stem: {name}")
        data, sr = sf.read(str(stem_file), dtype="float32", always_2d=True)
        samplerate = sr
        mix = data if mix is None else mix + data

    # Subsets of the original never exceed its range, but clamp defensively.
    np.clip(mix, -1.0, 1.0, out=mix)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "wav":
        sf.write(str(out_path), mix, samplerate, subtype="PCM_16")
        return out_path

    if fmt == "mp3":
        # Write a temp WAV, then encode to 320k MP3 with ffmpeg.
        tmp_wav = out_path.with_suffix(".tmp.wav")
        sf.write(str(tmp_wav), mix, samplerate, subtype="PCM_16")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(tmp_wav),
                    "-b:a", "320k", str(out_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        finally:
            tmp_wav.unlink(missing_ok=True)
        return out_path

    raise ValueError(f"unsupported format: {fmt}")
