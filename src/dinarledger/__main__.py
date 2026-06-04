"""Entry point for ``python -m dinarledger``.

Delegates to :func:`dinarledger.cli.main.main`.
"""

import sys

from dinarledger.cli.main import main

sys.exit(main())
