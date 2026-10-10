import sys
from pathlib import Path


project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from memory_app.server import main  # noqa: E402


if __name__ == "__main__":
    main()
