# Keka Expense Manager

CLI tool for authenticating with Keka HR and managing expense claims.

## Components

| Component | Description |
|-----------|--------------|
| `keka-main/keka.py` | Main CLI: login, logout, curl, expense |

## Prerequisites

- Python 3.13+ with [uv](https://github.com/astral-sh/uv) (keka.py is a `uv run --script` file with inline dependencies)
- Google Chrome (for browser-based OAuth login)

## Usage

```bash
# Authenticate with Keka (opens Chrome)
./keka-main/keka.py login
./keka-main/keka.py logout

# Authenticated passthrough to curl
./keka-main/keka.py curl https://think41.keka.com/api/v1/me

# Expense claims
./keka-main/keka.py expense --from-date 2026-02-01 --to-date 2026-03-30
./keka-main/keka.py expense create --title "Food & Travel (11/05/2026 to 17/05/2026)" --date 2026-05-17 --amount 2500 --comment "Per diem, 5 days"
./keka-main/keka.py expense update 6248217 --title "..." --date 2026-05-17 --amount 2500
./keka-main/keka.py expense submit 6248217 --title "Food & Travel (11/05/2026 to 17/05/2026)"
```

## Configuration

- Keka credentials are stored in the system keyring (falls back to `~/.keka/credentials.json`).
- Keka tenant domain is hardcoded to `think41.keka.com` in `keka.py`.

## Reference

- [Keka API Documentation](keka-main/docs/KEKA_API_DOCUMENTATION.md) - endpoints used, request/response shapes
- `keka-main/docs/keka_openapi.yaml` and `keka-main/api_docs/*.yaml` - raw OpenAPI specs for Keka's API surface
