#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "playwright",
#     "keyring",
#     "httpx",
# ]
# ///
import asyncio
import base64
import json
import keyring
import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
import httpx

# Configure logging (set to WARNING for normal use, DEBUG for troubleshooting)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

USAGE = """Usage: keka <command> [options]

Commands:
  login       Authenticate with Keka and store credentials
  logout      Remove stored credentials
  curl        Make authenticated curl requests to Keka API
  expense     Get expense claim history
  expense create   Save a new draft expense (Per Diem Allowance / JPMC by default)
  expense update   Edit an existing unclaimed draft expense
  expense submit   Bundle draft expense(s) into a submitted claim

Examples:
  keka login
  keka curl https://think41.keka.com/api/v1/me
  keka expense [--from-date 2026-02-01] [--to-date 2026-03-30]
  keka expense create --title "Food & Travel (11/05/2026 to 17/05/2026)" --date 2026-05-17 --amount 2500 --comment "Per diem, 5 days"
  keka expense update 6248217 --title "..." --date 2026-05-17 --amount 2500
  keka expense submit 6248217 --title "Food & Travel (11/05/2026 to 17/05/2026)"
  keka logout
"""

# Keka domain configuration
KEKA_DOMAIN = "think41.keka.com"
LOGIN_DOMAIN = "app.keka.com"
WORK_EMAIL_DOMAIN = "@think41.com"
USER_DATA_DIR = Path.home() / ".keka"

# Keyring configuration
KEYRING_SERVICE = "keka"
KEYRING_TOKEN_KEY = "access_token"
KEYRING_EXPIRY_KEY = "expires_at"

# --- Expense claim defaults (discovered from the Keka "Add/Update Expenses" form) ---
#
# These identifiers are tenant-specific (think41.keka.com) and were captured by
# creating a real expense through the web UI and re-fetching it via GET
# /k/default/api/me/expenses/bill/{id}. If Keka ever renumbers categories or
# projects, re-derive these from that same form.
EXPENSE_CATEGORY_PER_DIEM_ALLOWANCE = 25627  # "Per Diem Allowance" - approved client visits only
EXPENSE_PROJECT_JPMC_ID = 246520              # "JPMC" project, used as the Project/Cost Center
EXPENSE_LINKED_ENTITY_TYPE_PROJECT = 1        # linkedEntityType value meaning "Project"
EXPENSE_DEFAULT_BILL_NUMBER = "NA"            # used when no physical bill/receipt exists (e.g. per diem)
EXPENSE_DEFAULT_MERCHANT_NAME = "NA"          # ditto
EXPENSE_CURRENCY_INR = {
    "id": 0, "code": "INR", "name": None, "symbol": None,
    "sortOrder": 0, "precision": None, "currencyName": None, "subUnit": None,
}


