# Implementation Plan: Retro Export Cascading Filters

## Overview

Implement cascading filter dropdowns and a live record-count preview for the Retro Export modal. The work touches three existing files only: `app.py` (two new endpoints), `templates/index.html` (redesigned modal HTML), and `static/app.js` (refactored filter loading and new cascading/count logic). No new files or dependencies are introduced.

## Tasks

- [x] 1. Add `/api/retro/filters` endpoint to `app.py`
  - [x] 1.1 Implement the `/api/retro/filters` GET endpoint
    - Open RETRO.csv with `csv.reader`; return 404 if file missing, 500 if required columns (`state_abb`, `el_type`, `el_year`) are absent
    - Accept optional `state` and `el_type` query params; treat empty strings as absent
    - Always return all distinct `state_abb` values (unfiltered) in `states`
    - Return `el_types` filtered to the given `state` when provided; otherwise all distinct values
    - Return `years` filtered to the `state`+`el_type` intersection, or `state`-only, or `el_type`-only, or all distinct values, depending on which params are present
    - Sort `states` and `el_types` ascending alphabetically; sort `years` ascending numerically (cast to int)
    - Return HTTP 200 with empty lists when CSV has only a header row
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 6.2_

  - [ ]* 1.2 Write property test for `/api/retro/filters` — Property 1: filter results are subsets of full CSV data
    - **Property 1: Filter results are subsets of the full CSV data**
    - Generate random CSV rows with arbitrary `state_abb`, `el_type`, `el_year`; draw a random `state` param from the generated states
    - Assert every `el_type` and `year` in the response appears in at least one row matching the given state
    - **Validates: Requirements 1.3**

  - [ ]* 1.3 Write property test for `/api/retro/filters` — Property 2: dual-parameter filter results are subsets of state+type intersection
    - **Property 2: Dual-parameter filter results are subsets of the state+type intersection**
    - Generate random CSV rows; draw a random `(state, el_type)` pair from the generated data
    - Assert every `year` in the response appears in at least one row matching both state and el_type
    - **Validates: Requirements 1.4**

  - [ ]* 1.4 Write property test for `/api/retro/filters` — Property 3: type-only filter results are subsets of the type's rows
    - **Property 3: Type-only filter results are subsets of the type's rows**
    - Generate random CSV rows; draw a random `el_type` param from the generated data
    - Assert every `year` in the response appears in at least one row matching that el_type
    - **Validates: Requirements 1.5**

  - [ ]* 1.5 Write property test for `/api/retro/filters` — Property 4: response lists are correctly sorted
    - **Property 4: Filter API response lists are correctly sorted**
    - Generate random CSV rows with arbitrary values
    - Assert `states == sorted(distinct states)`, `el_types == sorted(distinct el_types)`, `years == sorted(distinct years, key=int)`
    - **Validates: Requirements 1.8**

- [x] 2. Add `/api/retro/count` endpoint to `app.py`
  - [x] 2.1 Implement the `/api/retro/count` GET endpoint
    - Open RETRO.csv; return 404 if missing
    - Accept optional `state`, `el_type`, `year` query params; treat empty strings as absent
    - Validate `year` when provided: must be a valid integer in range 1900–2100; return 400 with `{"error": "Invalid year parameter"}` otherwise
    - Count data rows matching all non-empty filters; return `{"count": N}`
    - Return `{"count": 0}` for a header-only CSV
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 2.2 Write property test for `/api/retro/count` — Property 5: count API returns exact match count
    - **Property 5: Count API returns exact match count for any filter combination**
    - Generate random CSV rows; draw a random subset of (state, el_type, year) params including empty strings
    - Assert returned count equals `len([r for r in rows if matches(r, params)])`
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 2.3 Write property test for `/api/retro/count` — Property 6: invalid year values always produce HTTP 400
    - **Property 6: Invalid year values always produce HTTP 400**
    - Generate arbitrary strings that are not valid integers in [1900, 2100] (letters, floats, out-of-range integers, empty-after-strip)
    - Assert response status is 400 with `{"error": "Invalid year parameter"}`
    - **Validates: Requirements 2.7**

- [x] 3. Checkpoint — backend endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Refactor `loadFilters()` and add `loadRetroFilters()` in `static/app.js`
  - [x] 4.1 Remove retro dropdown population from `loadFilters()`
    - Delete the four lines in `loadFilters()` that append options to `retro-state`, `retro-type`, and `retro-year`
    - The main dashboard dropdowns (`filter-state`, `filter-type`, `filter-year`) must continue to be populated from `/api/filters` unchanged
    - _Requirements: 6.1, 6.3, 6.4_

  - [x] 4.2 Implement `loadRetroFilters(params = {})` function
    - Declare module-level cache `let retroCache = { states: [], types: [], years: [] }` and sequence counter `let retroCountSeq = 0`
    - Build query string from `params` (omit empty `state` / `el_type` values)
    - Disable `retro-type` and `retro-year` before the fetch; re-enable on success or error
    - On success with no params: cache full lists in `retroCache`; populate `retro-state` (initial load only)
    - Always repopulate `retro-type` preserving prior selection if still in new list; reset to blank otherwise
    - Always repopulate `retro-year` preserving prior selection if still in new list; reset to blank otherwise
    - On error: call `showToast(msg, true)`; leave dropdown options and selected values unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9, 3.10, 3.11, 6.1, 6.5_

  - [ ]* 4.3 Write property test for `loadRetroFilters` — Property 7: dropdown repopulation preserves valid prior selections
    - **Property 7: Dropdown repopulation preserves valid prior selections**
    - For any prior selection value in `retro-type` or `retro-year`, after cascading repopulation: if the prior value is in the new list the selected value must remain; if absent the dropdown must reset to blank
    - Test using a DOM stub or jsdom environment
    - **Validates: Requirements 3.5, 3.6**

