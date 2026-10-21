"""Compatibility exports for archived prototype scripts."""

from cad_agent.integrations.solidworks import SolidWorksConnectionError, connect, get_status

__all__ = ["connect", "get_status", "SolidWorksConnectionError"]
