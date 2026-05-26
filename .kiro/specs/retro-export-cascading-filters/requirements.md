# Requirements Document

## Introduction

This feature improves the Retro Export modal in the Form 20 Backlog Dashboard. Currently, the modal's three dropdowns (State, Election Type, Election Year) are all populated from the main `/api/filters` endpoint, which reads from the `records` SQLite table. This means the year dropdown shows every year in the database regardless of what state or election type is selected, and the filter options may not reflect the actual coverage of RETRO.csv.

The improvement introduces:
1. A new backend endpoint that reads RETRO.csv directly and returns cascading filter data.
2. Cascading dropdown behaviour: selecting a State narrows Election Types to those present for that state in RETRO.csv; selecting an Election Type (with or without a state) narrows Election Years to those valid for that state+type combination.
3. A record-count preview in the modal so users can see how many rows will be exported before clicking Download.
4. A redesigned modal UI with better visual hierarchy and a cleaner download area.

---

## Glossary

- **Retro_Export_Modal**: The overlay dialog opened via the "Retro Export" nav link, used to filter and download data from RETRO.csv.
- **RETRO.csv**: The source CSV file on disk containing historical election result rows with columns `state_abb`, `el_type`, `el_year` (among others).
- **Cascading_Filter**: A UI pattern where selecting a value in an upstream dropdown restricts the options available in downstream dropdowns.
- **Filter_API**: The new Flask endpoint `/api/retro/filters` that reads RETRO.csv and returns cascading filter options.
- **Count_API**: The new Flask endpoint `/api/retro/count` that returns the number of RETRO.csv rows matching the current filter selection.
- **Export_API**: The existing Flask endpoint `/api/retro/export` that streams a filtered subset of RETRO.csv as CSV or XLSX.
- **State_Dropdown**: The `<select id="retro-state">` element in the Retro Export Modal.
- **Type_Dropdown**: The `<select id="retro-type">` element in the Retro Export Modal.
- **Year_Dropdown**: The `<select id="retro-year">` element in the Retro Export Modal.
- **Record_Count_Preview**: A UI element inside the Retro Export Modal that displays the number of matching rows before the user downloads.

---

## Requirements

### Requirement 1: Cascading Filter API

**User Story:** As a developer, I want a dedicated backend endpoint that reads RETRO.csv and returns cascading filter options, so that the frontend can populate dropdowns with only the values that have actual data.

#### Acceptance Criteria

1. THE Filter_API SHALL expose a GET endpoint at `/api/retro/filters`.
2. WHEN the Filter_API receives a request with no query parameters, THE Filter_API SHALL return a JSON object with keys `states` (all distinct `state_abb` values), `el_types` (all distinct `el_type` values), and `years` (all distinct `el_year` values) from RETRO.csv.
3. WHEN the Filter_API receives a request with only a `state` query parameter, THE Filter_API SHALL return a JSON object with `el_types` containing only the distinct `el_type` values present in rows where `state_abb` equals the given state, and `years` containing only the distinct `el_year` values present in those same rows; if no rows match, both lists SHALL be empty.
4. WHEN the Filter_API receives a request with both a `state` and an `el_type` query parameter, THE Filter_API SHALL return a JSON object with `years` containing only the distinct `el_year` values present in rows where both `state_abb` equals the given state and `el_type` equals the given type; if no rows match, `years` SHALL be an empty list.
5. WHEN the Filter_API receives a request with only an `el_type` query parameter (no state), THE Filter_API SHALL return a JSON object with `years` containing only the distinct `el_year` values present in rows where `el_type` equals the given type; if no rows match, `years` SHALL be an empty list.
6. IF RETRO.csv does not exist on disk, THEN THE Filter_API SHALL return HTTP 404 with a JSON body `{"error": "RETRO.csv not found"}`.
7. IF RETRO.csv is missing the required columns `state_abb`, `el_type`, or `el_year`, THEN THE Filter_API SHALL return HTTP 500 with a JSON body `{"error": "Invalid RETRO.csv format: missing columns"}`.
8. THE Filter_API SHALL return `states` and `el_types` sorted in ascending alphabetical order, and `years` sorted in ascending numeric order.
9. WHEN RETRO.csv exists but contains only a header row with no data rows, THE Filter_API SHALL return HTTP 200 with all lists empty.

