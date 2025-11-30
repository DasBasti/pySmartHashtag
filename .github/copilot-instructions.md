# Copilot Instructions for pySmartHashtag

## Project Overview

pySmartHashtag is a Python API wrapper library for Smart #1 and #3 Cloud Services. It provides async access to Smart vehicle data and is used as a backend for the Smart Hashtag Home Assistant integration.

## Development Setup

### Requirements

- Python 3.9 or higher (supports 3.9, 3.10, 3.11, 3.12)
- pip for package management

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Install package in editable mode
pip install -e .
```

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=pysmarthashtag --cov-report=term-missing pysmarthashtag/tests/

# Run a specific test file
pytest pysmarthashtag/tests/test_account.py
```

### Linting and Formatting

This project uses multiple linting tools:

```bash
# Run ruff linter
ruff check .

# Run ruff formatter
ruff format .

# Run flake8
flake8 . --max-line-length=120

# Run pre-commit hooks
pre-commit run --all-files
```

## Code Style Guidelines

- **Line length**: 120 characters maximum
- **Formatter**: Use `ruff format` (Black-compatible) for formatting
- **Imports**: Use `isort` compatible ordering (handled by ruff)
- **Docstrings**: Follow PEP 257 conventions (D2xx rules configured in ruff)
- **Type hints**: Use Python typing for function signatures

### Ruff Configuration

The project uses ruff with the following rule sets:
- C (complexity)
- D (docstrings)
- E (pycodestyle)
- F (pyflakes)
- I (isort)
- W (pycodestyle)
- UP (pyupgrade)

## Project Structure

```
pysmarthashtag/
├── __init__.py          # Package initialization
├── account.py           # SmartAccount class for API access
├── cli.py               # Command line interface
├── const.py             # Constants and configuration
├── models.py            # Data models and exceptions
├── api/
│   ├── authentication.py  # Authentication handling
│   ├── client.py          # HTTP client implementation
│   ├── log_sanitizer.py   # Log sanitization utilities
│   └── utils.py           # API utility functions
├── control/             # Vehicle control commands
├── vehicle/             # Vehicle data models
└── tests/
    ├── conftest.py      # Test fixtures
    ├── common.py        # Test utilities
    ├── replys/          # Mock API responses
    └── test_*.py        # Test files
```

## Testing Conventions

- Use `pytest` with `pytest-asyncio` for async tests
- Use `respx` for mocking HTTP requests
- Place test fixtures in `conftest.py`
- Store mock API responses in `tests/replys/` directory
- Test files should be named `test_*.py`
- Minimum code coverage requirement: 80%

## Async Patterns

This library uses async/await patterns. When writing new code:

```python
async def example_method(self) -> dict:
    """Example async method."""
    async with SmartClient(self.config) as client:
        response = await client.get(url, headers=headers)
        return response.json()
```

## Error Handling

Use the custom exception classes defined in `models.py`:
- `SmartAuthError` - Authentication failures
- `SmartTokenRefreshNecessary` - Token refresh required
- `SmartHumanCarConnectionError` - Human-car connection issues

## Logging

Use the standard Python logging module:

```python
import logging
_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("Debug message")
```

Use `sanitize_log_data()` from `api.log_sanitizer` when logging sensitive data.

## Dependencies

Main dependencies:
- `httpx` - Async HTTP client
- `pycryptodome` - Cryptographic functions
- `pyjwt` - JWT token handling

Test dependencies:
- `pytest`, `pytest-asyncio`, `pytest-cov`
- `respx` - HTTP mocking
- `ruff` - Linting and formatting
