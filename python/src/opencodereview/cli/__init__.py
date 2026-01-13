"""CLI tools for OpenCodeReview."""

import json
import sys
from pathlib import Path

try:
    import click
except ImportError:
    click = None

import opencodereview as ocr


def _require_click():
    if click is None:
        print("Error: click not installed. Run: pip install opencodereview[tools]", file=sys.stderr)
        sys.exit(1)


def validate_main():
    """Validate OpenCodeReview files against the schema."""
    _require_click()

    try:
        import jsonschema
    except ImportError:
        print("Error: jsonschema not installed. Run: pip install opencodereview[tools]", file=sys.stderr)
        sys.exit(1)

    @click.command()
    @click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
    @click.option("-q", "--quiet", is_flag=True, help="Only output errors")
    def validate(files, quiet):
        """Validate OpenCodeReview files against the JSON schema."""
        schema = _load_schema()
        exit_code = 0

        for file_path in files:
            try:
                # Load via library (validates with Pydantic)
                review = ocr.load(file_path)
                # Also validate against JSON schema
                data = review.model_dump(exclude_none=True, mode="json")
                errors = _validate_schema(data, schema, jsonschema)

                if errors:
                    click.echo(f"FAIL: {file_path}")
                    for error in errors:
                        click.echo(f"  - {error}")
                    exit_code = 1
                elif not quiet:
                    click.echo(f"OK: {file_path}")

            except Exception as e:
                click.echo(f"FAIL: {file_path}")
                click.echo(f"  - {e}")
                exit_code = 1

        sys.exit(exit_code)

    validate()


def convert_main():
    """Convert OpenCodeReview files between formats."""
    _require_click()

    @click.command()
    @click.argument("input", type=click.Path(exists=True, path_type=Path))
    @click.argument("output", type=click.Path(path_type=Path))
    @click.option("-f", "--force", is_flag=True, help="Overwrite existing output file")
    def convert(input, output, force):
        """Convert OpenCodeReview files between formats (yaml, json, xml)."""
        if output.exists() and not force:
            click.echo(f"Error: Output file exists: {output} (use -f to overwrite)", err=True)
            sys.exit(1)

        try:
            review = ocr.load(input)
            ocr.dump(review, output)
            click.echo(f"Converted {input} -> {output}")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    convert()


def _load_schema() -> dict:
    """Load the JSON schema."""
    pkg_dir = Path(__file__).parent  # cli/
    schema_paths = [
        pkg_dir.parent.parent.parent.parent / "schema" / "opencodereview.schema.json",  # repo root
        pkg_dir.parent / "schema" / "opencodereview.schema.json",  # bundled in package
    ]
    for schema_path in schema_paths:
        if schema_path.exists():
            with open(schema_path) as f:
                return json.load(f)
    raise FileNotFoundError("Could not find opencodereview.schema.json")


def _validate_schema(data: dict, schema: dict, jsonschema) -> list[str]:
    """Validate data against JSON schema. Returns list of errors."""
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "(root)"
        errors.append(f"{path}: {error.message}")
    return errors