---

### Requirement 2: Record Count Preview API

**User Story:** As a user, I want to see how many records match my current filter selection before I download, so that I can confirm I have the right combination before committing to a download.

#### Acceptance Criteria

1. THE Count_API SHALL expose a GET endpoint at `/api/retro/count`.
2. WHEN the Count_API receives `state`, `el_type`, and `year` query parameters (all non-empty), THE Count_API SHALL return HTTP 200 with `{"count": N}` where N is the number of RETRO.csv data rows where `state_abb` equals `state`, `el_type` equals `el_type`, and `el_year` equals `year`; if no rows match, N SHALL be 0.
3. WHEN the Count_API receives a subset of the three parameters, empty-string values SHALL be treated as absent, and THE Count_API SHALL apply only the non-empty filters and return `{"count": N}` for matching rows.
4. WHEN the Count_API receives no parameters (or all empty), THE Count_API SHALL return `{"count": N}` where N is the total number of data rows in RETRO.csv, excluding the header row.
5. IF RETRO.csv does not exist, THEN THE Count_API SHALL return HTTP 404 with `{"error": "RETRO.csv not found"}`.
6. WHEN RETRO.csv exists but contains only a header row, THE Count_API SHALL return HTTP 200 with `{"count": 0}`.
7. IF the `year` parameter is provided but is not a valid integer in the range 1900–2100, THEN THE Count_API SHALL return HTTP 400 with `{"error": "Invalid year parameter"}`.

---

### Requirement 3: Cascading Dropdown Behaviour in the Frontend

**User Story:** As a user, I want the Election Type and Election Year dropdowns to automatically update when I change the State selection, so that I only see valid combinations and avoid downloading an empty file.

#### Acceptance Criteria

1. WHEN the Retro Export Modal is opened, THE State_Dropdown SHALL be populated with all distinct states returned by the Filter_API with no query parameters.
2. WHEN the Retro Export Modal is opened, THE Type_Dropdown SHALL be populated with all distinct election types returned by the Filter_API with no query parameters.
3. WHEN the Retro Export Modal is opened, THE Year_Dropdown SHALL be populated with all distinct years returned by the Filter_API with no query parameters.
4. WHEN the user selects a non-empty value in the State_Dropdown, THE frontend SHALL call the Filter_API with the selected state, then repopulate THE Type_Dropdown with the returned `el_types` and THE Year_Dropdown with the returned `years`.
5. IF the previously-selected Type value is absent from the repopulated Type_Dropdown list, THEN THE Type_Dropdown SHALL be reset to the blank/placeholder option.
6. IF the previously-selected Year value is absent from the repopulated Year_Dropdown list, THEN THE Year_Dropdown SHALL be reset to the blank/placeholder option.
7. WHEN the user selects a non-empty value in the Type_Dropdown while a state is already selected, THE frontend SHALL call the Filter_API with both the current state and the selected type, then repopulate THE Year_Dropdown with the returned `years`.
8. WHEN the user selects a non-empty value in the Type_Dropdown while no state is selected, THE frontend SHALL call the Filter_API with only the selected type, then repopulate THE Year_Dropdown with the returned `years`.
9. WHEN the user clears the State_Dropdown (selects the blank option), THE Type_Dropdown and THE Year_Dropdown SHALL be reset to the full option lists cached at modal-open time, and both selected values SHALL be cleared.
10. WHILE a Filter_API request is in flight, THE Type_Dropdown and THE Year_Dropdown SHALL have their `disabled` attribute set to prevent interaction.
11. IF the Filter_API returns an error, THEN THE frontend SHALL display a toast notification with the error message, and both the options list and the selected value of the affected dropdowns SHALL remain unchanged.

