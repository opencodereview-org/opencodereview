"""I/O functions for loading and saving OpenCodeReview files."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TextIO

import yaml

from .models import Review


def load(source: str | Path | TextIO, format: str | None = None) -> Review:
    """Load a review from a file or file-like object.

    Args:
        source: File path or file-like object
        format: Format to use ('yaml', 'json', 'xml'). Auto-detected from extension if not specified.

    Returns:
        Review object
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if format is None:
            format = _detect_format(path)
        with open(path) as f:
            content = f.read()
    else:
        content = source.read()
        if format is None:
            raise ValueError("format must be specified when loading from file-like object")

    if format == "yaml":
        data = yaml.safe_load(content)
    elif format == "json":
        data = json.loads(content)
    elif format == "xml":
        data = _parse_xml(content)
    else:
        raise ValueError(f"Unsupported format: {format}")

    return Review.model_validate(data)


def dump(review: Review, dest: str | Path | TextIO, format: str | None = None) -> None:
    """Save a review to a file or file-like object.

    Args:
        review: Review object to save
        dest: File path or file-like object
        format: Format to use ('yaml', 'json'). Auto-detected from extension if not specified.
    """
    # Use exclude_none but not exclude_unset to preserve auto-generated IDs
    data = review.model_dump(exclude_none=True, mode="json")

    if isinstance(dest, (str, Path)):
        path = Path(dest)
        if format is None:
            format = _detect_format(path)
        with open(path, "w") as f:
            _write_format(f, data, format)
    else:
        if format is None:
            raise ValueError("format must be specified when saving to file-like object")
        _write_format(dest, data, format)


def _detect_format(path: Path) -> str:
    """Detect format from file extension."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return "yaml"
    elif suffix == ".json":
        return "json"
    elif suffix == ".xml":
        return "xml"
    else:
        # Default to yaml
        return "yaml"


def _write_format(f: TextIO, data: dict, format: str) -> None:
    """Write data in specified format."""
    if format == "yaml":
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    elif format == "json":
        json.dump(data, f, indent=2, default=str)
    elif format == "xml":
        xml_str = _to_xml(data)
        f.write(xml_str)
    else:
        raise ValueError(f"Unsupported format for writing: {format}")


# =============================================================================
# XML Parsing
# =============================================================================


def _parse_xml(content: str) -> dict:
    """Parse XML content into a dict."""
    root = ET.fromstring(content)
    return _xml_element_to_dict(root)


def _xml_element_to_dict(elem: ET.Element) -> dict:
    """Convert an XML element to a dictionary."""
    result = {}

    for child in elem:
        tag = child.tag

        # Handle special array elements
        if tag == "activities":
            result["activities"] = [_xml_element_to_dict(a) for a in child.findall("activity")]
        elif tag == "replies":
            result["replies"] = [_xml_element_to_dict(a) for a in child.findall("activity")]
        elif tag == "lines":
            result["lines"] = _parse_lines(child)
        elif tag == "mentions":
            result["mentions"] = [m.text for m in child.findall("mention") if m.text]
        elif tag == "supersedes":
            result["supersedes"] = [i.text for i in child.findall("id") if i.text]
        elif tag == "addresses":
            result["addresses"] = [i.text for i in child.findall("id") if i.text]
        elif tag == "conditions":
            result["conditions"] = [c.text for c in child.findall("condition") if c.text]
        elif tag == "scope":
            result["scope"] = [p.text for p in child.findall("pattern") if p.text]
        elif tag in ("author", "location", "selector", "subject", "agent_context"):
            result[tag] = _xml_element_to_dict(child)
        else:
            # Simple text element
            if child.text and child.text.strip():
                # Strip leading/trailing whitespace but preserve internal structure
                value = child.text.strip()
                # Convert booleans, keep everything else as strings
                # (Pydantic will coerce types during validation)
                if value.lower() == "true":
                    result[tag] = True
                elif value.lower() == "false":
                    result[tag] = False
                else:
                    # Preserve trailing newline if original had one (for multiline content)
                    if child.text.rstrip(" \t").endswith("\n"):
                        value = value + "\n"
                    result[tag] = value

    return result


def _parse_lines(lines_elem: ET.Element) -> list:
    """Parse lines element into list of [start, end] tuples."""
    result = []
    for range_elem in lines_elem.findall("range"):
        start = range_elem.find("start")
        end = range_elem.find("end")
        if start is not None and end is not None and start.text and end.text:
            result.append([int(start.text), int(end.text)])
    return result


# =============================================================================
# XML Writing
# =============================================================================


def _to_xml(data: dict) -> str:
    """Convert a dict to XML string."""
    root = ET.Element("review")
    _dict_to_xml(data, root)
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _dict_to_xml(data: dict, parent: ET.Element) -> None:
    """Convert a dict to XML elements under parent."""
    for key, value in data.items():
        if value is None:
            continue

        if key == "activities":
            activities_elem = ET.SubElement(parent, "activities")
            for activity in value:
                activity_elem = ET.SubElement(activities_elem, "activity")
                _dict_to_xml(activity, activity_elem)
        elif key == "replies":
            replies_elem = ET.SubElement(parent, "replies")
            for reply in value:
                reply_elem = ET.SubElement(replies_elem, "activity")
                _dict_to_xml(reply, reply_elem)
        elif key == "lines":
            lines_elem = ET.SubElement(parent, "lines")
            for line_range in value:
                range_elem = ET.SubElement(lines_elem, "range")
                start = ET.SubElement(range_elem, "start")
                start.text = str(line_range[0])
                end = ET.SubElement(range_elem, "end")
                end.text = str(line_range[1])
        elif key == "mentions":
            mentions_elem = ET.SubElement(parent, "mentions")
            for mention in value:
                m = ET.SubElement(mentions_elem, "mention")
                m.text = mention
        elif key == "supersedes":
            supersedes_elem = ET.SubElement(parent, "supersedes")
            for id_val in value:
                i = ET.SubElement(supersedes_elem, "id")
                i.text = id_val
        elif key == "addresses":
            addresses_elem = ET.SubElement(parent, "addresses")
            for id_val in value:
                i = ET.SubElement(addresses_elem, "id")
                i.text = id_val
        elif key == "conditions":
            conditions_elem = ET.SubElement(parent, "conditions")
            for cond in value:
                c = ET.SubElement(conditions_elem, "condition")
                c.text = cond
        elif key == "scope":
            scope_elem = ET.SubElement(parent, "scope")
            for pattern in value:
                p = ET.SubElement(scope_elem, "pattern")
                p.text = pattern
        elif key in ("author", "location", "selector", "subject", "agent_context"):
            child_elem = ET.SubElement(parent, key)
            _dict_to_xml(value, child_elem)
        elif isinstance(value, dict):
            child_elem = ET.SubElement(parent, key)
            _dict_to_xml(value, child_elem)
        elif isinstance(value, list):
            # Generic list handling
            list_elem = ET.SubElement(parent, key)
            for item in value:
                if isinstance(item, dict):
                    item_elem = ET.SubElement(list_elem, "item")
                    _dict_to_xml(item, item_elem)
                else:
                    item_elem = ET.SubElement(list_elem, "item")
                    item_elem.text = str(item)
        else:
            elem = ET.SubElement(parent, key)
            elem.text = str(value)
