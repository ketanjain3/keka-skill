# Keka HR API Documentation

This document provides an overview of the Keka HR REST APIs based on analysis of the application's network traffic.

## Overview

Keka is a comprehensive HR management platform. This documentation covers the GET APIs discovered from the application, organized by functional module.

**Base URL:** `https://{tenant}.keka.com`

**Authentication:** Bearer token (JWT) required for all endpoints.

---

## API Modules

| Module | Description | Endpoints |
|--------|-------------|-----------|
| [Attendance](#attendance) | Attendance tracking and management | 3 |
| [Bulk Operations](#bulk-operations) | Report builder and file exports | 7 |
| [Dashboard](#dashboard) | Dashboard widgets and employee data | 18 |
| [Core (Default)](#core-default) | Lookups, organization, exit, expense, inbox | 53 |
| [Engage](#engage) | Employee engagement and surveys | 3 |
| [Leave](#leave) | Leave management and approvals | 12 |
| [Payroll](#payroll) | Payroll configuration and lookups | 6 |
| [Platform](#platform) | Employee profile data | 1 |
| [Report Builder](#report-builder) | Report scheduling and widgets | 2 |
| [Timesheet](#timesheet) | Timesheet and project management | 25 |

---

## Common Response Format

Most Keka APIs return responses in this standard format:

```json
{
  "data": <response data>,
  "succeeded": true,
  "message": "",
  "errors": []
}
```

For the Engage module, a slightly different format is used:
```json
{
  "data": <response data>,
  "success": true
}
```

---

## Attendance

Attendance tracking, clock-in/out, and attendance metrics.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /k/attendance/api/employee/allpendingapprovalscount` | Get count of all pending attendance approvals |
| `GET /k/attendance/api/myteam/summary/{timePeriod}/attendancemetrics` | Get team attendance metrics by group |
| `GET /k/attendance/api/mytime/attendance/getcurrentdate` | Get current server date/time |

### Parameters

- `groupId` (integer): Group ID to filter by
- `systemGroupType` (integer): System group type filter

---

## Bulk Operations

Bulk data operations including report builder and file exports.

### Report Builder Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /k/bulk/api/report-builder/categories` | Get report categories |
| `GET /k/bulk/api/report-builder/favourites` | Get favorite reports |
| `GET /k/bulk/api/report-builder/recently-viewed` | Get recently viewed reports |
| `GET /k/bulk/api/report-builder/report-definitions` | Get report definitions by category |
| `GET /k/bulk/api/report-builder/report-definitions/filterbySlug` | Get report definition by slug |

### File Export Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /k/bulk/api/fileexport/exportrequest/` | Get file export request status |
| `GET /k/bulk/api/expense/claims/approved` | Get approved expense claims for bulk processing |

### Parameters

- `moduleName` (string): Module name filter (e.g., "payroll")
- `categoryId` (UUID): Report category ID
- `slug` (string): Report definition slug
- `fileExportIdentifier` (string): Export identifier (e.g., "currentctcreport", "exitcompleted")
- `isSettlementClaims` (boolean): Filter for settlement claims

---

## Dashboard

Dashboard widgets, wall posts, holidays, and employee summaries.

### Widget Configuration

| Endpoint | Description |
|----------|-------------|
| `GET /k/dashboard/api/dashboard/configurations` | Get dashboard widget configuration |
| `GET /k/dashboard/api/dashboard/wall/wallsettings` | Get wall settings (posts, polls, announcements) |

### Employee Data

| Endpoint | Description |
|----------|-------------|
| `GET /k/dashboard/api/dashboard/holidays` | Get upcoming holidays |
| `GET /k/dashboard/api/dashboard/onleavetoday` | Get employees on leave today |
| `GET /k/dashboard/api/dashboard/teamworkingremotely` | Get team members working remotely |
| `GET /k/dashboard/api/dashboard/wall/birthdays` | Get upcoming birthdays |
| `GET /k/dashboard/api/dashboard/wall/todayeventsstats` | Get today's events statistics |
| `GET /k/dashboard/api/wall/post` | Get wall posts |
| `GET /k/dashboard/api/employee/surveys/active` | Get active surveys |

### Attendance Data

| Endpoint | Description |
|----------|-------------|
| `GET /k/dashboard/api/mytime/attendance/attendancemodulestatus` | Get attendance module status |
| `GET /k/dashboard/api/mytime/attendance/attendancecapturescheme` | Get attendance capture scheme configuration |
| `GET /k/dashboard/api/mytime/attendance/attendancedayrequests` | Get attendance day requests (WFH, on-duty, etc.) |
| `GET /k/dashboard/api/mytime/attendance/shiftweekoffdetails` | Get shift and week-off details |

### Leave Data

| Endpoint | Description |
|----------|-------------|
| `GET /k/dashboard/api/me/leave/isleaveplanassigned` | Check if leave plan is assigned |
| `GET /k/dashboard/api/me/leave/summary` | Get leave balance summary |
| `GET /k/dashboard/api/me/weeklyoffpolicy` | Get weekly off policy |

### Inbox

| Endpoint | Description |
|----------|-------------|
| `GET /k/dashboard/api/inbox/pendingapprovalscount` | Get pending approvals count |
| `GET /k/dashboard/api/holiday/settings/leavetype/floatername` | Get floater leave type name |

### Parameters

- `currentDate` (date): Filter by date (YYYY-MM-DD)
- `forDate` (date): Date for leave summary
- `pageIndex` (integer): Page number (1-indexed)
- `pageSize` (integer): Items per page

---

## Core (Default)

Core APIs covering lookups, organization data, exit management, expenses, and inbox.

### Lookup APIs

Reference data for forms and filters.

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/lookup/departments` | Get all departments |
| `GET /k/default/api/lookup/businessunits` | Get all business units |
| `GET /k/default/api/lookup/locations` | Get all locations |
| `GET /k/default/api/lookup/legalentities` | Get all legal entities |
| `GET /k/default/api/lookup/costcenters` | Get all cost centers |
| `GET /k/default/api/lookup/countries` | Get all countries |
| `GET /k/default/api/lookup/currencies` | Get all currencies |
| `GET /k/default/api/lookup/basecurrencies` | Get base currencies |
| `GET /k/default/api/lookup/jobtitles` | Get all job titles |
| `GET /k/default/api/lookup/paygroups` | Get all pay groups |
| `GET /k/default/api/lookup/resignationreasons` | Get resignation reasons |
| `GET /k/default/api/lookup/terminationreasons` | Get termination reasons |
| `GET /k/default/api/lookup/expensecategories` | Get expense categories |
| `GET /k/default/api/lookup/explicitroles` | Get explicit roles |
| `GET /k/default/api/lookup/approvalchainrolesearchitems` | Get approval chain roles |
| `GET /k/default/api/lookup/availablegenders` | Get available genders |
| `GET /k/default/api/lookup/contingenttypes` | Get contingent worker types |
| `GET /k/default/api/lookup/globalfilterlist` | Get global filter options |

### Organization Dashboard

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/org/dashboard/employeescount` | Get employee counts by status |
| `GET /k/default/api/org/dashboard/comingbirthdays` | Get upcoming birthdays |
| `GET /k/default/api/org/dashboard/comingworkanniversaries` | Get upcoming work anniversaries |
| `GET /k/default/api/org/dashboard/onboardingemployeessummary` | Get onboarding employees summary |
| `GET /k/default/api/org/dashboard/preboardingsummary` | Get preboarding summary |
| `GET /k/default/api/org/dashboard/innoticesummary` | Get employees in notice period |
| `GET /k/default/api/org/dashboard/inprobationsummary` | Get employees in probation |
| `GET /k/default/api/org/dashboard/loginSummary` | Get login summary |
| `GET /k/default/api/org/dashboard/pendingactions` | Get pending actions count |

### Exit/Resignation Management

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/exit/summary` | Get exit summary counts |
| `GET /k/default/api/exit/settings` | Get exit settings configuration |
| `GET /k/default/api/exit/dashboard/retention/metric` | Get retention metrics |
| `GET /k/default/api/exittasks/summary/dashboard` | Get exit tasks summary |

### Expense Management

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/me/expenses/claims/pending` | Get pending expense claims |
| `GET /k/default/api/me/expenses/claims/past` | Get past expense claims (verified in production use, see [keka.py](../keka.py)) |
| `GET /k/default/api/me/expenses/claims/advance/pending` | Get pending advance requests |
| `GET /k/default/api/me/expenses/claims/pendingapprovalscount` | Get expense approvals count |
| `GET /k/default/api//organization/expensesettings` | Get organization expense settings (double slash is intentional - present in captured traffic and in `keka_openapi.yaml`, not a typo) |

### Inbox/Approvals

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/inbox/pendingapprovalscount` | Get all pending approvals count |
| `GET /k/default/api/inboxarchive/requestscount` | Get archived requests count |
| `GET /k/default/api/inbox/asset/acknowledgement` | Get asset acknowledgement requests |
| `GET /k/default/api/inbox/asset/acknowledgement/{requestId}` | Get specific asset acknowledgement |
| `GET /k/default/api/comment/comments` | Get comments for an item |

### Employee Profile

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/employee/{employeeId}/quickie/job/details` | Get employee job details |
| `GET /k/default/api/profile/changes/pending/count` | Get pending profile change count |
| `GET /k/default/api/myteam/profile/changes/pending/count` | Get team pending profile changes count |
| `GET /k/default/api/compositeviews/{viewType}/employeepublicview/employeepublicview` | Get employee public view |

### Welcome Screen

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/welcomescreen/details` | Get welcome screen details |
| `GET /k/default/api/welcomescreen/logindate` | Get last login date |
| `GET /k/default/api/welcomescreen/onboardingresources` | Get onboarding resources |
| `GET /k/default/api/welcomescreen/quicklinks` | Get quick links |

### Storyboard/Analytics

| Endpoint | Description |
|----------|-------------|
| `GET /k/default/api/storyboard/attrition/user/hasaccess` | Check attrition storyboard access |
| `GET /k/default/api/storyboard/attrition/user/all` | Get all attrition storyboard users |
| `GET /k/default/api/storyboard/attrition/ask-ai/get-all-prompts` | Get AI prompts for analytics |
| `GET /k/default/api/org/storyboard/attrition/getratingscales` | Get rating scales |

### Parameters

- `includeArchivedGroups` (boolean): Include archived groups
- `applyVisibilityRestrictionOnFilters` (boolean): Apply visibility restrictions
- `startDate/endDate` (date): Date range filters
- `fromDate/toDate` (date): Date range filters
- `paidFromDate/paidToDate` (date): Payment date range
- `searchKey` (string): Search keyword
- `isSettlementClaims` (boolean): Filter settlement claims
- `commentIdentifier` (UUID): Comment identifier
- `persona` (integer): User persona type
- `widgetName` (string): Widget name for analytics
- `viewAllInsights` (boolean): View all insights flag

---

## Engage

Employee engagement, pulse surveys, and announcements.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /engage/api/v1/employees/me/pulse/responses` | Get pulse survey responses |
| `GET /engage/api/v1/employees/me/surveys/pending` | Get pending surveys |
| `GET /engage/api/v1/employees/me/announcements` | Get announcements |

### Parameters

- `pageNumber` (integer): Page number (1-indexed)
- `pageSize` (integer): Items per page
- `wallType` (integer): Announcement wall type

---

## Leave

Leave management, approvals, and leave plan configuration.

### Leave Plans

| Endpoint | Description |
|----------|-------------|
| `GET /k/leave/api/leaves/settings/leaveplan/all` | Get all leave plans |
| `GET /k/leave/api/leaves/settings/leaveplan/{planId}` | Get specific leave plan |
| `GET /k/leave/api/leaves/settings/leavetypenames` | Get leave type names |
| `GET /k/leave/api/lookup/leavetypes` | Get leave types lookup |
| `GET /k/leave/api/leaves/yearendprocess/active` | Get active year-end processes |

### Leave Approvals

| Endpoint | Description |
|----------|-------------|
| `GET /k/leave/api/leave/approval/pendingleaverequests` | Get pending leave requests |
| `GET /k/leave/api/leave/approval/pendingcompoffrequests` | Get pending comp-off requests |
| `GET /k/leave/api/leave/approval/encashmentrequest/pending` | Get pending encashment requests |
| `GET /k/leave/api/leave/approval/encashmentrequest/past` | Get past encashment requests |

### Team Leave

| Endpoint | Description |
|----------|-------------|
| `GET /k/leave/api/myteam/summary/{level}/teamonleave` | Get team members on leave |
| `GET /k/leave/api/myteam/summary/{level}/teamleavecalendar` | Get team leave calendar |
| `GET /k/leave/api/CeoDashboard/employeesonleave` | Get employees on leave (CEO view) |

### Parameters

- `fromDate/toDate` (date): Date range
- `groupId` (integer): Group filter
- `systemGroupType` (integer): System group type

---

## Payroll

Payroll configuration and lookups.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /k/payroll/api/payroll/lookups/configuredcurrencies` | Get configured currencies |
| `GET /k/payroll/api/payroll/lookups/isindianpayrollconfigured` | Check if Indian payroll is configured |
| `GET /k/payroll/api/payroll/lookups/isLWFEnabled` | Check if LWF is enabled |
| `GET /k/payroll/api/payroll/lookups/issocialinsuranceenabled` | Check if social insurance is enabled |
| `GET /k/payroll/api/payroll/lookups/paygroupview` | Get pay group view |
| `GET /k/payroll/api/payroll/lookups/salarycomponent/recurring` | Get recurring salary components |

---

## Platform

Core platform APIs for employee data.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /platform/api/v1/employees/{employeeId}` | Get employee details by ID |

### Response Structure

```json
{
  "data": {
    "employeeId": "uuid",
    "fullName": "string",
    "displayName": "string",
    "email": "string",
    "mobilePhone": "string",
    "employeeNumber": "string",
    "employmentStatus": 0,
    "dateJoined": "date",
    "dateOfBirth": "date",
    "gender": 1,
    "workerType": 1,
    "departmentId": "uuid",
    "groups": [...],
    "legalEntityDetails": {...},
    "reporteeCount": 0
  },
  "success": true
}
```

---

## Report Builder

Report scheduling and widget analytics.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /report-builder/api/v1/report-schedules/` | Get report schedules |
| `GET /report-builder/api/v1/widgets/reaction-aggregates` | Get widget reaction aggregates |

### Parameters

- `reportDefinitionId` (UUID): Report definition ID

---

## Timesheet

Timesheet management and project tracking.

### Dashboard

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/timesheet/dashboard/timesheetdetails` | Get timesheet dashboard details |
| `GET /k/timesheet/api/timesheet/pendingapprovalcount` | Get pending approval count |
| `GET /k/timesheet/api/timesheet/resourcesettings` | Get resource settings |

### CEO Dashboard

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/CeoDashboard/projectstats` | Get project statistics |
| `GET /k/timesheet/api/CeoDashboard/projectUnsubmittedTimesheet` | Get unsubmitted timesheets |

### Projects

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/ps/project/activeprojects` | Get active projects |
| `GET /k/timesheet/api/ps/project/allprojects` | Get all projects |
| `GET /k/timesheet/api/ps/project/archivedprojects` | Get archived projects |
| `GET /k/timesheet/api/project/activeprojectsprojectmanagers` | Get project managers for active projects |
| `GET /k/timesheet/api/project/clientlookups` | Get client lookups |
| `GET /k/timesheet/api/project/customattributes/{type}/projecttype/{projectType}` | Get custom attributes |

### Clients

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/client/all` | Get all clients |
| `GET /k/timesheet/api/lookup/clientmanagers` | Get client managers |

### Team Timesheet

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/myteamemployees/timesheet/weektimesummary` | Get weekly time summary |
| `GET /k/timesheet/api/myteamemployees/timesheet/projectviewlookup` | Get project view lookup |
| `GET /k/timesheet/api/myteamemployees/timesheet/employeeviewlookup` | Get employee view lookup |
| `GET /k/timesheet/api/myteamemployees/timesheet/projectclientlookup` | Get project client lookup |
| `GET /k/timesheet/api/myteamemployees/timesheet/project/{projectId}/timedetails` | Get project time details |

### PSA (Professional Services Automation)

| Endpoint | Description |
|----------|-------------|
| `GET /k/timesheet/api/psa/analytics/settings/currencycode` | Get PSA currency settings |
| `GET /k/timesheet/api/psa/customview/{viewType}` | Get custom view |
| `GET /k/timesheet/api/psa/customview/columnidentifiers/{viewType}` | Get column identifiers |
| `GET /k/timesheet/api/psa/customview/summarydatapoints/{viewType}` | Get summary data points |
| `GET /k/timesheet/api/psa/opportunity/clientlookup` | Get opportunity client lookup |
| `GET /k/timesheet/api/psa/projectconversionrequest/count` | Get project conversion request count |
| `GET /k/timesheet/api/psa/projectconversionrequest/pending` | Get pending conversion requests |

### Parameters

- `fromDate/toDate` (date): Date range
- `startdate/endDate` (date): Start and end dates
- `projectId` (integer): Project ID

---

## Files Generated

1. **[`keka_openapi.yaml`](./keka_openapi.yaml)** - Unified OpenAPI 3.0 specification, the source this document was derived from. It contains ~140 GET paths, more than are broken out by module below - treat it as the more complete reference and this document as a curated summary.

---

## Notes

1. **Authentication**: All APIs require authentication. The exact authentication mechanism should be documented separately.

2. **Rate Limiting**: Rate limiting policies are not documented here and may apply.

3. **Pagination**: Many list endpoints support pagination using `pageIndex`/`pageNumber` and `pageSize` parameters.

4. **Date Formats**: Dates are typically in ISO 8601 format (YYYY-MM-DD or full datetime).

5. **IDs**: IDs can be either:
   - Numeric integers (e.g., employee ID: 217152)
   - UUIDs (e.g., request ID: a4b08d52-fbbd-f011-8194-6045bd729d4f)

6. **This documentation is based on captured network traffic and may not be complete**. Some endpoints may have additional parameters or behaviors not captured in this analysis.
