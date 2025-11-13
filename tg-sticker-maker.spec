# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for the Telegram sticker maker."""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Collect rembg resources (models, ONNX graphs, etc.) so background removal works offline.
rembg_datas, rembg_binaries, rembg_hiddenimports = collect_all("rembg")

# ONNX Runtime ships DLLs that rembg needs at runtime on Windows; skip gracefully if
# rembg pulls a different backend.
try:
    onnx_datas = collect_data_files("onnxruntime")
except ModuleNotFoundError:
    onnx_datas = []

# Bundle all optional helpers from tgradish to avoid missing CLI features.
tgradish_hiddenimports = collect_submodules("tgradish")

_datas = rembg_datas + onnx_datas
_binaries = rembg_binaries
_hiddenimports = sorted(set(rembg_hiddenimports + tgradish_hiddenimports))


a = Analysis(
    ["sticker_maker/__main__.py"],
    pathex=["."],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="tg-sticker-maker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
