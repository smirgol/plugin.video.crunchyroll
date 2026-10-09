# Test Suite

Unit and integration tests for the Crunchyroll Kodi plugin.

## Quick Start

### Install Dependencies

```bash
uv sync --extra test --extra dev
```

Dependencies are split into optional extras in `pyproject.toml`:

- `test` - pytest, python-dotenv, requests-mock, ... (running the test suite)
- `dev` - ruff (linting/formatting)

`uv sync --extra test --extra dev` materialises a `.venv` with everything pinned
by `uv.lock`. `uv run pytest` also pulls in the `test` extra automatically;
standalone scripts need it explicitly via `uv run --extra test python ...`.

`pyproject.toml` and `uv.lock` are committed (like `composer.json` /
`composer.lock`) so the test and lint environment is reproducible. They are dev
tooling only - the shipped Kodi addon resolves its runtime imports via
`addon.xml`, not via `pyproject.toml`.

### Run Unit Tests

```bash
# Unit tests only (fast, ~0.2s) - no credentials required
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=resources.lib --cov-report=html
```

Unit tests run against captured fixtures (`tests/fixtures/captured_responses.json`)
and mocked HTTP. They do not hit the network. If you switched API endpoints,
re-capture the fixtures first (see below) so the unit tests validate against
real response shapes.

## Linting

Linting and formatting use [Ruff](https://docs.astral.sh/ruff/). Config lives in
`pyproject.toml` under `[tool.ruff]` (line length 120, rule sets E/F/W/I/UP/B,
`resources/modules` excluded as vendored third-party code).

```bash
# Report issues
uv run ruff check .

# Auto-fix the safe subset
uv run ruff check --fix .

# Format
uv run ruff format .
```

## Credentials Setup

Both **capturing** and the **integration tests** make real API calls and need
credentials. Set them up once:

1. Copy the example env file:
   ```bash
   cp tests/.env.example tests/.env
   ```

2. Add your credentials to `tests/.env`:
   ```bash
   CRUNCHYROLL_REFRESH_TOKEN=your_token_here
   CRUNCHYROLL_DEVICE_ID=your_device_id_here
   ```
   Get these from your Kodi addon (start a fresh device auth on your real
   client) - see `tests/.env.example` for where to find them.

### Pitfall: the AUTHORIZATION client credential rotates

Token refresh uses a hardcoded `Basic ...` client credential
(`API.AUTHORIZATION` in `resources/lib/api.py`). Crunchyroll **rotates this
value every few weeks**. When it is stale, token refresh fails with:

```
401 - {"code":"auth.obtain_access_token.client_inactive","error":"invalid_client"}
```

This is **not** an expired refresh token - it is the client credential.
`tests/fixtures/token_manager.py` reuses `API.AUTHORIZATION` directly (single
source of truth), so renewing the value in `api.py` fixes both the plugin and
the tests at once.

## Capturing API Responses

Unit tests assert against real response shapes stored in
`tests/fixtures/captured_responses.json`. Re-capture these:

- **At least once** before running the unit tests for the first time, and
- **after every API endpoint change** (e.g. switching seasons/episodes
  endpoints), so the fixtures reflect the new schema.

`tests/capture_responses.py` is a **standalone script**, not a pytest test.
Run it as a plain script (requires valid credentials and the `test` extra):

```bash
uv run --extra test python tests/capture_responses.py
```

> Do **not** run it via `pytest tests/capture_responses.py`. pytest only
> imports the file during collection and swallows its output on the fd level -
> it looks like "nothing happened". The script guards against this and aborts
> with a clear message if imported by pytest.

It walks through profile, index, browse, search, seasons, episodes, watchlist,
history and playheads, prints a per-endpoint progress log, and writes the
result to `tests/fixtures/captured_responses.json`.

To compare old vs new API shapes, capture on the pre-migration commit, rename
the output (e.g. `captured_responses.old.json`), switch to the new commit and
capture again.

## Integration Tests

Integration tests make real API calls (see Credentials Setup above).

```bash
uv run pytest tests/ -m integration -v
```

## Project Structure

```
tests/
├── capture_responses.py     # Standalone fixture capture script
│
├── unit/                    # Unit tests (mocked HTTP, captured fixtures)
│   ├── test_api_auth.py
│   ├── test_api_content.py
│   ├── test_api_streaming.py
│   ├── test_api_exception_handling.py
│   ├── test_model_mapping.py
│   └── test_get_listables.py  # Type detection + DTO mapping (content/v2)
│
├── integration/             # Integration tests (real API)
│   ├── test_auth_flow.py
│   ├── test_content_api.py
│   └── test_streaming_api.py
│
└── fixtures/
    ├── token_manager.py     # Auto-refresh token mgmt (reuses api.py consts)
    ├── api_responses.py     # Mock responses
    └── captured_responses.json  # Real API responses
```

## Key Points

### API Response Structure

```python
# Legacy beta-api endpoints (Browse, Search, Watchlist) use "items"
data = api.make_request("GET", api.BROWSE_ENDPOINT)
assert "items" in data

# Migrated content/v2 endpoints (Seasons, Episodes) and History use "data"
data = api.make_request("GET", api.HISTORY_ENDPOINT)
assert "data" in data
```

### Type Detection / DTO Mapping

`utils.get_listables_from_response()` maps API items to DTOs. Mixed lists
(browse/search/watchlist) carry a type identifier per item (`panel.type` /
`type` / `__class__`). The migrated content/v2 endpoints (seasons, episodes) no
longer carry one, so the caller passes the known type explicitly:

```python
get_listables_from_response(req.get('data') or req.get('items'),
                            item_type_hint='season')
```

Detection order: per-item type first, `item_type_hint` as fallback. See
`test_get_listables.py`.

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
    mock_response.headers = {"Content-Type": "application/json"}

    with patch.object(self.api.http, 'request', return_value=mock_response):
        result = self.api.make_request("GET", url)
```
