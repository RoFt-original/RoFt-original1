"""Entry point for running the sticker maker GUI."""
from __future__ import annotations

from .gui import StickerMakerApp


def main() -> None:
    app = StickerMakerApp()
    app.run()


if __name__ == "__main__":
    main()
