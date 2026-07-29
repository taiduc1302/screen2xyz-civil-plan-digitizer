$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

try {
    $fontPath = [System.IO.Path]::Combine($env:WINDIR, 'Fonts', 'arial.ttf')
    if (-not [System.IO.File]::Exists($fontPath)) { exit 20 }
    $fontInfo = Get-Item -LiteralPath $fontPath
    $fontHash = (Get-FileHash -LiteralPath $fontPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $release = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release).Release
    $assembly = [System.Object].Assembly
    $fileInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($assembly.Location)
    @{
        schema_version = '1.0'
        powershell_version = $PSVersionTable.PSVersion.ToString()
        os_version = [System.Environment]::OSVersion.Version.ToString()
        dotnet_release = [int]$release
        mscorlib_assembly_version = $assembly.GetName().Version.ToString()
        mscorlib_file_version = ([string]$fileInfo.FileVersion -split '\s+')[0]
        font_file_bytes = [int64]$fontInfo.Length
        font_file_sha256 = $fontHash
    } | ConvertTo-Json -Compress
    exit 0
}
catch {
    [Console]::Error.WriteLine('environment adapter failure')
    exit 22
}
