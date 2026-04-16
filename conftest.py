"""Root conftest — adds the workspace root to sys.path so local packages resolve."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
