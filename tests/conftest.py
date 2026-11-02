import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def sock_dir():
    """Short temp dir for Unix sockets (pytest's tmp_path can exceed the
    108-byte sun_path limit)."""
    with tempfile.TemporaryDirectory(prefix="prc-") as d:
        yield Path(d)
