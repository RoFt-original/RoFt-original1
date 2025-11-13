"""Utilities for removing backgrounds from media files."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable


Logger = Callable[[str], None]


class BackgroundRemovalError(RuntimeError):
    """Raised when a background removal step fails."""


_IMAGE_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
}


@dataclass(slots=True)
class BackgroundRemovalResult:
    """Result object describing a processed file."""

    source: Path
    processed: Path


def _run_ffmpeg(args: Iterable[str], log: Logger) -> None:
    if shutil.which("ffmpeg") is None:
        raise BackgroundRemovalError(
            "ffmpeg не найден. Установите ffmpeg и добавьте его в PATH."
        )

    command = ["ffmpeg", "-y", *map(str, args)]
    log("Запуск ffmpeg: " + " ".join(command))
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        log(process.stdout)
        log(process.stderr)
        raise BackgroundRemovalError(
            "ffmpeg завершился с ошибкой (код {code}).".format(
                code=process.returncode
            )
        )


def _probe_fps(path: Path, log: Logger) -> float:
    if shutil.which("ffprobe") is None:
        raise BackgroundRemovalError(
            "ffprobe не найден. Установите ffmpeg (включая ffprobe)."
        )

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-print_format",
        "json",
        "-show_streams",
        str(path),
    ]
    log("Определение FPS через ffprobe: " + " ".join(command))
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        log(process.stderr)
        raise BackgroundRemovalError(
            "Не удалось определить FPS (код {code}).".format(
                code=process.returncode
            )
        )

    data = json.loads(process.stdout)
    stream = (data.get("streams") or [{}])[0]
    avg_frame_rate = stream.get("avg_frame_rate") or "0/0"

    try:
        fraction = Fraction(avg_frame_rate)
        if fraction.denominator == 0:
            raise ZeroDivisionError
        value = float(fraction)
    except (ValueError, ZeroDivisionError):
        log(
            "Не удалось преобразовать значение FPS '{value}', используется 30.".format(
                value=avg_frame_rate
            )
        )
        return 30.0

    value = max(1.0, min(60.0, value))
    log(f"FPS источника: {value:.2f}")
    return value


def _remove_background_from_image(source: Path, destination: Path, log: Logger) -> None:
    log(f"Удаление фона у изображения {source}…")
    try:
        from rembg import remove
    except ImportError as exc:  # pragma: no cover - executed only without dependency
        raise BackgroundRemovalError(
            "Библиотека rembg не установлена. Добавьте 'rembg' в зависимости."
        ) from exc

    data = source.read_bytes()
    result = remove(data)
    destination.write_bytes(result)
    log(f"Фон удалён: {destination}")


def _extract_video_frames(source: Path, frames_dir: Path, log: Logger) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = frames_dir / "frame_%07d.png"
    _run_ffmpeg(["-i", source, str(frame_pattern)], log)


def _compose_video_from_frames(
    frames_dir: Path,
    fps: float,
    destination: Path,
    log: Logger,
) -> None:
    frame_pattern = frames_dir / "frame_%07d.png"
    if not any(frames_dir.glob("frame_*.png")):
        raise BackgroundRemovalError(
            "Кадры для сборки видео не найдены: {dir}".format(dir=frames_dir)
        )

    args = [
        "-framerate",
        f"{fps:.3f}",
        "-i",
        frame_pattern,
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        destination,
    ]
    _run_ffmpeg(args, log)


def remove_background(source: Path, workspace: Path, log: Logger) -> BackgroundRemovalResult:
    """Remove background from ``source`` and return processed path."""

    source = source.resolve()
    workspace = workspace.resolve()
    log(f"Начало удаления фона из {source}")

    if source.suffix.lower() in _IMAGE_EXTENSIONS:
        processed_path = workspace / f"{source.stem}_bg_removed.png"
        _remove_background_from_image(source, processed_path, log)
        return BackgroundRemovalResult(source=source, processed=processed_path)

    # Treat everything else as a video container (including GIF).
    frames_dir = workspace / "frames"
    _extract_video_frames(source, frames_dir, log)

    processed_frames_dir = workspace / "frames_processed"
    processed_frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        from rembg import remove
    except ImportError as exc:  # pragma: no cover - executed only without dependency
        raise BackgroundRemovalError(
            "Библиотека rembg не установлена. Добавьте 'rembg' в зависимости."
        ) from exc

    frame_paths = sorted(frames_dir.glob("frame_*.png"))
    if not frame_paths:
        raise BackgroundRemovalError("ffmpeg не создал ни одного кадра.")

    for index, frame_path in enumerate(frame_paths, start=1):
        log(f"Удаление фона из кадра {index}/{len(frame_paths)}: {frame_path.name}")
        data = frame_path.read_bytes()
        processed_data = remove(data)
        (processed_frames_dir / frame_path.name).write_bytes(processed_data)

    fps = _probe_fps(source, log)
    processed_video = workspace / f"{source.stem}_bg_removed.webm"
    _compose_video_from_frames(processed_frames_dir, fps, processed_video, log)
    log(f"Видео с прозрачным фоном сохранено: {processed_video}")

    return BackgroundRemovalResult(source=source, processed=processed_video)
