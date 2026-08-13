param(
    [string]$Version = "0.1.0",
    [string]$OutputDirectory = "release"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$outputRoot = Join-Path $repoRoot $OutputDirectory
$packageName = "SafeCodeLoop-$Version"
$stagingRoot = Join-Path $outputRoot $packageName
$zipPath = Join-Path $outputRoot "$packageName.zip"

Push-Location $repoRoot
try {
    $trackedFiles = git ls-files
    if (-not $trackedFiles) {
        throw "git ls-files returned no tracked files"
    }

    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -Recurse -Force -LiteralPath $stagingRoot
    }
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -Force -LiteralPath $zipPath
    }
    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

    foreach ($relativePath in $trackedFiles) {
        $source = Join-Path $repoRoot $relativePath
        $destination = Join-Path $stagingRoot $relativePath
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }

    Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $zipPath -Force
    Remove-Item -Recurse -Force -LiteralPath $stagingRoot

    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $blockedPatterns = @(
            "^\.git/",
            "(^|/)\.env($|[./])",
            "(^|/)\.safecodeloop/",
            "__pycache__/",
            "\.pyc$",
            "\.pytest_cache/",
            "\.log$"
        )
        $violations = @()
        foreach ($entry in $zip.Entries) {
            $entryName = $entry.FullName -replace "\\", "/"
            foreach ($pattern in $blockedPatterns) {
                if ($entryName -match $pattern) {
                    $violations += $entryName
                    break
                }
            }
        }
        if ($violations.Count -gt 0) {
            throw "release archive contains excluded paths: $($violations -join ', ')"
        }
    }
    finally {
        $zip.Dispose()
    }

    Write-Host "Created $zipPath"
}
finally {
    Pop-Location
}
