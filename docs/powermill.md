# PowerMill connection smoke test

Installed application discovered: PowerMill 2027. Its embedded type library
identifies itself as PowerMILL 2027.000 and exposes the PowerMILL.Application COM
server, Project entity collections, and DoCommand/DoCommandEx interfaces.
This verifies interface availability, not a successful running integration.

## Successful live test

After opening PowerMill Ultimate 2027 (pmill.exe, not PowerMill Modeling), COM
status succeeded. The live test imported our archived native SolidWorks pocket
plate, created a 6 mm ball-nose tool, calculated a raster path and saved the native
project plus a preview. Measured model extents were 100 x 60 x 10 mm; cutting
length was 6105.527825 mm, stepover 1 mm and tolerance 0.05 mm.

Artifacts and limitations: jobs/powermill-smoke-20261019/RESULTS.md. The project
folder must be kept intact. No NC program or G-code was generated. The gouge
command reported no gouges and safe statuses, but a checked flag remained zero;
this is an unresolved validation discrepancy, not a manufacturing approval.
The test began as a local prototype. Linked CAM generation, checked command
execution and independent inspection are now integrated; see
[CAD-to-CAM workflow](cad-to-cam.md). Machine-specific production validation and
unattended project lifecycle handling remain future work.

## Initial startup diagnostic

The initial probe found no running instance. COM activation started PowerMill,
but startup remained blocked at an Autodesk licensing window reporting that the
required connection to Autodesk for license validation could not be established.
No project, toolpaths or NC file were generated. The report is under
jobs/powermill-connection-test/report.json.

Complete supported licensing/startup through the desktop application first.
Then run from the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m cad_agent powermill-status
```

The connector only attaches to an existing instance. It reads version, visibility,
busy status and entity counts; it does not clear or alter a project. Use the same
Windows user session and privilege level. COM calls can block during startup or
modal dialogs, so execute further probes with an external process timeout.

For multiple open instances, `connect(process_id=PID)` uses the Windows Running
Object Table to attach to that specific PowerMill process. It never silently
falls back to another application's active project.

## Next live milestone

1. Confirm read-only connection to the normal licensed workspace.
2. Work in a new, isolated test project and import known plate geometry.
3. Set explicit stock, units, datum, tool and one simple machining strategy.
4. Calculate and inspect the toolpath, save project and verification evidence.
5. Add NC output only with a known target machine/controller and validated post.

No machine-specific post or physical machine setup has been supplied. A computed
toolpath or successful post does not constitute a manufacturing release.

## References

- Installed type library: C:\Program Files\Autodesk\PowerMill 2027\sys\exec64\pmill.exe
- Installed plugin guides: C:\Program Files\Autodesk\PowerMill 2027\file\plugins\documentation
- [Autodesk automation wrapper source](https://github.com/Autodesk/PowerShapeAndPowerMillAPI/blob/master/Delcam.ProductInterface.PowerMILL/PMAutomation.cs)
- [Autodesk plugin examples](https://github.com/Autodesk/powermill-api-examples)
