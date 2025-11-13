param(
    [string]$Python = "python",
    [string]$FfmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    [switch]$SkipFfmpegDownload
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Write-Host "Building Windows executable in $repoRoot" -ForegroundColor Cyan

Push-Location $repoRoot
try {
    Write-Host "Installing Python dependencies..." -ForegroundColor Green
    & $Python -m pip install --upgrade pip | Out-Host
    & $Python -m pip install -r requirements.txt | Out-Host
    & $Python -m pip install pyinstaller | Out-Host

    $specPath = Join-Path $repoRoot 'tg-sticker-maker.spec'
    if (-not (Test-Path $specPath)) {
        throw "Spec file not found at $specPath"
    }

    Write-Host "Running PyInstaller..." -ForegroundColor Green
    & $Python -m PyInstaller $specPath --noconfirm | Out-Host

    $distDir = Join-Path $repoRoot 'dist'
    $exePath = Join-Path $distDir 'tg-sticker-maker.exe'
    if (-not (Test-Path $exePath)) {
        throw "tg-sticker-maker.exe not found in $distDir"
    }

    $bundleDir = Join-Path $repoRoot 'windows-bundle'
    if (Test-Path $bundleDir) {
        Remove-Item $bundleDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $bundleDir | Out-Null

    Copy-Item $exePath (Join-Path $bundleDir 'tg-sticker-maker.exe') -Force

    if (-not $SkipFfmpegDownload) {
        Write-Host "Downloading FFmpeg bundle..." -ForegroundColor Green
        $tempZip = Join-Path ([System.IO.Path]::GetTempPath()) 'ffmpeg-download.zip'
        if (Test-Path $tempZip) {
            Remove-Item $tempZip -Force
        }
        Invoke-WebRequest -Uri $FfmpegUrl -OutFile $tempZip

        $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) 'ffmpeg-unpacked'
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force
        }
        Expand-Archive -LiteralPath $tempZip -DestinationPath $tempDir -Force

        $binDir = Get-ChildItem -Path $tempDir -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1 | ForEach-Object { $_.DirectoryName }
        if (-not $binDir) {
            throw "Unable to locate ffmpeg.exe in the downloaded archive."
        }
        Copy-Item (Join-Path $binDir 'ffmpeg.exe') (Join-Path $bundleDir 'ffmpeg.exe') -Force
        if (Test-Path (Join-Path $binDir 'ffprobe.exe')) {
            Copy-Item (Join-Path $binDir 'ffprobe.exe') (Join-Path $bundleDir 'ffprobe.exe') -Force
        }

        Remove-Item $tempZip -Force
        Remove-Item $tempDir -Recurse -Force
    }

    $readmePath = Join-Path $bundleDir 'README.txt'
    @(
        'TGradish Sticker Maker (Windows build)',
        '=====================================',
        '',
        'Содержимое:',
        '  * tg-sticker-maker.exe — автономное приложение.',
        '  * ffmpeg.exe / ffprobe.exe — инструменты для обработки медиа.',
        '',
        'Запуск:',
        '  1. Убедитесь, что рядом с приложением находятся файлы ffmpeg.exe и ffprobe.exe.',
        '  2. Дважды щёлкните tg-sticker-maker.exe, чтобы запустить графический интерфейс.',
        '',
        'Примечания:',
        '  • Приложение требует наличия моделей rembg, которые загружаются автоматически при первом запуске.',
        '  • Если удаление фона работает медленно, запустите программу с параметром SkipFfmpegDownload и предоставьте собственные бинарники ffmpeg.',
        '',
        'Скрипт сборки: scripts/build_windows_exe.ps1'
    ) | Set-Content -Encoding UTF8 $readmePath

    $zipPath = Join-Path $repoRoot 'tg-sticker-maker-windows.zip'
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $bundleDir '*') -DestinationPath $zipPath -Force
    Write-Host "Готово! Итоговый архив: $zipPath" -ForegroundColor Cyan
}
finally {
    Pop-Location
}
