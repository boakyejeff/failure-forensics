"""Allow `python -m failure_forensics` to run the CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