---

### Requirement 4: Record Count Preview in the Modal

**User Story:** As a user, I want to see a live record count inside the modal that updates as I change filters, so that I know whether my selection will produce any data before I click Download.

#### Acceptance Criteria

1. WHEN the Retro Export Modal is opened, THE Record_Count_Preview SHALL immediately call the Count_API with no parameters and display the total row count.
2. WHEN the user changes any dropdown value (State, Type, or Year), THE frontend SHALL call the Count_API with the current non-empty filter values and update THE Record_Count_Preview with the result; if a newer request completes before an older one, the older response SHALL be discarded.
3. WHILE a Count_API request is in flight, THE Record_Count_Preview SHALL display a loading indicator (e.g., a spinner or "…" text).
4. WHEN the Count_API returns a count of zero, THE Record_Count_Preview SHALL display "0 records found".
5. WHEN the Count_API returns a count greater than zero, THE Record_Count_Preview SHALL display "N records found" where N is the returned count.
6. IF the Count_API returns an error, THEN THE Record_Count_Preview SHALL display "—".
7. THE Download button SHALL be enabled when the last known count is greater than zero, and disabled when the last known count is zero or when no count has been received yet.

---

### Requirement 5: Redesigned Retro Export Modal UI

**User Story:** As a user, I want the Retro Export modal to have a polished, well-structured layout, so that the export workflow feels clear and professional.

#### Acceptance Criteria

1. THE Retro_Export_Modal SHALL display a header section containing the title text "Export Retro Data", a subtitle text "Filter and download from RETRO.csv", and a close (×) button aligned to the top-right.
2. THE Retro_Export_Modal SHALL display the State_Dropdown, Type_Dropdown, and Year_Dropdown in a top-to-bottom stacked order with visible step labels (e.g., "1 State", "2 Election Type", "3 Election Year") to communicate the cascading dependency.
3. THE Retro_Export_Modal SHALL display the Record_Count_Preview in a visually distinct info band (e.g., a bordered or shaded row) positioned between the filter controls and the action buttons.
4. THE Retro_Export_Modal SHALL display a Format selector (CSV / Excel toggle or select) in the footer action area alongside the Download button.
5. THE Download button SHALL use a filled, high-contrast background (e.g., `bg-slate-900 text-white`) and include a download icon when enabled.
6. IF the Download button is disabled (count is zero or no count received), THEN THE Download button SHALL render with a muted background (e.g., `bg-slate-300 text-slate-500 cursor-not-allowed`) and the `disabled` attribute SHALL be set.
7. THE Retro_Export_Modal SHALL use the Inter font, the slate colour palette, and Tailwind CSS utility classes consistent with the rest of the dashboard.
8. WHEN all three dropdowns have a value selected, THE Download button SHALL become active (enabled) only if the Record_Count_Preview shows a count greater than zero.

---

### Requirement 6: Data Isolation Between Main Filters and Retro Filters

**User Story:** As a developer, I want the Retro Export modal's filter options to be sourced exclusively from RETRO.csv, so that the modal accurately reflects retro data coverage rather than the records table.

#### Acceptance Criteria

1. THE Retro_Export_Modal SHALL populate its State_Dropdown, Type_Dropdown, and Year_Dropdown exclusively by calling the Filter_API (`/api/retro/filters`), not the main `/api/filters` endpoint.
2. THE Filter_API SHALL populate its response by reading RETRO.csv directly on every request, without querying the SQLite `records` table.
3. WHEN the Retro Export Modal is opened, THE frontend SHALL call the Filter_API to load initial dropdown options, regardless of any filters currently active in the main dashboard.
4. WHEN the main dashboard filter dropdowns (State, Type, Year in the header bar) are changed, THE Retro_Export_Modal dropdown options and selected values SHALL NOT change.
5. IF the Filter_API is unavailable when the modal is opened, THEN THE frontend SHALL display a toast error and all three retro dropdowns SHALL remain empty with their placeholder options shown.
