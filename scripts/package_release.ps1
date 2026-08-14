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
$checksumPath = Join-Path $outputRoot "SHA256SUMS"

Push-Location $repoRoot
try {
    $trackedChanges = git status --porcelain --untracked-files=no
    if ($trackedChanges) {
        throw "tracked files have uncommitted changes; commit them before packaging a release"
    }

    $commit = git rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or -not $commit) {
        throw "unable to determine the release commit"
    }

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
    if (Test-Path -LiteralPath $checksumPath) {
        Remove-Item -Force -LiteralPath $checksumPath
    }
    Get-ChildItem -LiteralPath $outputRoot -File | Where-Object {
        $_.Name -like "safecodeloop-$Version-*.whl" -or
        $_.Name -eq "safecodeloop-$Version.tar.gz"
    } | Remove-Item -Force
    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

    foreach ($relativePath in $trackedFiles) {
        $source = Join-Path $repoRoot $relativePath
        $destination = Join-Path $stagingRoot $relativePath
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
    }
    Set-Content -LiteralPath (Join-Path $stagingRoot "BUILD_INFO.txt") -Encoding utf8NoBOM -Value @(
        "version=$Version"
        "commit=$commit"
    )

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

    python -m build --sdist --wheel --outdir $outputRoot
    if ($LASTEXITCODE -ne 0) {
        throw "python -m build failed with exit code $LASTEXITCODE"
    }

    $artifacts = @(
        Get-Item -LiteralPath $zipPath
        Get-Item -LiteralPath (Join-Path $outputRoot "safecodeloop-$Version.tar.gz")
        Get-ChildItem -LiteralPath $outputRoot -File -Filter "safecodeloop-$Version-*.whl" |
            Select-Object -First 1
    )
    if ($artifacts.Count -ne 3 -or $artifacts -contains $null) {
        throw "expected exactly one source zip, one sdist, and one wheel"
    }

    $checksumLines = foreach ($artifact in $artifacts) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.FullName).Hash.ToLowerInvariant()
        "$hash  $($artifact.Name)"
    }
    Set-Content -LiteralPath $checksumPath -Value $checksumLines -Encoding utf8NoBOM

    Write-Host "Created release assets in $outputRoot"
    $artifacts | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host "  SHA256SUMS"
}
finally {
    Pop-Location
}
