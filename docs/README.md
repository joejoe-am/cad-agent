# Project documentation

PowerMill automation PDFs and installed COM inventory:
[PowerMill reference library](powermill/README.md).

## SOLIDWORKS 2025 offline API library

Files are in [solidworks/2025](solidworks/2025/). The live application reported
revision 33.5.0 during our connection test; these references target release 2025.

| File | Purpose | Source |
| --- | --- | --- |
| `sldworksapi.chm` | Detailed interfaces, methods, properties, and examples | Installed SOLIDWORKS API directory |
| `sldworksapiprogguide.chm` | Programming concepts, setup, object access, and API guidance | Installed SOLIDWORKS API directory |
| `swconst.chm` | Enumerations and numeric constants | Installed SOLIDWORKS API directory |
| `apihelp.chm` | API help entry point; some links may target help files not copied here | Installed SOLIDWORKS API directory |
| `SWObjectModel.pdf` | Official API access/object-model diagram; not a complete API manual | Downloaded from official online help |

Double-click a CHM file to read it with Windows HTML Help. Open the programming
guide first, then use the API reference's index/search for individual calls.
The local library is copied, not removed, from:

```text
C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api
```

The vendor documents retain their original copyright and licensing notices.
These copies are for this local development workspace.

## How our Python scripts communicate

`pywin32` attaches to the running Windows COM application registered as
`SldWorks.Application`. From that application object, code obtains documents,
sketch managers, features, bodies, and faces. The vendor documentation primarily
shows VBA, C#, VB.NET, and C++ signatures; our Python code adapts those COM calls.
Python late binding and output parameters require additional handling, as our
connection and modeling tests demonstrated.

The implementation was informed by official online API topics and then tested
against the installed application. Some initial lookups used other documentation
years; use this 2025 library as the version-specific reference going forward.

## Topics used for the working examples

Search these names in the CHM index:

- `ISldWorks`: application access, `NewDocument`, `GetUserPreferenceStringValue`.
- `swUserPreferenceStringValue_e`: `swDefaultTemplatePart` is 8.
- `ISketchManager.CreateCornerRectangle`: sketch geometry.
- `ISketchManager.FullyDefineSketch`: dimensions and relations.
- `ISketch.GetConstrainedStatus`: constraint verification.
- `IFeatureManager.FeatureExtrusion2`: base extrusion (legacy API).
- `IFeatureManager.FeatureCut3`: blind pocket (legacy API).
- `IBody2.GetMassProperties`: volume at returned array index 3.
- `IBody2.GetVertices`, `IVertex.GetPoint`: independent corner checks.
- `IModelDocExtension.SaveAs`: native part save.
- `IModelDoc2.SaveBMP`: preview export.

Legacy methods were sufficient for the initial installed-version smoke test;
consult their documented replacements before expanding the production adapter.

## Official online references

- [2025 API Help](https://help.solidworks.com/2025/english/api/sldworksapi/Welcome.htm)
- [2025 API object-model PDF](https://help.solidworks.com/2025/english/api/sldworksapi/SWObjectModel.pdf)
- [Accessing SOLIDWORKS objects](https://help.solidworks.com/2025/English/api/sldworksapiprogguide/Overview/Accessing_Objects.htm)
- [Fully define sketch example](https://help.solidworks.com/2025/english/api/sldworksapi/fully_define_underdefined_sketch_example_vb.htm)
- [Body mass properties](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IBody2~GetMassProperties.html)

`solidworks/2025/manifest.json` records acquisition sources, sizes, and SHA-256
checksums. No HTML extraction or searchable agent index has been created yet.
