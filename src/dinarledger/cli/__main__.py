"""Entry point for ``python -m dinarledger``.

Delegates to :func:`dinarledger.cli.main.main` which builds the
argparse parser and dispatches to the appropriate subcommand.
"""

import sys

from dinarledger.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
