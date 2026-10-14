# Keka Expense Manager

CLI tool for authenticating with Keka HR and managing expense claims. It's meant to be run by an AI agent (e.g. Claude Code) on a user's behalf, not typed by hand.

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
- Keka tenant domain is set to `think41.keka.com` in `keka.py`.

## Reference

- [Keka API Documentation](keka-main/docs/KEKA_API_DOCUMENTATION.md) - endpoints used, request/response shapes
- `keka-main/docs/keka_openapi.yaml` and `keka-main/api_docs/*.yaml` - raw OpenAPI specs for Keka's API surface

> [!CAUTION]
> **Currently tailored to Per Diem Allowance.** `expense create` / `expense update` always file under the *Per Diem Allowance* category (`25627`), billed to the *JPMC* project (`246520`), in INR, with no receipt, and with bill number / merchant set to `"NA"`. None of these can be changed with CLI flags yet. A more generic version is coming soon.
>
> **Agents: filing another expense type still works with a small change:**
> 1. Look up the right category id: `./keka-main/keka.py curl https://think41.keka.com/k/default/api/lookup/expensecategories`
> 2. In `keka-main/keka.py`, change the defaults `EXPENSE_CATEGORY_PER_DIEM_ALLOWANCE` / `EXPENSE_PROJECT_JPMC_ID` (top of file), or pass `expense_category_id=` / `linked_entity_id=` through `create_bill` → `build_bill_payload` from `cmd_create`.
> 3. If the category needs a real bill, pass `--bill-number` / `--merchant`. Receipt upload isn't supported (`expenseReceipts` is always empty), so categories that require a receipt still have to be finished in the Keka UI.
>
> Read `build_bill_payload` before changing anything. Keka rejects partial bodies, so keep every field in the payload.