- [ ] 5. Implement `updateRetroCount()` in `static/app.js`
  - [x] 5.1 Implement `updateRetroCount()` function
    - Read current values of `retro-state`, `retro-type`, `retro-year`
    - Increment `retroCountSeq`; capture the current seq value in closure
    - Show loading indicator ("…") in the `retro-count-preview` element
    - Call `GET /api/retro/count` with only non-empty params
    - On success: if seq matches current, update preview text to "N records found"; enable Download button if N > 0, disable if N == 0
    - On error: if seq matches current, set preview text to "—"; disable Download button
    - Silently discard stale responses (seq mismatch)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 5.2 Write property test for `updateRetroCount` — Property 8: count preview text matches API response
    - **Property 8: Count preview text matches the API response for any count value**
    - For any integer N returned by `/api/retro/count`, the `retro-count-preview` element must display exactly "N records found" and the Download button's `disabled` attribute must be set iff N == 0
    - Test using a DOM stub or jsdom environment
    - **Validates: Requirements 4.4, 4.5, 4.7**

- [x] 6. Implement `openRetroModal()` and `closeRetroModal()` in `static/app.js`
  - [x] 6.1 Extract and implement `openRetroModal()` function
    - Move the existing `nav-retro` click handler body into a named `openRetroModal()` function
    - Show the overlay (existing animation: remove `opacity-0`/`pointer-events-none`, add `scale-100`)
    - Call `loadRetroFilters()` with no params (initial population + cache)
    - Call `updateRetroCount()` (show total count)
    - Wire `nav-retro` click to call `openRetroModal()`
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 6.3_

  - [x] 6.2 Extract and implement `closeRetroModal()` function
    - Move the existing inline close handler body into a named `closeRetroModal()` function
    - Reset `retroCountSeq` to prevent stale callbacks from a previous session updating the UI after close
    - Wire `retro-close`, `retro-cancel`, overlay-click, and Escape key to call `closeRetroModal()`
    - _Requirements: (supports 4.2 stale-discard behaviour)_

  - [x] 6.3 Attach cascading change handlers for `retro-state` and `retro-type`
    - `retro-state` change: if value non-empty call `loadRetroFilters({ state })`; if value empty restore full cached lists from `retroCache` and clear both downstream selections; then call `updateRetroCount()`
    - `retro-type` change: call `loadRetroFilters({ state: currentState, el_type: selectedType })` (omit state if empty); then call `updateRetroCount()`
    - `retro-year` change: call `updateRetroCount()`
    - _Requirements: 3.4, 3.7, 3.8, 3.9, 4.2_

  - [ ]* 6.4 Write property test for data isolation — Property 9: retro modal filter options are independent of main dashboard filter state
    - **Property 9: Retro modal filter options are independent of main dashboard filter state**
    - For any combination of values in `filter-state`, `filter-type`, `filter-year`, the options in `retro-state`, `retro-type`, `retro-year` must equal the response from `GET /api/retro/filters` with no query parameters
    - **Validates: Requirements 6.3, 6.4**

- [x] 7. Redesign the Retro Export Modal HTML in `templates/index.html`
  - [x] 7.1 Redesign the retro modal markup
    - Replace the current two-column grid layout with a top-to-bottom stacked filter layout
    - Add visible step labels ("① State", "② Election Type", "③ Election Year") above each dropdown to communicate cascading dependency
    - Add a `retro-count-preview` element in a visually distinct info band (bordered/shaded row) between the filter controls and the action buttons; initial text "—"
    - Move the Format selector (`retro-format`) into the footer action area alongside the Download button
    - Apply `disabled` attribute to `retro-download` by default (enabled only when count > 0)
    - Apply `disabled` attribute to `retro-type` and `retro-year` by default (enabled by `loadRetroFilters`)
    - Use Inter font, slate colour palette, and Tailwind utility classes consistent with the rest of the dashboard
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 8. Final checkpoint — full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` (Python) and a DOM stub (JS); run with `pytest` for backend tests
- Checkpoints ensure incremental validation after each major layer
- The existing `/api/retro/export` endpoint and `/api/filters` endpoint are unchanged
- `retroCountSeq` is reset in `closeRetroModal()` to prevent stale async callbacks from a previous modal session

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "2.2", "2.3", "4.1", "7.1"] },
    { "id": 2, "tasks": ["4.2"] },
    { "id": 3, "tasks": ["4.3", "5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1", "6.2"] },
    { "id": 5, "tasks": ["6.3"] },
    { "id": 6, "tasks": ["6.4"] }
  ]
}
```
