# Saves Grantha_Heritage_Tracker_SIH26096.pptx again from PowerPoint with its TrueType fonts embedded, so the deck shows
# Grenze Gotisch, Grenze and Hanken Grotesk on a PC that does not have them. Needs PowerPoint and the fonts installed.
#   powershell -File scripts/embed_fonts.ps1 [-Png <folder>]     # -Png also exports each slide as an image to check by eye
param([string]$Png = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$deck = Join-Path $root "Grantha_Heritage_Tracker_SIH26096.pptx"
$tmp = Join-Path $env:TEMP ("grantha-embed-" + [guid]::NewGuid() + ".pptx")
$pp = New-Object -ComObject PowerPoint.Application
try {
    $pres = $pp.Presentations.Open($deck, $true, $false, $false)          # read-only, untitled off, no window
    $pres.SaveAs($tmp, 24, -1)                                            # ppSaveAsOpenXMLPresentation, EmbedTrueTypeFonts
    if ($Png) { New-Item -ItemType Directory -Force $Png | Out-Null; $pres.SaveAs($Png, 18) }   # ppSaveAsPNG
    $pres.Close()
} finally { $pp.Quit() }
Move-Item $tmp $deck -Force
Write-Output "embedded fonts in $deck"
