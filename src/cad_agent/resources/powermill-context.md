# PowerMill 2027 context

Installed reference: docs/powermill. Automation: PowerMILL.Application Windows COM.
execute_command checks numeric status AND textual #ERROR responses; both matter.
require_empty_project refuses existing saved/nonempty projects before any changes.
Native SolidWorks parts imported successfully in our live test, with mm extents.

These exact commands worked in the local demo (paths/names must be quoted):
IMPORT MODEL "absolute model path"
SIZE MODEL "model name"
EDIT BLOCK RESET
CREATE TOOL ; BALLNOSED
EDIT TOOL ; DIAMETER 6
EDIT TOOL ; LENGTH 30
RENAME TOOL ; Demo_Ball6
IMPORT TEMPLATE ENTITY TOOLPATH "absolute installed .ptf path"
RENAME TOOLPATH ; Demo_Raster
EDIT FINRASTER STEPOVER 1
EDIT PAR "Tolerance" "0.05"
EDIT TOOLPATH ; CALCULATE
ACTIVATE TOOLPATH "Demo_Raster"
PRINT PAR TERSE "Computed"
PRINT PAR TERSE "Statistics.CuttingMoves.Lengths.Linear"
PRINT PAR TERSE "Statistics.CuttingMoves.Lengths.arcs"
EDIT COLLISION TYPE Gouge
EDIT COLLISION SCOPE ALL
EDIT COLLISION SPLIT_TOOLPATH N
EDIT COLLISION STOCKMODEL_CHECK N
EDIT COLLISION APPLY
PRINT PAR TERSE "Verification.GougeChecked"
PRINT PAR TERSE "Safety.Tool.Cutting.Status"
PRINT PAR TERSE "Safety.Tool.Links.Status"
PRINT PAR TERSE "Safety.Tool.Leads.Status"
PROJECT SAVE AS "absolute new project directory"
ROTATE TRANSFORM ISO1
KEEP BITMAP WHITEBG "absolute preview.jpg" YES

The tested raster template is installed at:
C:\Program Files\Autodesk\PowerMill 2027\file\templates\Finishing\Raster-Finishing.002.ptf
Discover and validate installed files; do not assume this path exists everywhere.
The template is old despite being shipped in 2027. Commands/parameters may differ
between strategies. Capture echo/recorded commands before unfamiliar operations.

Toolpath calculation may be queued: poll Computed/Busy with a bounded deadline
before claiming success. A toolpath entity count alone does not prove calculation.
The demo reported safe cutting/links/leads but GougeChecked=0. Treat discrepancies
and any holder/fixture/machine checks not performed as unresolved. Toolpath
calculation and a finishing strategy do not establish complete stock removal.
