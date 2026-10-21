"""Bounded worker entry point for read-only application inventory."""

import json
import sys


def main() -> int:
    try:
        if sys.argv[1] == "solidworks":
            from cad_agent.integrations.solidworks import connect, get_status, read_member

            result = get_status()
            app = connect()
            docs = []
            document = read_member(app, "GetFirstDocument")
            while document is not None:
                docs.append(
                    {"title": read_member(document, "GetTitle"), "path": read_member(document, "GetPathName")}
                )
                document = read_member(document, "GetNext")
            result["documents"] = docs
        elif sys.argv[1] == "powermill":
            from cad_agent.integrations.powermill import connect, execute_command, get_status

            result = get_status()
            app = connect()
            result["project_path"] = execute_command(app, "PRINT VALUE PROJECTPATH")
            result["toolpath_names"] = [
                app.Project.Toolpaths.Item(i).Name for i in range(app.Project.Toolpaths.Count)
            ]
        else:
            raise ValueError("Unknown application.")
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
