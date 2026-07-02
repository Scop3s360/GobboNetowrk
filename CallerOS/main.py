"""
CallerOS — Application Entry Point
===================================
Run with:

    python main.py

The entry point is deliberately thin.  All logic lives in Application.
"""

import sys

from core.application import Application
from core.exceptions import CallerOSError


def main() -> int:
    """
    Bootstrap CallerOS and keep it running until interrupted.

    Returns:
        0 on clean exit, 1 on startup failure.
    """
    app = Application()
    try:
        app.startup()
    except CallerOSError as exc:
        # Logging may or may not be available at this point — always print
        # to stderr so the operator sees the failure regardless.
        print(f"[CallerOS] FATAL: {exc}", file=sys.stderr)
        return 1

    print("[CallerOS] Running — press Ctrl-C to stop.")

    try:
        # Park the process.  In Stage 1 there is no event loop or server yet.
        # Ctrl-C delivers SIGINT, which the Application signal handler converts
        # to a graceful shutdown followed by sys.exit(0).
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
