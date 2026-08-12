# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Repository Overview

This repository contains tools for managing Keka HR data (expenses):
- **keka-main/keka.py** - CLI tool for Keka API authentication and expense operations

## Skills

### /expense - Expense Claims Skill

This skill handles expense-related queries like "when was my last expense claimed", "show my expense history", "expense claim details", etc.

**Trigger phrases:**
- "when was my last expense claimed"
- "show my expense claims"
- "expense history"
- "my last expense"
- "expense claim details for [date/period]"

**Workflow:**
When the user requests expense information:

1. **Determine the date range:**
   - For "last expense" → search past 365 days
   - For "expense claims in [period]" → extract specific date range
   - Default range: last 6 months if not specified

2. **Query the Keka Expense API:**
   ```
   GET https://think41.keka.com/k/default/api/me/expenses/claims/past
   Parameters:
     - paidFromDate: YYYY-MM-DD (start date)
     - paidToDate: YYYY-MM-DD (end date)
     - isSettlementClaims: false
     - searchKey: "" (optional search term)
   ```

3. **Parse the response** and extract key information:
   - claimNumber: The expense claim reference number
   - title: Description/title of the expense
   - totalAmount: Claimed amount
   - baseCurrency: Currency code (usually INR)
   - submittedOn: ISO datetime when claim was submitted
   - payDate: Expected/actual payment date
   - approvalStatus: Status code (1=Submitted, 2=Rejected, 5=Approved)
   - approverName: Person who approved the claim

4. **Report the result** including:
   - Claim number and title
   - Amount and currency
   - Submission date
   - Current status
   - Approver information

**Status codes:**
- 0: Unknown
- 1: Submitted
- 2: Rejected
- 3: Recalled
- 4: Pending
- 5: Approved
- 6: Paid

**Example usage:**
```
User: "when was my last expense claimed"
Assistant: Your last expense claim was on February 10, 2026 at 6:39 PM
- Claim Number: #EXP639
- Title: Claude Code
- Amount: 2,000 INR
- Status: Approved
- Approver: Varsha Madhav
- Pay Date: February 26, 2026
```

**API Response Structure:**
```json
{
  "data": [
    {
      "id": 849905,
      "claimNumber": "#EXP00234",
      "title": "Food & Travel",
      "totalAmount": 2000.0,
      "claimedAmount": 2000.0,
      "baseCurrency": {
        "id": 1,
        "code": "INR",
        "name": " India Rupee"
      },
      "submittedOn": "2025-09-08T07:18:00Z",
      "payDate": "2025-10-31",
      "approvalStatus": 5,
      "approverName": "Varsha Madhav"
    }
  ],
  "succeeded": true,
  "message": "",
  "errors": []
}
```

## CLI Commands

### keka.py Commands

```bash
# Login to Keka (browser-based OAuth)
./keka-main/keka.py login

# Logout
./keka-main/keka.py logout

# Make authenticated API requests
./keka-main/keka.py curl https://think41.keka.com/api/v1/me
```

## Development Notes

- Keka credentials are stored in system keyring
- Keka domain: `think41.keka.com`
