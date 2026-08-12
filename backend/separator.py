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


def stem_path(stems_dir: Path, name: str) -> Path:
    """Path to a single separated stem WAV."""
    return stems_dir / f"{name}.wav"

def _pick_device() -> str:
    """Use the best available accelerator: NVIDIA CUDA, Apple Silicon MPS, else CPU."""
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


_model = None
_device = _pick_device()


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


# --------------------------------------------------------------------------- #
# BPM & key detection
# --------------------------------------------------------------------------- #

# Krumhansl-Schmuckler key profiles (major / minor).
_KS_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
_KS_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# pitch-class index (0=C .. 11=B) -> Camelot code
_CAMELOT_MAJOR = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
    6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}
_CAMELOT_MINOR = {
    0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
    6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A",
}


def analyze(input_path: Path) -> dict:
    """Detect BPM and musical key of the full mix.

    Returns {"bpm": int|None, "key_camelot": str|None, "key_musical": str|None}.
    Best-effort: any failure returns None fields rather than raising.
    """
    result = {"bpm": None, "key_camelot": None, "key_musical": None}
    try:
        import librosa

        y, sr = librosa.load(str(input_path), mono=True)

        # Tempo (beat_track may return a scalar or a 1-element array).
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        if bpm > 0:
            result["bpm"] = int(round(bpm))

        # Key: mean chroma correlated against all 24 rotated KS profiles.
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
        best_corr, best_i, best_mode = -2.0, 0, "maj"
        for i in range(12):
            for prof, mode in ((_KS_MAJOR, "maj"), (_KS_MINOR, "min")):
                corr = np.corrcoef(chroma, np.roll(prof, i))[0, 1]
                if corr > best_corr:
                    best_corr, best_i, best_mode = corr, i, mode
        if best_mode == "maj":
            result["key_musical"] = _NOTE_NAMES[best_i]
            result["key_camelot"] = _CAMELOT_MAJOR[best_i]
        else:
            result["key_musical"] = _NOTE_NAMES[best_i] + "m"
            result["key_camelot"] = _CAMELOT_MINOR[best_i]
    except Exception as exc:  # noqa: BLE001 - detection is best-effort
        print(f"analyze() failed: {exc}")
    return result


# --------------------------------------------------------------------------- #
# Metadata / cover-art passthrough
# --------------------------------------------------------------------------- #

def read_source_meta(input_path: Path, fallback_title: str) -> dict:
    """Read text tags + first embedded cover from the original upload.

    Missing values fall back sensibly (title -> ``fallback_title``).
    """
    meta = {
        "title": None, "artist": None, "album": None,
        "genre": None, "date": None, "cover": None, "cover_mime": None,
    }
    try:
        from mutagen import File as MutagenFile

        easy = MutagenFile(str(input_path), easy=True)
        if easy is not None and easy.tags:
            def g(key: str):
                v = easy.tags.get(key)
                return v[0] if v else None
            meta["title"] = g("title")
            meta["artist"] = g("artist")
            meta["album"] = g("album")
            meta["genre"] = g("genre")
            meta["date"] = g("date")

        raw = MutagenFile(str(input_path))
        cover, mime = _extract_cover(raw)
        meta["cover"], meta["cover_mime"] = cover, mime
    except Exception as exc:  # noqa: BLE001
        print(f"read_source_meta() failed: {exc}")

    if not meta["title"]:
        meta["title"] = fallback_title
    return meta


def _extract_cover(raw) -> tuple[bytes | None, str | None]:
    """Pull the first cover image (bytes, mime) from a mutagen file, if any."""
    if raw is None:
        return None, None
    tags = getattr(raw, "tags", None)
    # MP3 / ID3: APIC frames
    if tags is not None and hasattr(tags, "getall"):
        pics = tags.getall("APIC")
        if pics:
            return pics[0].data, pics[0].mime or "image/jpeg"
    # FLAC / OGG: .pictures
    pics = getattr(raw, "pictures", None)
    if pics:
        return pics[0].data, pics[0].mime or "image/jpeg"
    # MP4 / M4A: 'covr' atom
    if tags is not None:
        covr = tags.get("covr")
        if covr:
            from mutagen.mp4 import MP4Cover

            mime = "image/png" if covr[0].imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
            return bytes(covr[0]), mime
    return None, None


def tag_output(out_path: Path, fmt: str, meta: dict) -> None:
    """Write metadata (and cover art for MP3) into a finished output file.

    MP3 gets full ID3 (title/artist/album/genre/date/BPM/key + cover art).
    WAV gets best-effort RIFF-INFO text tags via ffmpeg (no cover art).
    """
    if fmt == "mp3":
        _tag_mp3(out_path, meta)
    elif fmt == "wav":
        _tag_wav(out_path, meta)


def _tag_mp3(out_path: Path, meta: dict) -> None:
    from mutagen.id3 import (
        APIC, ID3, TALB, TBPM, TCON, TDRC, TIT2, TKEY, TPE1,
    )
    from mutagen.id3 import ID3NoHeaderError

    try:
        tags = ID3(str(out_path))
    except ID3NoHeaderError:
        tags = ID3()

    def setf(frame, value):
        if value:
            tags.setall(frame.__name__, [frame(encoding=3, text=str(value))])

    setf(TIT2, meta.get("title"))
    setf(TPE1, meta.get("artist"))
    setf(TALB, meta.get("album"))
    setf(TCON, meta.get("genre"))
    setf(TDRC, meta.get("date"))
    setf(TBPM, meta.get("bpm"))
    setf(TKEY, meta.get("key"))

    if meta.get("cover"):
        tags.setall("APIC", [APIC(
            encoding=3,
            mime=meta.get("cover_mime") or "image/jpeg",
            type=3,  # front cover
            desc="Cover",
            data=meta["cover"],
        )])
    tags.save(str(out_path))


def _tag_wav(out_path: Path, meta: dict) -> None:
    pairs = {
        "title": meta.get("title"),
        "artist": meta.get("artist"),
        "album": meta.get("album"),
        "genre": meta.get("genre"),
        "date": meta.get("date"),
    }
    bits = [f"{k} {meta[k]}" for k in ("bpm", "key") if meta.get(k)]
    if bits:
        pairs["comment"] = " ".join(bits)

    cmd = ["ffmpeg", "-y", "-i", str(out_path)]
    for k, v in pairs.items():
        if v:
            cmd += ["-metadata", f"{k}={v}"]
    tmp = out_path.with_suffix(".tag.wav")
    cmd += ["-c", "copy", str(tmp)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        tmp.replace(out_path)
    except Exception as exc:  # noqa: BLE001 - tagging must not break downloads
        print(f"_tag_wav() failed: {exc}")
        tmp.unlink(missing_ok=True)
