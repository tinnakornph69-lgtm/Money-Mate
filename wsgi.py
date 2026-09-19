"""Production and local entry point for the completed MoneyMate app."""

import os
import sys

from app import app
from moneymate_bootstrap import configure


configure(app)


if __name__ == "__main__":
    value = os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else "5000")
    try:
        port = int(value)
    except (TypeError, ValueError):
        port = 5000
    app.run(debug=False, host="0.0.0.0", port=port)
