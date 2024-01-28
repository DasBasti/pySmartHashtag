"""Mock for API Backend."""

import json
from pathlib import Path
from typing import Any, Union

TEST_USERNAME = "some_user"
TEST_PASSWORD = "my_secret"


RESPONSE_DIR = Path(__file__).parent / "replys"


def load_response(path: Union[Path, str]) -> Any:
    """Load a stored response."""
    with open(path, "rb") as file:
        if Path(path).suffix == ".json":
            return json.load(file)
        return file.read().decode("UTF-8")
