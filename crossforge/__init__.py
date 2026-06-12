"""crossforge — composition rendering. Part of the Cognis Neural Suite."""

from crossforge.core import (
    TOOL_NAME,
    TOOL_VERSION,
    CrossforgeError,
    draft_composition,
    explain,
    load,
    parse_yaml_subset,
    render,
    render_all,
    resolve_params,
    validate_composition,
)

__version__ = TOOL_VERSION

__all__ = [
    "TOOL_NAME", "TOOL_VERSION", "__version__", "CrossforgeError",
    "draft_composition", "explain", "load", "parse_yaml_subset", "render",
    "render_all", "resolve_params", "validate_composition",
]
