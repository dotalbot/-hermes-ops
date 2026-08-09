#!/usr/bin/env python3
"""Regression tests for the Skills Manager draw.io operating contracts."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAGRAM_ROOT = HERE.parents[1]
SOURCE = DIAGRAM_ROOT / "artifacts/source/skills-manager-operating-overview.drawio"
VALIDATOR = HERE / "validate_and_render_drawio.py"

spec = importlib.util.spec_from_file_location("drawio_validator", VALIDATOR)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load draw.io validator")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class DrawioOperatingContractTests(unittest.TestCase):
    def validate_mutation(self, mutate) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tree = ET.parse(SOURCE)
            mutate(tree)
            candidate = temp / "candidate.drawio"
            tree.write(candidate, encoding="utf-8", xml_declaration=True)
            validator.validate_and_render(candidate, temp / "preview")

    def test_current_source_passes(self) -> None:
        self.validate_mutation(lambda _tree: None)

    def test_rejects_impact_gate_bypass(self) -> None:
        def mutate(tree: ET.ElementTree) -> None:
            edge = tree.find("./diagram[@name='Skill Lifecycle']/mxGraphModel/root/mxCell[@id='p3-e6']")
            assert edge is not None
            edge.set("source", "p3-impact")

        with self.assertRaisesRegex(ValueError, "missing required edges|forbidden bypass"):
            self.validate_mutation(mutate)

    def test_rejects_disconnected_rollback(self) -> None:
        def mutate(tree: ET.ElementTree) -> None:
            root = tree.find("./diagram[@name='Project Setup']/mxGraphModel/root")
            assert root is not None
            edge = root.find("mxCell[@id='p2-e17']")
            assert edge is not None
            root.remove(edge)

        with self.assertRaisesRegex(ValueError, "missing required edges"):
            self.validate_mutation(mutate)

    def test_rejects_solid_recovery_path(self) -> None:
        def mutate(tree: ET.ElementTree) -> None:
            edge = tree.find("./diagram[@name='Skill Lifecycle']/mxGraphModel/root/mxCell[@id='p3-e18']")
            assert edge is not None
            edge.set("style", edge.get("style", "").replace("dashed=1;dashPattern=6 4;", ""))

        with self.assertRaisesRegex(ValueError, "not dashed"):
            self.validate_mutation(mutate)

    def test_rejects_overlapping_private_corridors(self) -> None:
        def mutate(tree: ET.ElementTree) -> None:
            edge = tree.find("./diagram[@name='Operating Map']/mxGraphModel/root/mxCell[@id='p1-e20']")
            assert edge is not None
            points = edge.findall("mxGeometry/Array[@as='points']/mxPoint")
            points[-1].set("x", "1000")

        with self.assertRaisesRegex(ValueError, "overlap the same h corridor"):
            self.validate_mutation(mutate)


if __name__ == "__main__":
    unittest.main()
