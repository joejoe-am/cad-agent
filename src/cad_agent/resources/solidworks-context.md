# SOLIDWORKS 2025 integration context

Use cad_agent.integrations.solidworks.connect and read_member.
The connection attaches to an existing session; do not start applications silently.
Use GetUserPreferenceStringValue(8) for the default part template; validate it.
Keep explicit references to newly created documents. Never use the user's active
document as a modeling target. Model dimensions are in metres and angles in radians.
Check results after sketch, feature, rebuild, save and export operations.
Use dedicated output paths in the attempt directory and descriptive feature names.
Prefer fully constrained sketches with named driving dimensions.
Read back body geometry separately; script success is not design verification.
COM wrappers can expose zero-argument methods as property values. read_member
handles this without accidentally invoking returned COM objects.

Relevant interfaces: ISldWorks, IModelDoc2, ISketchManager, IFeatureManager,
IBody2, IFace2, IModelDocExtension. Body GetMassProperties returns volume at index 3.
The local reference library lives at docs/solidworks/2025 (CHM plus object diagram).
Cloud providers receive this text only, not full local help. Retrieve and include
additional verified method signatures before implementing unfamiliar features.
The independent reference pocket checker is task-specific and cannot certify
arbitrary geometry, hydraulic performance or manufacturing safety.
