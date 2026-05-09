"""Allow `python -m dectalk` to invoke the CLI."""

from dectalk.cli import main

raise SystemExit(main())
