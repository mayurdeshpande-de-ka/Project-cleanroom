# Design Document — Retro Export Cascading Filters

## Overview

This feature replaces the current Retro Export modal's static, database-driven dropdowns with cascading, RETRO.csv-driven dropdowns and adds a live record-count preview. The work spans two new Flask endpoints, a refactored frontend filter-loading function, cascading change handlers, and a redesigned modal layout.

The key design goals are:
- **Data isolation**: retro filter options come exclusively from RETRO.csv, never from the SQLite `records` table.
- **Cascading behaviour**: selecting State narrows Election Types; selecting State + Type narrows Election Years.
- **Informed download**: a live count preview tells the user how many rows will be exported before they click Download.
- **Minimal footprint**: no new dependencies, no build step — pure Flask + vanilla JS + Tailwind CDN.

---

## Architecture

The feature follows the existing layered architecture of the application:

```
Browser (index.html + app.js)
        │
        │  GET /api/retro/filters?state=&el_type=
        │  GET /api/retro/count?state=&el_type=&year=
        ▼
Flask (app.py)
        │
        │  csv.reader
        ▼
RETRO.csv (disk)
```

The two new endpoints are read-only and stateless — they open RETRO.csv on every request, apply in-memory filtering, and return JSON. No caching layer is introduced; the file is small enough that per-request reads are acceptable.

The existing `/api/retro/export` endpoint is unchanged. The existing `/api/filters` endpoint continues to serve the main dashboard header bar; it is no longer called by the retro modal.

### Request Flow — Modal Open

```
nav-retro click
  → openRetroModal()
      → loadRetroFilters()          GET /api/retro/filters (no params)
          → populate retro-state, retro-type, retro-year
          → cache fullStates, fullTypes, fullYears
      → updateRetroCount()          GET /api/retro/count (no params)
          → show total count in preview band
```

### Request Flow — State Change

```
retro-state change
  → loadRetroFilters({ state })     GET /api/retro/filters?state=XX
      → repopulate retro-type (preserve selection if still valid)
      → repopulate retro-year (preserve selection if still valid)
  → updateRetroCount()              GET /api/retro/count?state=XX
```

### Request Flow — Type Change

```
retro-type change
  → loadRetroFilters({ state, el_type })   GET /api/retro/filters?state=XX&el_type=GE
      → repopulate retro-year (preserve selection if still valid)
  → updateRetroCount()                     GET /api/retro/count?state=XX&el_type=GE
```

---

## Components and Interfaces

### Backend: `/api/retro/filters` (new)

**Method:** GET  
**Query parameters:**

| Parameter | Type   | Required | Description                        |
|-----------|--------|----------|------------------------------------|
| `state`   | string | No       | Filter by `state_abb` value        |
| `el_type` | string | No       | Filter by `el_type` value          |

**Response (200):**
```json
{
  "states":   ["AP", "GJ", "TN", ...],
  "el_types": ["AE", "GE", ...],
  "years":    [2009, 2014, 2019, ...]
}
```

- `states` is always returned (all distinct `state_abb` values, regardless of query params).
- `el_types` is filtered to the given `state` when `state` is provided; otherwise all distinct values.
- `years` is filtered to the given `state` + `el_type` combination when both are provided; to the given `state` alone when only `state` is provided; to the given `el_type` alone when only `el_type` is provided; otherwise all distinct values.
- All lists are sorted: `states` and `el_types` ascending alphabetically; `years` ascending numerically.

**Error responses:**

| Condition                        | Status | Body                                              |
|----------------------------------|--------|---------------------------------------------------|
| RETRO.csv not found              | 404    | `{"error": "RETRO.csv not found"}`                |
| Missing required columns         | 500    | `{"error": "Invalid RETRO.csv format: missing columns"}` |

---

### Backend: `/api/retro/count` (new)

**Method:** GET  
**Query parameters:**

| Parameter | Type   | Required | Description                        |
|-----------|--------|----------|------------------------------------|
| `state`   | string | No       | Filter by `state_abb`              |
| `el_type` | string | No       | Filter by `el_type`                |
| `year`    | string | No       | Filter by `el_year` (integer)      |

Empty-string values are treated as absent (no filter applied for that dimension).

**Response (200):**
```json
{ "count": 1842 }
```

**Error responses:**

| Condition                        | Status | Body                                              |
|----------------------------------|--------|---------------------------------------------------|
| RETRO.csv not found              | 404    | `{"error": "RETRO.csv not found"}`                |
| `year` not a valid integer 1900–2100 | 400 | `{"error": "Invalid year parameter"}`            |

---

### Frontend: `loadRetroFilters(params)` (new function)

Replaces the retro-specific population code currently inside `loadFilters()`.

