"""Tests for CLI tools."""

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


class TestValidate:
    """Tests for ocr-validate command."""

    def test_validate_yaml_files(self):
        """Validate all YAML example files."""
        yaml_files = list(EXAMPLES_DIR.glob("**/*.yaml"))
        assert len(yaml_files) > 0, "No YAML files found"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "validate", *[str(f) for f in yaml_files]],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"

    def test_validate_json_files(self):
        """Validate all JSON example files."""
        json_files = list(EXAMPLES_DIR.glob("**/*.json"))
        assert len(json_files) > 0, "No JSON files found"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "validate", *[str(f) for f in json_files]],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"

    def test_validate_xml_files(self):
        """Validate all XML example files."""
        xml_files = list(EXAMPLES_DIR.glob("**/*.xml"))
        assert len(xml_files) > 0, "No XML files found"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "validate", *[str(f) for f in xml_files]],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"

    def test_validate_nonexistent_file(self):
        """Validate returns error for nonexistent file."""
        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "validate", "nonexistent.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_validate_quiet_mode(self):
        """Validate quiet mode only shows errors."""
        yaml_file = next(EXAMPLES_DIR.glob("**/*.yaml"))
        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "validate", "-q", str(yaml_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout == "", "Quiet mode should not output anything on success"


class TestConvert:
    """Tests for ocr-convert command."""

    def test_convert_yaml_to_json(self, tmp_path):
        """Convert YAML to JSON."""
        yaml_file = EXAMPLES_DIR / "yaml" / "00-minimal.yaml"
        json_output = tmp_path / "output.json"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", str(yaml_file), str(json_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Conversion failed:\n{result.stdout}\n{result.stderr}"
        assert json_output.exists()

        # Verify the output is valid JSON that can be loaded
        import opencodereview as ocr
        review = ocr.load(json_output)
        assert review.version == "0.1"

    def test_convert_json_to_yaml(self, tmp_path):
        """Convert JSON to YAML."""
        json_file = EXAMPLES_DIR / "json" / "00-minimal.json"
        yaml_output = tmp_path / "output.yaml"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", str(json_file), str(yaml_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Conversion failed:\n{result.stdout}\n{result.stderr}"
        assert yaml_output.exists()

        import opencodereview as ocr
        review = ocr.load(yaml_output)
        assert review.version == "0.1"

    def test_convert_yaml_to_xml(self, tmp_path):
        """Convert YAML to XML."""
        yaml_file = EXAMPLES_DIR / "yaml" / "00-minimal.yaml"
        xml_output = tmp_path / "output.xml"

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", str(yaml_file), str(xml_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Conversion failed:\n{result.stdout}\n{result.stderr}"
        assert xml_output.exists()

        import opencodereview as ocr
        review = ocr.load(xml_output)
        assert review.version == "0.1"

    def test_convert_refuses_overwrite(self, tmp_path):
        """Convert refuses to overwrite existing file without -f."""
        yaml_file = EXAMPLES_DIR / "yaml" / "00-minimal.yaml"
        json_output = tmp_path / "output.json"
        json_output.write_text("{}")

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", str(yaml_file), str(json_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "exists" in result.stderr.lower()

    def test_convert_force_overwrite(self, tmp_path):
        """Convert overwrites existing file with -f."""
        yaml_file = EXAMPLES_DIR / "yaml" / "00-minimal.yaml"
        json_output = tmp_path / "output.json"
        json_output.write_text("{}")

        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", "-f", str(yaml_file), str(json_output)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Conversion failed:\n{result.stdout}\n{result.stderr}"

        import opencodereview as ocr
        review = ocr.load(json_output)
        assert review.version == "0.1"

    def test_convert_nonexistent_input(self, tmp_path):
        """Convert returns error for nonexistent input file."""
        result = subprocess.run(
            [sys.executable, "-m", "opencodereview.cli", "convert", "nonexistent.yaml", str(tmp_path / "out.json")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
