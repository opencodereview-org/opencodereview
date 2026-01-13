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


def _require_rich():
    try:
        import rich
    except ImportError:
        print("Error: rich not installed. Run: pip install opencodereview[tools]", file=sys.stderr)
        sys.exit(1)


def _get_git_config(key: str) -> str | None:
    """Get git config value."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def _find_editor() -> str | None:
    """Find an available editor."""
    import os
    import shutil

    # Check environment variables first
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return editor

    # Try common editors
    for cmd in ("vim", "vi", "nano"):
        if shutil.which(cmd):
            return cmd

    return None


def _edit_in_editor(initial: str = "", suffix: str = ".md") -> str | None:
    """Open $EDITOR for multiline input. Returns None if cancelled."""
    import os
    import tempfile
    import subprocess

    editor = _find_editor()
    if not editor:
        return None

    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(initial)
        temp_path = f.name

    try:
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            return None

        with open(temp_path) as f:
            content = f.read()

        # Strip the initial template marker if unchanged
        return content.strip() if content.strip() != initial.strip() else ""
    finally:
        os.unlink(temp_path)


def _multiline_input(console) -> str:
    """Fallback line-by-line input. Blank line ends input."""
    console.print("[dim]Enter content (blank line to finish):[/dim]")
    lines = []
    while True:
        try:
            line = console.input("  ")
            if not line:
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


def _prompt_content(console, category: str) -> str:
    """Prompt for multiline content using editor or fallback."""
    # Try editor first
    template = f"# Enter {category} content below (lines starting with # are ignored)\n\n"
    content = _edit_in_editor(template)

    if content is None:
        # Fallback to line-by-line
        content = _multiline_input(console)
    else:
        # Strip comment lines from editor content
        lines = [l for l in content.split("\n") if not l.startswith("#")]
        content = "\n".join(lines).strip()

    return content


def _find_review_files(path: Path) -> list[Path]:
    """Find all review files in a directory or return single file."""
    if path.is_file():
        return [path]

    files = []
    for ext in ("*.yaml", "*.yml", "*.json", "*.xml"):
        files.extend(path.glob(ext))
    return sorted(files)


def _get_issue_state(issue_id: str, activities: list) -> str:
    """Determine the state of an issue: open, resolved, or retracted."""
    for activity in activities:
        if activity.category == "resolved" and issue_id in activity.addresses:
            return "resolved"
        if activity.category == "retract" and issue_id in activity.addresses:
            return "retracted"
    return "open"


def _format_location(activity) -> str:
    """Format location info for display."""
    loc = activity.get_location()
    if not loc:
        return ""

    parts = []
    if loc.file:
        parts.append(loc.file)
    if loc.lines:
        line_strs = []
        for start, end in loc.lines:
            if start == end:
                line_strs.append(str(start))
            else:
                line_strs.append(f"{start}-{end}")
        if line_strs:
            parts.append(f":{','.join(line_strs)}")

    return "".join(parts)


def _list_issues(console, path, full, filter_state):
    """List issues from review files."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown

    files = _find_review_files(path)

    if not files:
        console.print(f"[yellow]No review files found in {path}[/yellow]")
        return

    found_issues = False
    for file_path in files:
        try:
            review = ocr.load(file_path)
        except Exception as e:
            console.print(f"[red]Error loading {file_path}: {e}[/red]")
            continue

        issues = [a for a in review.activities if a.category == "issue"]
        if not issues:
            continue

        # Filter issues by state
        filtered_issues = []
        for issue in issues:
            state = _get_issue_state(issue.id, review.activities)
            if filter_state == "all" or state == filter_state:
                filtered_issues.append((issue, state))

        if not filtered_issues:
            continue

        found_issues = True

        # Create table for this file
        table = Table(title=str(file_path), title_style="bold", show_header=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Severity", style="dim")
        table.add_column("State", style="dim")
        table.add_column("Location", style="blue")
        if not full:
            table.add_column("Summary", style="white", overflow="ellipsis", max_width=50)

        for issue, state in filtered_issues:
            # State formatting
            if state == "resolved":
                state_str = "[green]✓ resolved[/green]"
            elif state == "retracted":
                state_str = "[dim]✗ retracted[/dim]"
            else:
                state_str = "[yellow]○ open[/yellow]"

            # Severity formatting
            severity = issue.severity or "info"
            if severity == "critical":
                severity_str = f"[red bold]{severity}[/red bold]"
            elif severity == "error":
                severity_str = f"[red]{severity}[/red]"
            elif severity == "warning":
                severity_str = f"[yellow]{severity}[/yellow]"
            else:
                severity_str = f"[dim]{severity}[/dim]"

            location = _format_location(issue)

            if full:
                table.add_row(
                    issue.id or "",
                    severity_str,
                    state_str,
                    location,
                )
            else:
                # Extract first line as summary
                content = issue.content or ""
                first_line = content.split("\n")[0][:80] if content else ""
                table.add_row(
                    issue.id or "",
                    severity_str,
                    state_str,
                    location,
                    first_line,
                )

        console.print(table)

        # If --full, print content below table
        if full:
            for issue, state in filtered_issues:
                if issue.content:
                    console.print()
                    console.print(Panel(
                        Markdown(issue.content),
                        title=f"[cyan]{issue.id}[/cyan]",
                        border_style="dim"
                    ))

        console.print()

    if not found_issues:
        console.print("[dim]No issues found.[/dim]")


def _get_activity_title(activity) -> str:
    """Extract title/first line from activity content."""
    if not activity.content:
        return ""
    first_line = activity.content.strip().split("\n")[0]
    # Strip markdown bold markers
    if first_line.startswith("**") and "**" in first_line[2:]:
        end = first_line.index("**", 2)
        return first_line[2:end]
    return first_line[:60]


def _show_review(console, file, conversation_id):
    """Show individual review state and activities."""
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
    from rich.padding import Padding
    from collections import Counter

    try:
        review = ocr.load(file)
    except Exception as e:
        console.print(f"[red]Error loading {file}: {e}[/red]")
        sys.exit(1)

    # Build activity lookup by ID
    activity_by_id = {a.id: a for a in review.activities}

    # Review header
    console.print(Panel(f"[bold]{file}[/bold]", style="blue"))

    # Subject info
    if review.subject:
        subject_info = []
        subject_info.append(f"[bold]Type:[/bold] {review.subject.type}")
        if review.subject.name:
            subject_info.append(f"[bold]Name:[/bold] {review.subject.name}")
        if review.subject.scope:
            subject_info.append(f"[bold]Scope:[/bold] {', '.join(review.subject.scope)}")
        if review.subject.url:
            subject_info.append(f"[bold]URL:[/bold] {review.subject.url}")
        console.print("\n".join(subject_info))
        console.print()

    # Status and reviewers
    console.print(f"[bold]Status:[/bold] {review.status}")
    if review.reviewers:
        console.print(f"[bold]Reviewers:[/bold] {', '.join(review.reviewers)}")
    console.print()

    # Activity summary (use visible activities for count)
    visible = review.get_visible_activities()
    categories = Counter(a.category for a in visible)
    summary_parts = [f"{cat}: {count}" for cat, count in sorted(categories.items())]
    console.print(f"[bold]Activities:[/bold] {', '.join(summary_parts)}")
    console.print()

    if conversation_id is not None:
        # Filter to specific conversation if ID provided
        if conversation_id:
            # Find all activities related to this ID (the issue + activities addressing it)
            related_ids = {conversation_id}
            for a in visible:
                if conversation_id in a.addresses:
                    related_ids.add(a.id)
            activities_to_show = [a for a in visible if a.id in related_ids]
            if not activities_to_show:
                console.print(f"[yellow]No activity found with ID: {conversation_id}[/yellow]")
                return
        else:
            activities_to_show = visible

        console.print("[bold]Conversation:[/bold]")
        console.print()

        for activity in activities_to_show:
            # Format author
            author_name = ""
            author_meta = ""
            if activity.author:
                author_name = activity.author.name
                if activity.author.type == "agent":
                    author_meta = f" (agent: {activity.author.model or 'unknown'})"
            else:
                author_name = "unknown"

            # Format timestamp
            time_str = ""
            if activity.created:
                time_str = activity.created.isoformat()

            # Category color and state for issues
            cat = activity.category
            state_str = ""
            if cat == "issue":
                cat_style = "red"
                state = _get_issue_state(activity.id, review.activities)
                if state == "resolved":
                    state_str = " [green]✓ resolved[/green]"
                elif state == "retracted":
                    state_str = " [dim]✗ retracted[/dim]"
                else:
                    state_str = " [yellow]○ open[/yellow]"
            elif cat == "resolved":
                cat_style = "green"
            elif cat == "retract":
                cat_style = "dim"
            elif cat in ("approved", "merged"):
                cat_style = "green"
            elif cat in ("changes_requested", "closed"):
                cat_style = "red"
            elif cat == "suggestion":
                cat_style = "blue"
            else:
                cat_style = "cyan"

            # Header line
            header = Text()
            header.append(f"[{activity.id}] ", style="dim")
            header.append(cat, style=cat_style)
            if state_str:
                header.append_text(Text.from_markup(state_str))
            header.append(" by ")
            header.append(author_name)
            if author_meta:
                header.append(author_meta, style="dim")
            if time_str:
                header.append(" ")
                header.append(time_str, style="dim")

            console.print(header)

            # Location
            location = _format_location(activity)
            if location:
                console.print(f"  [blue]{location}[/blue]")

            # Addresses/references with titles
            if activity.addresses:
                addr_line = Text()
                addr_line.append("  addresses: ", style="dim")
                for i, addr_id in enumerate(activity.addresses):
                    if i > 0:
                        addr_line.append(", ", style="dim")
                    addr_line.append(addr_id, style="cyan bold")
                    # Look up referenced activity and show title
                    if addr_id in activity_by_id:
                        title = _get_activity_title(activity_by_id[addr_id])
                        if title:
                            addr_line.append(f" ({title})", style="dim")
                console.print(addr_line)

            # Content (rendered as markdown)
            if activity.content:
                md = Markdown(activity.content.strip())
                console.print(Padding(md, (0, 0, 0, 2)))

            console.print()


def _add_activity(console, file_path: Path, addressing_id: str | None):
    """Add a new activity to a review file."""
    from beaupy import select, prompt, confirm
    from rich.panel import Panel
    from rich.markdown import Markdown
    from datetime import datetime, timezone

    from opencodereview.models import Review, Subject, Author

    # Load or create review
    if file_path.exists():
        try:
            review = ocr.load(file_path)
        except Exception as e:
            console.print(f"[red]Error loading {file_path}: {e}[/red]")
            sys.exit(1)
    else:
        console.print(f"[yellow]Creating new review file: {file_path}[/yellow]")
        console.print()

        # Prompt for subject type
        subject_types = ["audit", "patch", "commit", "file", "directory", "snapshot"]
        console.print("[bold]Subject type[/bold] [dim](↑↓ to select, enter to confirm)[/dim]")
        subject_type = select(subject_types, cursor="→ ", cursor_style="cyan")
        if subject_type is None:
            console.print("[red]Cancelled[/red]")
            sys.exit(1)
        console.print()

        # Build subject based on type
        subject_kwargs = {"type": subject_type}

        # Helper to get stripped prompt value
        def get_input(label: str) -> str:
            return (prompt(label) or "").strip()

        # Common fields
        name = get_input("Name: ")
        if name:
            subject_kwargs["name"] = name

        url = get_input("URL: ")
        if url:
            subject_kwargs["url"] = url

        # Type-specific fields
        if subject_type == "audit":
            scope = get_input("Scope patterns (comma-separated, e.g. src/**, tests/*): ")
            if scope:
                subject_kwargs["scope"] = [s.strip() for s in scope.split(",") if s.strip()]

        elif subject_type == "patch":
            provider = get_input("Provider (e.g. github-pr, gitlab-mr): ")
            if provider:
                subject_kwargs["provider"] = provider

            provider_ref = get_input("Provider ref (e.g. PR number): ")
            if provider_ref:
                subject_kwargs["provider_ref"] = provider_ref

            repo = get_input("Repository (e.g. owner/repo): ")
            if repo:
                subject_kwargs["repo"] = repo

            base = get_input("Base branch: ")
            if base:
                subject_kwargs["base"] = base

            head = get_input("Head branch: ")
            if head:
                subject_kwargs["head"] = head

        elif subject_type == "commit":
            commit = get_input("Commit hash: ")
            if commit:
                subject_kwargs["commit"] = commit

            repo = get_input("Repository (e.g. owner/repo): ")
            if repo:
                subject_kwargs["repo"] = repo

            branch = get_input("Branch: ")
            if branch:
                subject_kwargs["branch"] = branch

        elif subject_type in ("file", "directory"):
            path = get_input("Path: ")
            if path:
                subject_kwargs["path"] = path

            ref = get_input("Commit/ref: ")
            if ref:
                subject_kwargs["ref"] = ref

        elif subject_type == "snapshot":
            tree = get_input("Tree hash: ")
            if tree:
                subject_kwargs["tree"] = tree

            branch = get_input("Branch: ")
            if branch:
                subject_kwargs["branch"] = branch

        subject = Subject(**subject_kwargs)
        review = Review(subject=subject)
        console.print()

    # Build activity lookup
    activity_by_id = {a.id: a for a in review.activities}

    # If addressing an existing activity, show it first
    addressed_activity = None
    if addressing_id:
        if addressing_id not in activity_by_id:
            console.print(f"[red]Activity not found: {addressing_id}[/red]")
            sys.exit(1)

        addressed_activity = activity_by_id[addressing_id]
        console.print(Panel(
            Markdown(addressed_activity.content or "(no content)"),
            title=f"[cyan]Addressing: [{addressed_activity.id}] {addressed_activity.category}[/cyan]",
            border_style="blue",
        ))
        console.print()

    # Determine available categories based on context
    if addressed_activity:
        if addressed_activity.category in ("issue", "security", "task"):
            categories = ["resolved", "note", "question"]
        elif addressed_activity.category == "question":
            categories = ["note", "resolved"]
        else:
            categories = ["resolved", "note", "retract"]
    else:
        categories = [
            "issue", "suggestion", "note", "praise", "question", "task", "security",
            "reviewed", "ignored",
            "closed", "merged", "reopened",
            "approved", "changes_requested", "commented",
        ]

    # Prompt for category
    console.print("[bold]Category[/bold] [dim](↑↓ to select, enter to confirm)[/dim]")
    category = select(categories, cursor="→ ", cursor_style="cyan")
    if category is None:
        console.print("[red]Cancelled[/red]")
        sys.exit(1)
    console.print()

    # Prompt for author
    git_name = _get_git_config("user.name")
    git_email = _get_git_config("user.email")

    author_name = (prompt("Author name: ", initial_value=git_name or "") or "").strip()
    author_email = (prompt("Author email: ", initial_value=git_email or "") or "").strip()

    if not author_name:
        console.print("[red]Author name is required[/red]")
        sys.exit(1)

    author = Author(
        name=author_name,
        email=author_email if author_email else None,
    )

    # Prompt for content
    content = _prompt_content(console, category)

    # Prompt for location (for commentary categories)
    file_loc = None
    lines_loc = None
    commentary_categories = ["issue", "suggestion", "note", "praise", "question", "task", "security"]
    if category in commentary_categories and not addressing_id:
        # Offer file selection via fuzzy finder or manual entry
        console.print("[bold]File location[/bold] [dim](↑↓ to select)[/dim]")
        file_choice = select(
            ["Search for file", "Enter path manually", "Skip"],
            cursor="→ ",
            cursor_style="cyan",
        )

        if file_choice == "Search for file":
            import subprocess
            import shutil

            # Get list of tracked files from git (respects .gitignore)
            try:
                git_result = subprocess.run(
                    ["git", "ls-files"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                files = git_result.stdout.strip().split("\n") if git_result.stdout.strip() else []
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback: list files excluding common ignore patterns
                from pathlib import Path
                ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache"}
                files = sorted(
                    str(p.relative_to(Path.cwd()))
                    for p in Path.cwd().rglob("*")
                    if p.is_file() and not any(part in ignore_dirs for part in p.parts)
                )

            if files:
                # Try fzf first (best experience), fall back to beaupy select
                if shutil.which("fzf"):
                    result = subprocess.run(
                        ["fzf", "--height=40%", "--reverse"],
                        input="\n".join(files),
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        file_loc = result.stdout.strip()
                else:
                    # Fall back to beaupy select
                    console.print("[dim]Tip: Install fzf for better fuzzy search[/dim]")
                    console.print("[bold]Select file[/bold] [dim](↑↓ to select)[/dim]")
                    file_loc = select(files[:100], cursor="→ ", cursor_style="cyan", pagination=True, page_size=15)
            else:
                console.print("[yellow]No files found[/yellow]")
        elif file_choice == "Enter path manually":
            file_loc = (prompt("File path: ") or "").strip()

        if file_loc:
            from rich.syntax import Syntax
            from rich.panel import Panel
            from pathlib import Path

            file_path_obj = Path(file_loc)

            while True:
                lines_str = (prompt("Lines (e.g., 5 or 1,3-10,15): ") or "").strip()
                if not lines_str:
                    break  # Skip lines

                try:
                    # Parse multiple lines and ranges: "1,3-10,15" -> [(1,1), (3,10), (15,15)]
                    lines_loc = []
                    for part in lines_str.split(","):
                        part = part.strip()
                        if "-" in part:
                            start, end = part.split("-", 1)
                            lines_loc.append((int(start.strip()), int(end.strip())))
                        else:
                            line_num = int(part)
                            lines_loc.append((line_num, line_num))

                    # Show syntax-highlighted preview and confirm
                    if lines_loc and file_path_obj.exists():
                        # Collect all line numbers to show
                        all_lines = set()
                        for start, end in lines_loc:
                            all_lines.update(range(start, end + 1))

                        # Read file and extract lines
                        content = file_path_obj.read_text()
                        file_lines = content.split("\n")

                        # Build preview with just selected lines
                        preview_lines = []
                        for line_num in sorted(all_lines):
                            if 1 <= line_num <= len(file_lines):
                                preview_lines.append(file_lines[line_num - 1])

                        if preview_lines:
                            # Detect language from extension
                            ext = file_path_obj.suffix.lstrip(".")
                            lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "rb": "ruby", "rs": "rust", "go": "go", "java": "java", "c": "c", "cpp": "cpp", "h": "c", "hpp": "cpp", "md": "markdown", "yaml": "yaml", "yml": "yaml", "json": "json", "xml": "xml", "html": "html", "css": "css", "sh": "bash", "bash": "bash", "zsh": "bash"}
                            lang = lang_map.get(ext, ext) or "text"

                            # Show with syntax highlighting
                            preview_text = "\n".join(preview_lines)
                            syntax = Syntax(preview_text, lang, theme="monokai", line_numbers=True, start_line=min(all_lines))
                            console.print(Panel(syntax, title=f"[cyan]{file_loc}[/cyan]", border_style="dim"))

                            # Confirm
                            console.print("[bold]Confirm selection?[/bold] [dim](↑↓ to select)[/dim]")
                            confirm = select(["Yes", "No, re-enter", "Skip lines"], cursor="→ ", cursor_style="cyan")
                            if confirm == "Yes":
                                break  # Keep lines_loc and continue
                            elif confirm == "Skip lines":
                                lines_loc = None
                                break
                            # "No, re-enter" continues the loop
                        else:
                            console.print("[yellow]No valid lines in range[/yellow]")
                    else:
                        break  # File doesn't exist or no lines, just accept input

                except ValueError:
                    console.print("[yellow]Invalid line format, try again[/yellow]")

    # Prompt for severity (for issue/security)
    severity = None
    if category in ("issue", "security"):
        console.print("[bold]Severity[/bold] [dim](↑↓ to select)[/dim]")
        severity = select(
            ["info", "warning", "error", "critical"],
            cursor="→ ",
            cursor_style="cyan",
            cursor_index=1,  # default to "warning"
        )
        console.print()

    # Prompt for activity ID
    default_id = f"{category}-{len(review.activities) + 1}"
    if addressing_id:
        default_id = f"{addressing_id}-{category}"
    activity_id = (prompt("Activity ID: ", initial_value=default_id) or "").strip() or default_id

    # Build activity data
    activity_data = {
        "id": activity_id,
        "category": category,
        "author": author.model_dump(exclude_none=True),
        "content": content if content else None,
        "created": datetime.now(timezone.utc).isoformat(),
    }

    if addressing_id:
        activity_data["addresses"] = [addressing_id]

    if file_loc:
        activity_data["file"] = file_loc
    if lines_loc:
        activity_data["lines"] = lines_loc
    if severity:
        activity_data["severity"] = severity

    # Add activity to review
    # We need to serialize and re-parse to get proper Activity type
    review_data = review.model_dump(exclude_none=True, mode="json")
    review_data["activities"].append(activity_data)

    # Save
    try:
        updated_review = Review.model_validate(review_data)
        ocr.dump(updated_review, file_path)
        console.print()
        console.print(f"[green]Added activity [{activity_id}] to {file_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving: {e}[/red]")
        sys.exit(1)


def reviews_main():
    """List and display issues from OpenCodeReview files."""
    _require_click()
    _require_rich()

    from rich.console import Console

    @click.group()
    @click.pass_context
    def reviews(ctx):
        """OpenCodeReview file viewer and editor.

        Use 'reviews list <path>' to list issues.
        Use 'reviews show <file>' to show review details.
        Use 'reviews add <file>' to add a new activity.
        """
        ctx.ensure_object(dict)
        ctx.obj["console"] = Console()

    @reviews.command("list")
    @click.argument("path", type=click.Path(exists=True, path_type=Path))
    @click.option("--full", is_flag=True, help="Include full body of issues")
    @click.option("--filter", "filter_state", type=click.Choice(["open", "resolved", "retracted", "all"]), default="all", help="Filter by state")
    @click.pass_context
    def list_cmd(ctx, path, full, filter_state):
        """List issues from OpenCodeReview files.

        PATH can be a directory or a single review file.
        """
        _list_issues(ctx.obj["console"], path, full, filter_state)

    @reviews.command("show")
    @click.argument("file", type=click.Path(exists=True, path_type=Path))
    @click.option("--full", "-f", is_flag=True, help="Show all activities")
    @click.option("--id", "activity_id", default=None, help="Filter to specific activity ID and related")
    @click.pass_context
    def show_cmd(ctx, file, full, activity_id):
        """Show individual review state and activities."""
        # If --id is given, imply --full
        if activity_id:
            conversation_id = activity_id
        elif full:
            conversation_id = ""
        else:
            conversation_id = None
        _show_review(ctx.obj["console"], file, conversation_id)

    @reviews.command("add")
    @click.argument("file", type=click.Path(path_type=Path))
    @click.argument("activity_id", required=False)
    @click.pass_context
    def add_cmd(ctx, file, activity_id):
        """Add a new activity to a review file.

        FILE is the review file to add to (created if doesn't exist).
        ACTIVITY_ID optionally specifies an existing activity to address.
        """
        _add_activity(ctx.obj["console"], file, activity_id)

    reviews()