```
loadRetroFilters(params = {})
  Builds query string from params (state, el_type — omit empty values)
  Sets retro-type and retro-year to disabled
  Calls GET /api/retro/filters?...
  On success:
    If no params: caches fullStates, fullTypes, fullYears
    Repopulates retro-state (only on initial load)
    Repopulates retro-type (preserving prior selection if still in new list)
    Repopulates retro-year (preserving prior selection if still in new list)
    Re-enables retro-type and retro-year
  On error:
    Re-enables dropdowns
    Calls showToast(errorMessage, true)
```

---

### Frontend: `updateRetroCount()` (new function)

```
updateRetroCount()
  Reads current values of retro-state, retro-type, retro-year
  Increments a request counter (retroCountSeq) to detect stale responses
  Shows loading indicator in count preview band
  Calls GET /api/retro/count?... (only non-empty params)
  On success (if seq matches current):
    Updates preview text to "N records found"
    Enables/disables Download button based on count > 0
  On error (if seq matches current):
    Sets preview text to "—"
    Disables Download button
  Stale responses (seq mismatch): silently discarded
```

---

### Frontend: `openRetroModal()` (refactored)

Extracted from the inline `nav-retro` click handler. Responsibilities:
1. Show the overlay (existing animation logic).
2. Call `loadRetroFilters()` with no params (initial population + cache).
3. Call `updateRetroCount()` (show total count).

---

### Frontend: `closeRetroModal()` (refactored)

Extracted from the existing inline close handler. Resets `retroCountSeq` to prevent stale callbacks from a previous session updating the UI after the modal is closed.

---

### `loadFilters()` — change

Remove the four lines that populate `retro-state`, `retro-type`, and `retro-year` from the `/api/filters` response. The main dashboard dropdowns (`filter-state`, `filter-type`, `filter-year`) continue to be populated from `/api/filters` as before.

---

## Data Models

### RETRO.csv columns used

| Column      | Type   | Description                          |
|-------------|--------|--------------------------------------|
| `state_abb` | string | Two-letter state abbreviation        |
| `el_type`   | string | Election type code (e.g. `GE`, `AE`) |
| `el_year`   | string | Election year (stored as string in CSV, cast to int for sorting and validation) |

All other columns are passed through unchanged to the export endpoint.

### In-memory filter state (frontend)

```js
// Cached at modal-open time; used to restore dropdowns when State is cleared
let retroCache = { states: [], types: [], years: [] };

// Monotonically increasing sequence number for count requests
let retroCountSeq = 0;
```

### API response shapes