class Authentication:
    """Everything about proving who you are to Keka: browser login, token
    storage (keyring, falling back to a file), and authenticated curl."""

    def __init__(self):
        self._cached_token = None

    @staticmethod
    def _decode_jwt_email(token):
        """Extract the 'email' claim from a JWT access token, if present."""
        try:
            payload = token.split('.')[1]
            payload += '=' * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload)).get('email')
        except Exception:
            return None

    @staticmethod
    def _chrome_user_data_dir():
        """Locate the local Chrome 'User Data' directory for this OS, if any."""
        home = Path.home()
        for candidate in (
            Path(os.environ.get("LOCALAPPDATA", home)) / "Google" / "Chrome" / "User Data",  # Windows
            home / "Library" / "Application Support" / "Google" / "Chrome",                   # macOS
            home / ".config" / "google-chrome",                                               # Linux
        ):
            if candidate.exists():
                return candidate
        return None

    def list_chrome_profiles(self):
        """List local Chrome profiles as [{'dir_name', 'display_name', 'email'}, ...]."""
        user_data_dir = self._chrome_user_data_dir()
        if not user_data_dir:
            return []

        profiles = []
        for entry in sorted(user_data_dir.iterdir()):
            if not entry.is_dir() or (entry.name != "Default" and not entry.name.startswith("Profile ")):
                continue
            prefs_file = entry / "Preferences"
            if not prefs_file.exists():
                continue
            try:
                prefs = json.loads(prefs_file.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            account_info = prefs.get("account_info") or []
            email = account_info[0].get("email") if account_info else None
            display_name = prefs.get("profile", {}).get("name", entry.name)
            profiles.append({"dir_name": entry.name, "display_name": display_name, "email": email})
        return profiles

    def choose_work_chrome_profile(self):
        """Pick the Chrome profile signed into a WORK_EMAIL_DOMAIN account.

        Auto-picks when there's exactly one match, prompts interactively when
        there are several, and exits with guidance when there are none - this
        tool only works from a Chrome profile already signed into a work
        account.
        """
        work_profiles = [
            p for p in self.list_chrome_profiles()
            if p["email"] and p["email"].lower().endswith(WORK_EMAIL_DOMAIN)
        ]

        if not work_profiles:
            print(f"No Chrome profile on this machine is signed into a {WORK_EMAIL_DOMAIN} account.",
                  file=sys.stderr)
            print(f"Sign into Chrome with your {WORK_EMAIL_DOMAIN} work Google account "
                  f"(Chrome menu > profile icon > \"Add\"/\"Sign in\"), then run 'keka login' again.",
                  file=sys.stderr)
            sys.exit(1)

        if len(work_profiles) == 1:
            return work_profiles[0]

        print(f"Multiple Chrome profiles are signed into a {WORK_EMAIL_DOMAIN} account:")
        for i, p in enumerate(work_profiles, 1):
            print(f"  {i}. {p['display_name']} ({p['email']})")
        while True:
            choice = input(f"Choose the profile to use for Keka [1-{len(work_profiles)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(work_profiles):
                return work_profiles[int(choice) - 1]
            print("Invalid choice, try again.")

    @staticmethod
    def validate_keka_url(url):
        """Validate that URL matches Keka pattern"""
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            return parsed.netloc == KEKA_DOMAIN
        except:
            return False

    @staticmethod
    def _get_credentials_file():
        """Get path to credentials file"""
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return USER_DATA_DIR / "credentials.json"

    def load_credentials(self):
        """Load credentials from keyring or fallback to file storage"""
        try:
            access_token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
            expires_at_str = keyring.get_password(KEYRING_SERVICE, KEYRING_EXPIRY_KEY)

            if access_token and expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(timezone.utc) < expires_at:
                    return {"access_token": access_token, "expires_at": expires_at_str}
        except Exception:
            pass

        try:
            cred_file = self._get_credentials_file()
            if cred_file.exists():
                with open(cred_file, 'r') as f:
                    creds = json.load(f)
                    expires_at = datetime.fromisoformat(creds.get('expires_at', ''))
                    if datetime.now(timezone.utc) < expires_at:
                        return creds
        except Exception:
            pass

        return None

    def save_credentials(self, access_token, expires_at):
        """Save credentials to keyring or fallback to file storage"""
        expires_at_iso = expires_at.isoformat()

        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, access_token)
            keyring.set_password(KEYRING_SERVICE, KEYRING_EXPIRY_KEY, expires_at_iso)
            return
        except Exception as e:
            logger.debug(f"Keyring failed: {e}, using file storage instead")

        try:
            cred_file = self._get_credentials_file()
            cred_file.parent.mkdir(parents=True, exist_ok=True)

            creds = {"access_token": access_token, "expires_at": expires_at_iso}

            with open(cred_file, 'w') as f:
                json.dump(creds, f)

            if hasattr(cred_file, 'chmod'):
                cred_file.chmod(0o600)  # Read/write for owner only

            logger.info(f"Credentials saved to {cred_file}")
        except Exception as e:
            logger.exception(f"Failed to save credentials: {e}")
            raise

    def clear_credentials(self):
        """Remove stored credentials from keyring and file storage"""
        cleared = False

        try:
            if keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY):
                keyring.delete_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
                cleared = True
        except (keyring.errors.PasswordDeleteError, Exception):
            pass
        try:
            if keyring.get_password(KEYRING_SERVICE, KEYRING_EXPIRY_KEY):
                keyring.delete_password(KEYRING_SERVICE, KEYRING_EXPIRY_KEY)
                cleared = True
        except (keyring.errors.PasswordDeleteError, Exception):
            pass

        try:
            cred_file = self._get_credentials_file()
            if cred_file.exists():
                cred_file.unlink()
                cleared = True
        except Exception as e:
            logger.debug(f"Failed to delete credentials file: {e}")

        return cleared

    async def authenticate(self):
        """Authenticate against Keka via browser OAuth and return (access_token, expires_at)"""
        keka_url = f"https://{KEKA_DOMAIN}"
        logger.info(f"Starting authentication, navigating to {keka_url}")

        profile = self.choose_work_chrome_profile()
        user_data_dir = self._chrome_user_data_dir()
        print(f"Using Chrome profile \"{profile['display_name']}\" ({profile['email']}). "
              f"If it isn't already signed into Keka, sign in when the browser opens.")

        async with async_playwright() as p:
            context = None
            try:
                logger.debug(f"Launching Chrome profile {profile['dir_name']} at {user_data_dir}")
                try:
                    context = await p.chromium.launch_persistent_context(
                        str(user_data_dir),
                        headless=False,
                        channel="chrome",
                        args=[f"--profile-directory={profile['dir_name']}"],
                    )
                except Exception as e:
                    logger.exception(f"Failed to launch Chrome profile {profile['dir_name']}: {e}")
                    print(f"Could not launch Chrome with profile \"{profile['display_name']}\" - "
                          f"it's likely already open. Close all Chrome windows and try again.",
                          file=sys.stderr)
                    sys.exit(7)
                logger.debug("Browser launched successfully")

                page = await context.new_page()

                logger.info(f"Navigating to {keka_url}")
                await page.goto(keka_url, timeout=60000)
                # Use 'load' instead of 'networkidle' - SPAs often never reach network idle due to websockets/polling
                await page.wait_for_load_state("load")
                logger.debug(f"Page loaded, current URL: {page.url}")

                loop_count = 0
                while True:
                    loop_count += 1
                    await page.wait_for_timeout(2000)
                    current_url = page.url
                    logger.debug(f"Loop iteration {loop_count}, current URL: {current_url}")

                    if LOGIN_DOMAIN in current_url:
                        logger.info("Still on login page, waiting for user to authenticate...")
                        continue
                    elif KEKA_DOMAIN in current_url:
                        logger.debug("On Keka domain, checking for access token in localStorage")
                        try:
                            all_keys = await page.evaluate("() => Object.keys(localStorage)")
                            logger.debug(f"localStorage keys: {all_keys}")

                            token = await page.evaluate("() => localStorage.getItem('access_token')")
                            logger.debug(f"access_token value: {token[:50] if token else 'None'}...")
                            if token:
                                logger.info("Access token found, authentication complete!")
                                break
                            else:
                                logger.debug("No access_token found, continuing to wait...")
                        except Exception as e:
                            logger.warning(f"Error accessing localStorage: {e}")
                            continue
                    else:
                        logger.debug(f"On unexpected domain: {current_url}")

                logger.debug("Extracting access token from localStorage")
                access_token = await page.evaluate("() => localStorage.getItem('access_token')")

                if not access_token:
                    logger.error("Failed to extract access token after authentication")
                    print("curl: (7) Failed to connect to authentication server", file=sys.stderr)
                    sys.exit(7)

                email = self._decode_jwt_email(access_token)
                if not email or not email.lower().endswith(WORK_EMAIL_DOMAIN):
                    logger.error(f"Logged in as {email!r}, not a {WORK_EMAIL_DOMAIN} account")
                    print(f"Logged in as {email or 'an unknown account'}, which isn't your "
                          f"{WORK_EMAIL_DOMAIN} work account. Log out of that account in the "
                          f"browser and try again.", file=sys.stderr)
                    await context.close()
                    sys.exit(7)

                expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
                logger.info(f"Token expires at {expires_at}")

                logger.debug("Closing browser context...")
                await context.close()
                logger.debug("Browser context closed")

                return access_token, expires_at

            except Exception as e:
                logger.exception(f"Authentication failed with exception: {e}")
                if context:
                    logger.debug("Attempting to close browser context after error...")
                    try:
                        await context.close()
                        logger.debug("Browser context closed after error")
                    except Exception as close_error:
                        logger.error(f"Failed to close context: {close_error}")
                print(f"curl: (7) Failed to connect to authentication server", file=sys.stderr)
                sys.exit(7)

    async def get_credentials(self):
        """Get a valid access token, authenticating (via browser) if needed"""
        creds = self.load_credentials()
        if creds:
            return creds["access_token"]

        access_token, expires_at = await self.authenticate()
        self.save_credentials(access_token, expires_at)

        return access_token

    @staticmethod
    def build_curl_command(curl_args, access_token):
        """Build curl command with Bearer authorization header"""
        curl_cmd = ["curl", "-H", f"Authorization: Bearer {access_token}"]
        curl_cmd.extend(curl_args)
        return curl_cmd

    async def cmd_login(self):
        """Handle 'keka login' command"""
        creds = self.load_credentials()
        if creds:
            expires_at = datetime.fromisoformat(creds.get('expires_at', ''))
            print(f"Already logged in. Token expires at {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print("Run 'keka logout' first to re-authenticate.")
            return

        try:
            access_token, expires_at = await self.authenticate()
            self.save_credentials(access_token, expires_at)
            print(f"Login successful. Token expires at {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception as e:
            logger.exception(f"Login failed: {e}")
            print("Login failed. Please try again.", file=sys.stderr)
            sys.exit(1)

    def cmd_logout(self):
        """Handle 'keka logout' command"""
        if self.clear_credentials():
            print("Logged out successfully.")
        else:
            print("No credentials found.")

class Expense:
    """Everything about expense claims: listing, and creating/editing/
    submitting draft expenses ("bills") via the Keka API."""

    def __init__(self, auth: Authentication):
        self.auth = auth

    # --- formatting/parsing helpers ---

    @staticmethod
    def parse_list_args(args):
        """Parse command line arguments for 'keka expense'"""
        from_date = None
        to_date = None

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '--from-date' and i + 1 < len(args):
                from_date = args[i + 1]
                i += 2
            elif arg == '--to-date' and i + 1 < len(args):
                to_date = args[i + 1]
                i += 2
            else:
                i += 1

        # Default to last 6 months if not specified
        if not to_date:
            to_date = datetime.now().strftime('%Y-%m-%d')
        if not from_date:
            from_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

        return from_date, to_date

    @staticmethod
    def format_approval_status(status_code):
        """Convert status code to human-readable status"""
        status_map = {
            0: "Unknown", 1: "Submitted", 2: "Rejected", 3: "Recalled",
            4: "Pending", 5: "Approved", 6: "Paid",
        }
        return status_map.get(status_code, "Unknown")

    @staticmethod
    def format_date(iso_datetime):
        """Format ISO datetime to human-readable format"""
        try:
            dt = datetime.fromisoformat(iso_datetime.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p')
        except:
            return iso_datetime

    @staticmethod
    def build_bill_payload(
        title: str,
        billing_date: str,
        amount: float,
        comment: str,
        bill_id: int = 0,
        bill_number: str = EXPENSE_DEFAULT_BILL_NUMBER,
        merchant_name: str = EXPENSE_DEFAULT_MERCHANT_NAME,
        expense_category_id: int = EXPENSE_CATEGORY_PER_DIEM_ALLOWANCE,
        linked_entity_id: int = EXPENSE_PROJECT_JPMC_ID,
        linked_entity_type: int = EXPENSE_LINKED_ENTITY_TYPE_PROJECT,
    ) -> dict:
        """Build the JSON body for the Keka "expense bill" create/update endpoint.

        This mirrors the full view-model Keka's own web UI submits from the
        "Add/Update Expenses" form (POST to create, PUT .../bill/{id} to update) -
        the API rejects partial bodies with a generic "Invalid request model"
        error, so every field below is required even though most never change.

        Args:
            title: Free-text expense title shown in the claims list, e.g.
                "Food & Travel (11/05/2026 to 17/05/2026)". Keka has no dedicated
                "Food & Travel" category - this text is just the title, filed
                under the expense_category_id category.
            billing_date: ISO date string "YYYY-MM-DD" the expense is billed to.
            amount: Amount in the currency's major unit (e.g. 2500 for INR 2,500).
            comment: Free-text comment/justification stored on the expense.
            bill_id: 0 to create a new expense; the existing bill's id to update
                one in place (only meaningful when passed to update_bill).
            bill_number: Reference/receipt number. Required by the API even when
                there's no physical bill (e.g. a per-diem allowance) - defaults
                to "NA" to match that case.
            merchant_name: Vendor/merchant name. Same "required but often
                inapplicable" situation as bill_number - defaults to "NA".
            expense_category_id: Keka expense category id. Defaults to "Per Diem
                Allowance" (25627), which per Keka's own category description is
                "applicable only for approved client visits".
            linked_entity_id: id of the Project/Cost Center to bill against.
                Defaults to the JPMC project (246520).
            linked_entity_type: Keka's type code for linked_entity_id. Defaults
                to 1 ("Project"); other values (e.g. cost centers) aren't covered
                here since this tenant only ever bills expenses to a Project.

        Returns:
            A dict ready to json-serialize as the request body.
        """
        return {
            "id": bill_id,
            "title": title,
            "billingDate": billing_date,
            "billingNumber": bill_number,
            "merchantName": merchant_name,
            "amount": amount,
            "foreignCurrencyAmount": amount,
            "currency": EXPENSE_CURRENCY_INR,
            "expenseCategoryId": expense_category_id,
            "comment": comment,
            "expenseReceipts": [],
            "hasReceipt": False,
            "hasComment": bool(comment),
            "tripStart": None,
            "tripEnd": None,
            "totalDistance": None,
            "isAdvanceRequest": False,
            "accommodationPlace": None,
            "travelFrom": None,
            "travelTo": None,
            "fromDate": None,
            "toDate": None,
            "isSelfBooking": False,
            "bookingStatus": 0,
            "bookingReceipts": [],
            "bookingComment": None,
            "bookingApproverId": None,
            "bookingConfirmedOn": None,
            "linkedEntityId": linked_entity_id,
            "linkedEntityType": linked_entity_type,
            "actualDistance": None,
            "attributes": {"useDistanceCalculationService": "false"},
            "expenseClaimId": None,
            "status": 1,
        }

    @staticmethod
    def parse_create_args(args):
        """Parse CLI args for 'keka expense create' / 'keka expense update'.

        Recognized flags:
            --title "..."       required. Expense title, e.g.
                                 "Food & Travel (11/05/2026 to 17/05/2026)".
            --date YYYY-MM-DD    required. Billing date.
            --amount 2500         required. Amount in INR (major unit).
            --comment "..."      optional. Defaults to "".
            --bill-number ...    optional. Defaults to EXPENSE_DEFAULT_BILL_NUMBER ("NA").
            --merchant ...       optional. Defaults to EXPENSE_DEFAULT_MERCHANT_NAME ("NA").

        Returns:
            dict of parsed values (title, billing_date, amount, comment,
            bill_number, merchant_name), with amount converted to float.
            Missing required fields are left as None for the caller to validate.
        """
        parsed = {
            "title": None,
            "billing_date": None,
            "amount": None,
            "comment": "",
            "bill_number": EXPENSE_DEFAULT_BILL_NUMBER,
            "merchant_name": EXPENSE_DEFAULT_MERCHANT_NAME,
        }

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '--title' and i + 1 < len(args):
                parsed["title"] = args[i + 1]
                i += 2
            elif arg == '--date' and i + 1 < len(args):
                parsed["billing_date"] = args[i + 1]
                i += 2
            elif arg == '--amount' and i + 1 < len(args):
                parsed["amount"] = float(args[i + 1])
                i += 2
            elif arg == '--comment' and i + 1 < len(args):
                parsed["comment"] = args[i + 1]
                i += 2
            elif arg == '--bill-number' and i + 1 < len(args):
                parsed["bill_number"] = args[i + 1]
                i += 2
            elif arg == '--merchant' and i + 1 < len(args):
                parsed["merchant_name"] = args[i + 1]
                i += 2
            else:
                i += 1

        return parsed

    # --- API calls ---

    async def get_bill(self, access_token: str, bill_id: int) -> dict:
        """Fetch a single expense/bill entry by id.

        Returns:
            The expense's data dict (title, billingDate, amount, expenseClaimId
            - null while still a draft, set once bundled into a submitted claim -
            etc.), i.e. response_json["data"].

        Raises:
            httpx.HTTPStatusError: if the request fails (e.g. bad id, expired token).
        """
        url = f"https://{KEKA_DOMAIN}/k/default/api/me/expenses/bill/{bill_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30.0
            )
            response.raise_for_status()
            return response.json()["data"]

    async def create_bill(self, access_token: str, **payload_kwargs) -> int:
        """Create a new draft expense entry (not yet part of a submitted claim).

        This only saves the expense to "Expenses to be Claimed" - it does NOT
        submit a claim. Call submit_claim() afterward (with this expense's id)
        to bundle it into a submitted claim, matching the web UI's "Submit
        Claim" button.

        Returns:
            The new expense's id (int), for use with update_bill or to locate
            it in the Keka UI to submit the claim.

        Raises:
            httpx.HTTPStatusError: if the request fails.
        """
        payload = self.build_bill_payload(**payload_kwargs)
        url = f"https://{KEKA_DOMAIN}/k/default/api/me/expenses/bill"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["data"]["id"]

    async def update_bill(self, access_token: str, bill_id: int, **payload_kwargs) -> None:
        """Update an existing draft expense entry in place.

        Only works while the expense is still unclaimed (expenseClaimId is null,
        i.e. it hasn't been submitted as part of a claim yet).

        Raises:
            httpx.HTTPStatusError: if the request fails.
        """
        payload = self.build_bill_payload(bill_id=bill_id, **payload_kwargs)
        url = f"https://{KEKA_DOMAIN}/k/default/api/me/expenses/bill/{bill_id}"
        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()

    async def submit_claim(
        self, access_token: str, expense_ids: list, title: str, description: str = ""
    ) -> dict:
        """Bundle one or more unclaimed draft expenses into a submitted claim.

        This is the direct equivalent of clicking "Submit Claim" in the Keka web
        UI's Add/Update Expenses dialog - it both creates the claim record and
        submits it for approval in one call (there's no separate "save as draft
        claim" step).

        Returns:
            The created claim's data dict, notably "claimNumber" (e.g.
            "#EXP879"), "totalAmount", and "approvalStatus" (1 = Submitted).

        Raises:
            httpx.HTTPStatusError: if the request fails (e.g. an expense id is
                already claimed, or doesn't belong to this employee).
        """
        url = f"https://{KEKA_DOMAIN}/k/default/api/me/expenses/claim"
        payload = {"expenseIds": expense_ids, "title": title, "description": description}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["data"]

    # --- CLI command handlers ---

    async def cmd_create(self, args):
        """Handle 'keka expense create' - save a new draft expense (Per Diem
        Allowance / JPMC by default).

        Does not submit a claim - see create_bill's docstring. Prints the new
        expense id, which you'll need to find it in Keka's "Pending Expenses"
        tab to click "Submit Claim".
        """
        parsed = self.parse_create_args(args)
        missing = [k for k in ("title", "billing_date", "amount") if not parsed[k] and parsed[k] != 0]
        if missing:
            print("Usage: keka expense create --title \"...\" --date YYYY-MM-DD --amount 2500 "
                  "[--comment \"...\"] [--bill-number NA] [--merchant NA]", file=sys.stderr)
            print(f"Missing required argument(s): {', '.join(missing)}", file=sys.stderr)
            sys.exit(2)

        try:
            access_token = await self.auth.get_credentials()
        except Exception as e:
            print(f"Failed to get credentials: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            bill_id = await self.create_bill(
                access_token,
                title=parsed["title"],
                billing_date=parsed["billing_date"],
                amount=parsed["amount"],
                comment=parsed["comment"],
                bill_number=parsed["bill_number"],
                merchant_name=parsed["merchant_name"],
            )
        except httpx.HTTPStatusError as e:
            print(f"API error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            sys.exit(1)

        print(f"Created draft expense #{bill_id}: {parsed['title']} (INR {parsed['amount']:.2f})")
        print("Not yet claimed - open Keka > Me > Expenses & Travel > Pending Expenses "
              "and click \"Submit Claim\" to finalize.")

    async def cmd_update(self, args):
        """Handle 'keka expense update <billId>' - edit an existing draft
        expense in place (must still be unclaimed).
        """
        if not args or args[0].startswith('--'):
            print("Usage: keka expense update <billId> --title \"...\" --date YYYY-MM-DD "
                  "--amount 2500 [--comment \"...\"] [--bill-number NA] [--merchant NA]", file=sys.stderr)
            sys.exit(2)

        try:
            bill_id = int(args[0])
        except ValueError:
            print(f"Invalid expense id: {args[0]}", file=sys.stderr)
            sys.exit(2)

        parsed = self.parse_create_args(args[1:])
        missing = [k for k in ("title", "billing_date", "amount") if not parsed[k] and parsed[k] != 0]
        if missing:
            print(f"Missing required argument(s): {', '.join(missing)}", file=sys.stderr)
            sys.exit(2)

        try:
            access_token = await self.auth.get_credentials()
        except Exception as e:
            print(f"Failed to get credentials: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            await self.update_bill(
                access_token,
                bill_id,
                title=parsed["title"],
                billing_date=parsed["billing_date"],
                amount=parsed["amount"],
                comment=parsed["comment"],
                bill_number=parsed["bill_number"],
                merchant_name=parsed["merchant_name"],
            )
        except httpx.HTTPStatusError as e:
            print(f"API error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            sys.exit(1)

        print(f"Updated draft expense #{bill_id}: {parsed['title']} (INR {parsed['amount']:.2f})")

    async def cmd_submit(self, args):
        """Handle 'keka expense submit <billId> [<billId>...] --title "..."'.

        Bundles the given draft expense id(s) into a submitted claim - the
        script equivalent of clicking "Submit Claim" in the Keka web UI. This
        finalizes the claim: it goes to your approver and can no longer be
        edited like a draft.

        Usage:
            keka expense submit 6248228 --title "Food & Travel (18/05/2026 to 24/05/2026)" [--description "..."]
            keka expense submit 6248228 6248229 --title "..."   # bundle multiple expenses into one claim
        """
        expense_ids = []
        title = None
        description = ""

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '--title' and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif arg == '--description' and i + 1 < len(args):
                description = args[i + 1]
                i += 2
            elif not arg.startswith('--'):
                try:
                    expense_ids.append(int(arg))
                except ValueError:
                    print(f"Invalid expense id: {arg}", file=sys.stderr)
                    sys.exit(2)
                i += 1
            else:
                i += 1

        if not expense_ids or not title:
            print("Usage: keka expense submit <billId> [<billId>...] --title \"...\" [--description \"...\"]",
                  file=sys.stderr)
            sys.exit(2)

        try:
            access_token = await self.auth.get_credentials()
        except Exception as e:
            print(f"Failed to get credentials: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            claim = await self.submit_claim(access_token, expense_ids, title, description)
        except httpx.HTTPStatusError as e:
            print(f"API error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            sys.exit(1)

        print(f"Submitted claim {claim['claimNumber']}: {claim['title']} "
              f"(INR {claim['totalAmount']:.2f})")

    async def cmd_list(self, args):
        """Handle 'keka expense' command - fetch and display expense claims"""
        from_date, to_date = self.parse_list_args(args)

        try:
            access_token = await self.auth.get_credentials()
        except Exception as e:
            print(f"Failed to get credentials: {e}", file=sys.stderr)
            sys.exit(1)

        url = f"https://{KEKA_DOMAIN}/k/default/api/me/expenses/claims/past?paidFromDate={from_date}&paidToDate={to_date}&isSettlementClaims=false&searchKey="

        print(f"Fetching expense claims from {from_date} to {to_date}...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0
                )
                response.raise_for_status()
                response_data = response.json()
                data = response_data.get('data', response_data) if isinstance(response_data, dict) else response_data
        except httpx.HTTPStatusError as e:
            print(f"API error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Failed to fetch expense claims: {e}", file=sys.stderr)
            sys.exit(1)

        if not data:
            print(f"No expense claims found between {from_date} and {to_date}")
            return

        # Sort by submission date, most recent first
        claims = sorted(data, key=lambda x: x.get('submittedOn', ''), reverse=True)

        if claims:
            latest = claims[0]

            print("\n" + "=" * 70)
            print("YOUR LAST EXPENSE CLAIM")
            print("=" * 70)
            print(f"Claim Number:     {latest.get('claimNumber', 'N/A')}")
            print(f"Title:            {latest.get('title', 'N/A')}")
            print(f"Amount:           {latest.get('totalAmount', 'N/A')} {latest.get('baseCurrency', {}).get('code', 'INR')}")
            print(f"Submitted Date:   {self.format_date(latest.get('submittedOn', 'N/A'))}")
            print(f"Pay Date:         {latest.get('payDate', 'N/A')}")
            print(f"Status:           {self.format_approval_status(latest.get('approvalStatus', 0))}")
            print(f"Approver:         {latest.get('approverName', 'N/A')}")
            print("=" * 70)

            if len(claims) > 1:
                print(f"\nRecent expense claims ({len(claims)} total):")
                print("-" * 70)
                for i, claim in enumerate(claims[:10], 1):
                    status = self.format_approval_status(claim.get('approvalStatus', 0))
                    submitted = self.format_date(claim.get('submittedOn', 'N/A'))
                    print(f"{i:2}. {claim.get('claimNumber'):10} | {claim.get('title'):20} | {claim.get('totalAmount'):>8} {claim.get('baseCurrency', {}).get('code', 'INR')} | {status:10} | {submitted}")


async def cmd_curl(auth: Authentication, curl_args):
    """Handle 'keka curl' command - run an authenticated curl against any
    Keka API endpoint.

    Used with the explicit request by the user, request user's permission
    before using this functionality. This is a convenience for advanced users


    This is the escape hatch for experimenting with Keka's API surface: poke
    at an endpoint to see its shape before wiring up a proper method for it,
    or just run one-off requests that don't warrant new functionality at all.
    """
    if not curl_args:
        print("Usage: keka curl [curl options] <url>", file=sys.stderr)
        print("Example: keka curl https://think41.keka.com/api/v1/me", file=sys.stderr)
        sys.exit(2)

    url = None
    for arg in curl_args:
        if arg.startswith(('http://', 'https://')):
            url = arg
            break

    if not url:
        subprocess.run(["curl"] + curl_args)
        return

    if not auth.validate_keka_url(url):
        result = subprocess.run(["curl"] + curl_args)
        sys.exit(result.returncode)

    if not shutil.which("curl"):
        print("curl: command not found", file=sys.stderr)
        sys.exit(127)

    try:
        access_token = await auth.get_credentials()
        curl_cmd = auth.build_curl_command(curl_args, access_token)
        result = subprocess.run(curl_cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"curl: (7) Failed to connect to authentication server", file=sys.stderr)
        sys.exit(7)



async def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(2)

    command = sys.argv[1]
    auth = Authentication()

    if command == "login":
        await auth.cmd_login()
    elif command == "logout":
        auth.cmd_logout()
    elif command == "curl":
        await cmd_curl(auth, sys.argv[2:])
    elif command == "expense":
        expense = Expense(auth)
        sub_args = sys.argv[2:]
        if sub_args and sub_args[0] == "create":
            await expense.cmd_create(sub_args[1:])
        elif sub_args and sub_args[0] == "update":
            await expense.cmd_update(sub_args[1:])
        elif sub_args and sub_args[0] == "submit":
            await expense.cmd_submit(sub_args[1:])
        else:
            await expense.cmd_list(sub_args)
    elif command in ("-h", "--help", "help"):
        print(USAGE)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main())
