# PowerMill automation reference library

## Start here

- `reference-2024/macro-programming-guide.pdf`: Autodesk's 147-page macro language
  guide, downloaded from its PowerMill 2024 offline documentation collection.
- `2027/Writing_a_PowerMILL_plugin_v6.pdf`: detailed plugin guide copied from the
  installed PowerMill 2027 documentation directory.
- `2027/PowerMILL_plugin_quickstart_guide_CS_v1.pdf`: C# plugin quickstart.
- `2027/PowerMILL_plugin_quickstart_guide_VB_v1.pdf`: VB.NET plugin quickstart.
- `2027/automation-interface.json`: machine-readable inventory extracted from the
  installed executable's COM type library. Lists interface members and argument
  names; this is a generated inventory, not a vendor-authored programming manual.

The plugin guides use their original filenames/revision labels. Their presence
in the 2027 installer does not mean their examples were newly written for 2027.
The downloaded macro guide is explicitly kept under reference-2024; validate
version-sensitive commands in the installed 2027 application.

## How Python connects

The application exposes `PowerMILL.Application` through Windows COM. Our Python
connector uses pywin32. Macro commands drive application operations through
`DoCommandEx`, which returns a command status and response. Check both: our live
test found a textual `#ERROR` response even when the numeric code was zero.

The macro guide documents the macro language and finding commands through
recording/echo. It is not an exhaustive version-specific command dictionary.
Use installed help, recorded operations and the type inventory alongside it.

## Sources

Installed PDF source:

```text
C:\Program Files\Autodesk\PowerMill 2027\file\plugins\documentation
```

COM inventory source:

```text
C:\Program Files\Autodesk\PowerMill 2027\sys\exec64\pmill.exe
```

- [Official macro programming guide](https://damassets.autodesk.net/content/dam/autodesk/external-assets/support-articles/powermill-2024-offline-help-and-macros-and-plugin-documentation/pm-macro-programming-guide.pdf)
- [Autodesk automation wrapper source](https://github.com/Autodesk/PowerShapeAndPowerMillAPI)
- [Autodesk plugin examples](https://github.com/Autodesk/powermill-api-examples)
- [Project integration notes and live test](../powermill.md)

Original vendor copyright/license notices are retained in the PDFs. Files are
local development references; PDFs are excluded from Git. manifest.json records
acquisition sources, sizes and SHA-256 checksums. Back up local reference files
separately from source control.
