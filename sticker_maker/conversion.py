"""Инструменты для конвертации в формат стикеров Telegram."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from tgradish import get_config
from tgradish.converter import convert_video


Logger = Callable[[str], None]


@dataclass(slots=True)
class ConversionOptions:
    """Настройки процесса конвертации."""

    scaling: str = "preserve-ratio"
    loop: bool = False
    best_quality: bool = False
    multithreading: bool = False
    lossless: bool = False
    guess_value: str = "bitrate"
    guess_iterations: Optional[int] = None
    guess_min: Optional[float] = None
    guess_max: Optional[float] = None
    length: Optional[float] = None
    framerate: Optional[float] = None
    bitrate: Optional[int] = None
    crf: Optional[int] = None


class ConversionError(RuntimeError):
    """Ошибка, возникающая при работе tgradish."""


def _add_optional_value(
    args: list[str],
    flag: str,
    value: Optional[object],
) -> None:
    if value is not None and value != "":
        args.extend([flag, str(value)])


def convert_to_sticker(
    source: Path,
    destination: Path,
    options: ConversionOptions,
    log: Logger,
) -> Path:
    """Преобразовать файл ``source`` в webm-стикер."""

    source = source.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    config = get_config()

    args: list[str] = [
        "--input",
        str(source),
        "--output",
        str(destination),
        "--scaling",
        options.scaling,
        "--guess-value",
        options.guess_value,
    ]

    if options.loop:
        args.append("--loop")
    if options.best_quality:
        args.append("--best_quality")
    if options.multithreading:
        args.append("--multithreading")
    if options.lossless:
        args.append("--lossless")

    _add_optional_value(args, "--iterations", options.guess_iterations)
    _add_optional_value(args, "-min", options.guess_min)
    _add_optional_value(args, "-max", options.guess_max)
    _add_optional_value(args, "--length", options.length)
    _add_optional_value(args, "--framerate", options.framerate)
    _add_optional_value(args, "--bitrate", options.bitrate)
    _add_optional_value(args, "-crf", options.crf)

    log("Запуск tgradish c аргументами: " + " ".join(args))

    try:
        convert_video(config, args)
    except Exception as exc:  # pragma: no cover - зависимость от tgradish
        raise ConversionError(
            "Не удалось создать стикер: {err}".format(err=exc)
        ) from exc

    log(f"Стикер сохранён: {destination}")
    return destination
