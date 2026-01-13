"""Entry point for python -m opencodereview.cli."""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m opencodereview.cli <command> [args...]")
        print("Commands: validate, convert")
        sys.exit(1)

    command = sys.argv[1]
    sys.argv = sys.argv[1:]  # Shift argv so click sees correct args

    if command == "validate":
        from . import validate_main
        validate_main()
    elif command == "convert":
        from . import convert_main
        convert_main()
    else:
        print(f"Unknown command: {command}")
        print("Commands: validate, convert")
        sys.exit(1)


if __name__ == "__main__":
    main()
