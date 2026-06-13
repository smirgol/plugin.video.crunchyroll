# Test Suite

Unit and integration tests for the Crunchyroll Kodi plugin.

## Quick Start

### Install Dependencies

```bash
uv sync
```

### Run Tests

```bash
# Unit tests only (fast, ~0.2s)
uv run pytest tests/unit/ -v

# All tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/unit/ --cov=resources.lib --cov-report=html
```

## Integration Tests

Integration tests make real API calls and require credentials.

### Setup

1. Copy the example env file:
   ```bash
   cp tests/.env.example tests/.env
   ```

2. Add your credentials to `tests/.env`:
   ```bash
   CRUNCHYROLL_REFRESH_TOKEN=your_token_here
   CRUNCHYROLL_DEVICE_ID=your_device_id_here
   ```
   
3. Verify that Authorization is up to date in `tests/fixtures/token_manager.py`:
    ```bash
        AUTHORIZATION = "Basic bm1oaGcwbDZ4eXhjZm02aHQ2aGY6SjR6bU1mdjNkMVFkWHk4dDk2d1NjeDdoUnkzclBHLTM="
        USER_AGENT = "Crunchyroll/ANDROIDTV/3.54.3_22302 (Android 14; en-US; Chromecast)"
    ```

4. Run integration tests:
   ```bash
   uv run pytest tests/ -m integration -v
   ```

## Project Structure

```
tests/
├── unit/                    # Unit tests (mocked HTTP)
│   ├── test_api_auth.py
│   ├── test_api_content.py
│   ├── test_api_streaming.py
│   ├── test_api_exception_handling.py
│   └── test_model_mapping.py
│
├── integration/             # Integration tests (real API)
│   ├── test_auth_flow.py
│   ├── test_content_api.py
│   └── test_streaming_api.py
│
└── fixtures/
    ├── token_manager.py     # Auto-refresh token management
    ├── api_responses.py     # Mock responses
    └── captured_responses.json  # Real API responses (8 endpoints)
```

## Key Points

### API Response Structure

```python
# Browse, Search, Seasons, Episodes, Watchlist use "items"
data = api.make_request("GET", api.BROWSE_ENDPOINT)
assert "items" in data

# ONLY History uses "data"
data = api.make_request("GET", api.HISTORY_ENDPOINT)
assert "data" in data
```

### make_request() Returns JSON Directly

```python
# Correct
data = api.make_request("GET", url)
assert "items" in data  # Already a JSON dict

# Wrong
response = api.make_request("GET", url)
data = response.json()  # Error! No .json() method
```

### Mocking Pattern

See `test_api_exception_handling.py` for working examples.

```python
def setup_method(self):
    with patch('resources.lib.api.default_request_headers'), \
         patch('resources.lib.globals.G'):
        self.api = API()
        self.api.account_data = AccountData({...})

def test_something(self):
    mock_response = Mock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {...}
    mock_response.text = json.dumps({...})
    mock_response.headers 