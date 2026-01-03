"""Progress indicator utilities using rich library."""

import sys
from contextlib import contextmanager

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)


@contextmanager
def progress_spinner(message: str = "Loading", estimate: str | None = None):
    """Context manager for indeterminate spinner (single operations).

    Use for single long-running API calls where duration is unknown.
    Progress indicator disappears after completion (transient).

    Args:
        message: Description of the operation
        estimate: Optional time estimate to append to message (e.g., "~5s")

    Usage:
        with progress_spinner("Rotating token", "~5s"):
            result = provider.rotate(token)
    """
    full_message = f"{message} ({estimate})" if estimate else message

    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        transient=True,
        disable=not sys.stderr.isatty(),
    )

    with progress:
        progress.add_task(full_message, total=None)
        yield progress
