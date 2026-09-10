#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["saxonche>=12.5"]
# ///
"""
run_xslt.py — run an XSLT 3.0 stylesheet over an input XML file using Saxon-HE.

Inverse-direction sibling of convert_to_jsonld_wContext_nesting.py:
    XML  --(run_xslt.py)-->  RDF/XML  --(convert_to_jsonld...)-->  JSON-LD

Usage:
    uv run tools/run_xslt.py <stylesheet.xslt> <input.xml> <output.rdf>

Exits non-zero on any Saxon/compilation error so it composes in a pipeline / CI.
"""

import sys
from pathlib import Path

try:
    from saxonche import PySaxonProcessor, PySaxonApiError
except ImportError:
    sys.stderr.write(
        "saxonche is not installed. Add it to pyproject.toml and run `uv sync`,\n"
        "or run this script with `uv run tools/run_xslt.py ...`.\n"
    )
    sys.exit(2)


def run_xslt(stylesheet: Path, xml_in: Path, rdf_out: Path) -> None:
    for label, p in (("stylesheet", stylesheet), ("input XML", xml_in)):
        if not p.is_file():
            sys.stderr.write(f"error: {label} not found: {p}\n")
            sys.exit(2)

    rdf_out.parent.mkdir(parents=True, exist_ok=True)

    with PySaxonProcessor(license=False) as proc:
        xslt = proc.new_xslt30_processor()
        try:
            executable = xslt.compile_stylesheet(stylesheet_file=str(stylesheet))
        except PySaxonApiError as exc:
            sys.stderr.write(f"error: failed to compile {stylesheet}:\n{exc}\n")
            sys.exit(1)
        try:
            executable.transform_to_file(source_file=str(xml_in), output_file=str(rdf_out))
        except PySaxonApiError as exc:
            sys.stderr.write(f"error: transform failed for {xml_in}:\n{exc}\n")
            sys.exit(1)

    print(f"✓ {xml_in.name} --[{stylesheet.name}]--> {rdf_out}")


def main() -> None:
    if len(sys.argv) != 4:
        sys.stderr.write(
            "usage: uv run tools/run_xslt.py <stylesheet.xslt> <input.xml> <output.rdf>\n"
        )
        sys.exit(2)
    run_xslt(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
