"""Mock for API Backend."""

import json
from pathlib import Path
from typing import Any, Union

TEST_USERNAME = "some_user"
TEST_PASSWORD = "my_secret"


RESPONSE_DIR = Path(__file__).parent / "replys"


def load_response(path: Union[Path, str]) -> Any:
    """Load a stored response.

    Text fixtures (e.g. ``.url`` files) are stripped of surrounding
    whitespace so a trailing newline added by EOF-normalizing hooks
    doesn't corrupt the value (URLs in these fixtures are single-line).
    """
    with open(path, "rb") as file:
        if Path(path).suffix == ".json":
            return json.load(file)
        return file.read().decode("UTF-8").strip()
