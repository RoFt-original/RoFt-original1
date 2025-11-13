"""Графический интерфейс для создания стикеров."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import background, conversion


@dataclass(slots=True)
class FormState:
    source: Path
    destination: Path
    scaling: str
    loop: bool
    best_quality: bool
    multithreading: bool
    lossless: bool
    remove_background: bool
    length: Optional[float]
    framerate: Optional[float]
    bitrate: Optional[int]
    crf: Optional[int]


class StickerMakerApp:
    """Главное приложение Tkinter."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("TGradish Sticker Maker")
        self.root.geometry("720x520")
        self.root.minsize(680, 500)

        self._worker: Optional[threading.Thread] = None
        self._log_queue: queue.Queue[str] = queue.Queue()

        self.source_var = tk.StringVar()
        self.destination_var = tk.StringVar()
        self.scaling_var = tk.StringVar(value="preserve-ratio")
        self.loop_var = tk.BooleanVar(value=False)
        self.best_quality_var = tk.BooleanVar(value=False)
        self.multithreading_var = tk.BooleanVar(value=False)
        self.lossless_var = tk.BooleanVar(value=False)
        self.remove_bg_var = tk.BooleanVar(value=True)
        self.length_var = tk.StringVar()
        self.framerate_var = tk.StringVar()
        self.bitrate_var = tk.StringVar()
        self.crf_var = tk.StringVar()

        self._build_ui()
        self.root.after(100, self._process_log_queue)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 5}

        file_frame = ttk.LabelFrame(self.root, text="Файлы")
        file_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(file_frame, text="Источник:").grid(row=0, column=0, sticky=tk.W, **padding)
        source_entry = ttk.Entry(file_frame, textvariable=self.source_var, width=70)
        source_entry.grid(row=0, column=1, sticky=tk.EW, **padding)
        ttk.Button(file_frame, text="Обзор…", command=self._choose_source).grid(
            row=0, column=2, **padding
        )

        ttk.Label(file_frame, text="Результат:").grid(row=1, column=0, sticky=tk.W, **padding)
        destination_entry = ttk.Entry(file_frame, textvariable=self.destination_var, width=70)
        destination_entry.grid(row=1, column=1, sticky=tk.EW, **padding)
        ttk.Button(
            file_frame,
            text="Сохранить как…",
            command=self._choose_destination,
        ).grid(row=1, column=2, **padding)

        file_frame.columnconfigure(1, weight=1)

        options_frame = ttk.LabelFrame(self.root, text="Настройки")
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        scaling_frame = ttk.Frame(options_frame)
        scaling_frame.grid(row=0, column=0, sticky=tk.W, **padding)
        ttk.Label(scaling_frame, text="Масштабирование:").pack(anchor=tk.W)
        ttk.Radiobutton(
            scaling_frame,
            text="Сохранить пропорции",
            value="preserve-ratio",
            variable=self.scaling_var,
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            scaling_frame,
            text="Сделать квадрат",
            value="squared",
            variable=self.scaling_var,
        ).pack(anchor=tk.W)

        toggles_frame = ttk.Frame(options_frame)
        toggles_frame.grid(row=0, column=1, sticky=tk.W, **padding)
        ttk.Checkbutton(
            toggles_frame,
            text="Зациклить анимацию",
            variable=self.loop_var,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            toggles_frame,
            text="Максимальное качество",
            variable=self.best_quality_var,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            toggles_frame,
            text="Многопоточность",
            variable=self.multithreading_var,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            toggles_frame,
            text="Режим lossless",
            variable=self.lossless_var,
        ).pack(anchor=tk.W)
        ttk.Checkbutton(
            toggles_frame,
            text="Удалить фон",
            variable=self.remove_bg_var,
        ).pack(anchor=tk.W)

        numeric_frame = ttk.Frame(options_frame)
        numeric_frame.grid(row=0, column=2, sticky=tk.NW, **padding)

        self._add_labeled_entry(numeric_frame, "Длительность (сек)", self.length_var)
        self._add_labeled_entry(numeric_frame, "FPS", self.framerate_var)
        self._add_labeled_entry(numeric_frame, "Битрейт (кбит/с)", self.bitrate_var)
        self._add_labeled_entry(numeric_frame, "CRF", self.crf_var)

        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.convert_button = ttk.Button(
            action_frame, text="Создать стикер", command=self.start_conversion
        )
        self.convert_button.pack(side=tk.RIGHT)

        log_frame = ttk.LabelFrame(self.root, text="Логи")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_widget = tk.Text(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _add_labeled_entry(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, anchor=tk.W, pady=2)
        ttk.Label(frame, text=label).pack(side=tk.LEFT)
        entry = ttk.Entry(frame, textvariable=variable, width=10)
        entry.pack(side=tk.RIGHT)

    # -------------------------------------------------------------- callbacks --
    def _choose_source(self) -> None:
        filename = filedialog.askopenfilename(
            title="Выберите файл",
            filetypes=[
                ("Видео и изображения", "*.mp4 *.mov *.mkv *.webm *.gif *.png *.jpg *.jpeg *.bmp *.webp"),
                ("Все файлы", "*.*"),
            ],
        )
        if filename:
            path = Path(filename)
            self.source_var.set(str(path))
            default_destination = path.with_suffix(".webm")
            if not self.destination_var.get():
                self.destination_var.set(str(default_destination))

    def _choose_destination(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Сохранить как",
            defaultextension=".webm",
            filetypes=[("WebM", "*.webm"), ("Все файлы", "*.*")],
        )
        if filename:
            self.destination_var.set(filename)

    # -------------------------------------------------------------- logging --
    def _log(self, message: str) -> None:
        self._log_queue.put(message)

    def _process_log_queue(self) -> None:
        while not self._log_queue.empty():
            message = self._log_queue.get()
            self.log_widget.configure(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.configure(state=tk.DISABLED)
        self.root.after(100, self._process_log_queue)

    # -------------------------------------------------------------- parsing --
    def _parse_float(self, value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"'{value}' должно быть числом")

    def _parse_int(self, value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"'{value}' должно быть целым числом")

    def _gather_state(self) -> FormState:
        source = Path(self.source_var.get()).expanduser()
        destination_text = self.destination_var.get().strip()
        destination = (
            Path(destination_text).expanduser()
            if destination_text
            else source.with_suffix(".webm")
        )

        if not source.exists():
            raise FileNotFoundError("Файл источника не найден")

        length = self._parse_float(self.length_var.get())
        framerate = self._parse_float(self.framerate_var.get())
        bitrate = self._parse_int(self.bitrate_var.get())
        crf = self._parse_int(self.crf_var.get())

        return FormState(
            source=source,
            destination=destination,
            scaling=self.scaling_var.get(),
            loop=self.loop_var.get(),
            best_quality=self.best_quality_var.get(),
            multithreading=self.multithreading_var.get(),
            lossless=self.lossless_var.get(),
            remove_background=self.remove_bg_var.get(),
            length=length,
            framerate=framerate,
            bitrate=bitrate,
            crf=crf,
        )

    # -------------------------------------------------------------- workflow --
    def start_conversion(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("В процессе", "Дождитесь завершения текущего задания")
            return

        try:
            state = self._gather_state()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))
            return

        self.convert_button.config(state=tk.DISABLED)
        self._log("Начало обработки…")
        self._worker = threading.Thread(
            target=self._run_conversion,
            args=(state,),
            daemon=True,
        )
        self._worker.start()

    def _run_conversion(self, state: FormState) -> None:
        try:
            with TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                source_path = state.source

                if state.remove_background:
                    self._log("Удаление фона…")
                    result = background.remove_background(source_path, workspace, self._log)
                    source_path = result.processed

                options = conversion.ConversionOptions(
                    scaling=state.scaling,
                    loop=state.loop,
                    best_quality=state.best_quality,
                    multithreading=state.multithreading,
                    lossless=state.lossless,
                    length=state.length,
                    framerate=state.framerate,
                    bitrate=state.bitrate,
                    crf=state.crf,
                )

                conversion.convert_to_sticker(
                    source=source_path,
                    destination=state.destination,
                    options=options,
                    log=self._log,
                )
        except Exception as exc:
            self._log(f"Ошибка: {exc}")
            self.root.after(0, lambda: messagebox.showerror("Ошибка", str(exc)))
        else:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Готово", f"Стикер сохранён в {state.destination}"
                ),
            )
        finally:
            self.root.after(0, lambda: self.convert_button.config(state=tk.NORMAL))

    # -------------------------------------------------------------- helpers --
    def run(self) -> None:
        self.root.mainloop()


__all__ = ["StickerMakerApp"]