```ts
// GET /api/retro/filters
interface FilterResponse {
  states:   string[];   // sorted ascending
  el_types: string[];   // sorted ascending
  years:    number[];   // sorted ascending
}

// GET /api/retro/count
interface CountResponse {
  count: number;
}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Filter results are subsets of the full CSV data

*For any* `state` value passed to `/api/retro/filters`, every `el_type` in the returned `el_types` list must appear in at least one RETRO.csv row where `state_abb` equals that state, and every `year` in the returned `years` list must appear in at least one row where `state_abb` equals that state.

**Validates: Requirements 1.3**

---

### Property 2: Dual-parameter filter results are subsets of the state+type intersection

*For any* `(state, el_type)` pair passed to `/api/retro/filters`, every `year` in the returned `years` list must appear in at least one RETRO.csv row where both `state_abb` equals `state` AND `el_type` equals `el_type`.

**Validates: Requirements 1.4**

---

### Property 3: Type-only filter results are subsets of the type's rows

*For any* `el_type` value passed to `/api/retro/filters` (with no `state`), every `year` in the returned `years` list must appear in at least one RETRO.csv row where `el_type` equals that value.

**Validates: Requirements 1.5**

---

### Property 4: Filter API response lists are correctly sorted

*For any* RETRO.csv content, the `states` list returned by `/api/retro/filters` must equal `sorted(distinct state_abb values)`, the `el_types` list must equal `sorted(distinct el_type values)`, and the `years` list must equal `sorted(distinct el_year values, key=int)`.

**Validates: Requirements 1.8**

---

### Property 5: Count API returns exact match count for any filter combination

*For any* combination of `state`, `el_type`, and `year` parameters (including empty subsets), the `count` returned by `/api/retro/count` must equal the number of RETRO.csv data rows that satisfy all non-empty filter conditions.

**Validates: Requirements 2.2, 2.3, 2.4**

---

### Property 6: Invalid year values always produce HTTP 400

*For any* string passed as the `year` parameter to `/api/retro/count` that is not a valid integer in the range 1900–2100, the endpoint must return HTTP 400 with `{"error": "Invalid year parameter"}`.

**Validates: Requirements 2.7**

---

### Property 7: Dropdown repopulation preserves valid prior selections

*For any* prior selection value in `retro-type` or `retro-year`, after a cascading repopulation triggered by a state or type change: if the prior value is present in the new option list, the dropdown's selected value must remain unchanged; if the prior value is absent from the new option list, the dropdown must be reset to the blank/placeholder option.

**Validates: Requirements 3.5, 3.6**

---

### Property 8: Count preview text matches the API response for any count value

*For any* integer `N` returned by `/api/retro/count`, the Record_Count_Preview element must display exactly "N records found", and the Download button's `disabled` attribute must be set if and only if `N == 0`.

**Validates: Requirements 4.4, 4.5, 4.7**

---

### Property 9: Retro modal filter options are independent of main dashboard filter state

*For any* combination of values selected in the main dashboard's `filter-state`, `filter-type`, and `filter-year` dropdowns, the options populated in the retro modal's `retro-state`, `retro-type`, and `retro-year` dropdowns must equal the response from `GET /api/retro/filters` with no query parameters.

**Validates: Requirements 6.3, 6.4**

---

## Error Handling

### Backend

| Scenario | Endpoint | Behaviour |
|---|---|---|
| RETRO.csv missing | `/api/retro/filters`, `/api/retro/count` | Return 404 `{"error": "RETRO.csv not found"}` |
| RETRO.csv missing required columns | `/api/retro/filters` | Return 500 `{"error": "Invalid RETRO.csv format: missing columns"}` |
| `year` param not a valid integer 1900–2100 | `/api/retro/count` | Return 400 `{"error": "Invalid year parameter"}` |
| RETRO.csv empty (header only) | Both | Return 200 with empty lists / `{"count": 0}` |
| Unexpected exception | Both | Return 500 `{"error": "<message>"}` (consistent with existing `/api/retro/export` pattern) |

### Frontend

| Scenario | Behaviour |
|---|---|
| `loadRetroFilters()` network/API error | Re-enable dropdowns; call `showToast(msg, true)`; leave dropdown options and selected values unchanged |
| `updateRetroCount()` network/API error | Set preview text to "—"; disable Download button; discard if stale |
| Filter_API unavailable on modal open | Toast error; all three retro dropdowns remain empty with placeholder options |
| Stale count response (newer request already completed) | Silently discard via `retroCountSeq` comparison |

---

## Testing Strategy

### Unit / Example-Based Tests (Python — `pytest`)

These cover specific scenarios and error conditions that are not suited to property-based testing:

- **Smoke**: `GET /api/retro/filters` and `GET /api/retro/count` return 200 with correct structure.
- **Example**: No-params call returns all distinct states, el_types, years from a known fixture CSV.
- **Error cases**: 404 when RETRO.csv missing; 500 when columns missing; 400 for invalid year; 200 with empty lists for header-only CSV.
- **Edge case**: Header-only CSV returns `{"count": 0}` and empty filter lists.

### Property-Based Tests (Python — `hypothesis`)

Property-based tests use `hypothesis` to generate random CSV content and random filter parameter combinations, then assert the universal properties defined above.

Each property test runs a minimum of **100 iterations**.

Tag format for each test: `# Feature: retro-export-cascading-filters, Property N: <property_text>`

**Property 1 — Filter results are subsets of full CSV data**
Generate: random CSV rows with arbitrary `state_abb`, `el_type`, `el_year` values; random `state` param drawn from the generated states.
Assert: every `el_type` and `year` in the response appears in at least one row matching the given state.

**Property 2 — Dual-parameter filter results are subsets of state+type intersection**
Generate: random CSV rows; random `(state, el_type)` pair drawn from the generated data.
Assert: every `year` in the response appears in at least one row matching both state and el_type.

**Property 3 — Type-only filter results are subsets of the type's rows**
Generate: random CSV rows; random `el_type` drawn from the generated data.
Assert: every `year` in the response appears in at least one row matching that el_type.

**Property 4 — Response lists are correctly sorted**
Generate: random CSV rows with arbitrary values.
Assert: `states == sorted(distinct states)`, `el_types == sorted(distinct el_types)`, `years == sorted(distinct years, key=int)`.

**Property 5 — Count API returns exact match count**
Generate: random CSV rows; random subset of (state, el_type, year) params (including empty strings).
Assert: returned count equals `len([r for r in rows if matches(r, params)])`.

**Property 6 — Invalid year values produce HTTP 400**
Generate: arbitrary strings that are not valid integers in [1900, 2100] (e.g. letters, floats, out-of-range integers, empty after strip).
Assert: response status is 400 with `{"error": "Invalid year parameter"}`.

### Frontend Tests (JavaScript — manual / integration)

The frontend logic (cascading repopulation, stale-response discard, count preview text, button enable/disable) is tested manually against the running server. The following scenarios must be verified:

- Opening the modal populates all three dropdowns and shows total count.
- Selecting a state narrows types and years; previously-selected values absent from new list are cleared.
- Clearing the state restores full cached lists.
- Selecting a type (with and without a state) narrows years.
- Rapid dropdown changes result in the preview showing the count for the last selection only.
- Network error on filter load shows toast; dropdowns unchanged.
- Network error on count shows "—" and disables Download.
- Download button is disabled when count is 0 and enabled when count > 0.
- Main dashboard filter changes have no effect on retro modal options.
