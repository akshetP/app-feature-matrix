# Copilot Instructions for app-feature-matrix

## Project Overview
A **Streamlit-based SaaS feature matrix viewer and editor** for tracking product features across multiple product tiers (Connect, Connect Pro Free, Connect Pro Pro Plan). The app parses TSV/CSV data, provides filtering/search, displays coverage metrics, enables inline editing, and exports to CSV.

## Architecture & Key Components

### Data Model
- **Core DataFrame Structure**: SECTION → FEATURE → [WEB column + 3 product coverage columns]
- **Coverage Values**: Y, N, PARTIAL, TBD (normalized to uppercase in `parse_matrix_text()`)
- See [app.py#L180-L210](app.py#L180-L210) for parsing logic that handles both TSV and CSV formats with robust fallback

### Main Workflows

**Data Input** (`parse_matrix_text()`, lines 96-132):
- Accepts TSV (tab-separated) as primary, CSV as secondary
- Auto-detects separator via `"\t" in first_line` heuristic
- Normalizes column names and ensures all expected columns exist
- Returns DataFrame with columns in order: META_COLS + PRODUCT_COLS

**Filtering & Display** (lines 253-318):
- Sidebar filters: sections (multiselect), WEB values, product focus
- "Show gaps" mode filters to rows where product_focus ≠ "Y"
- Search uses regex with case-insensitive FEATURE/SECTION matching
- Coverage counts calculated via `coverage_counts()` returning (Y, N, PARTIAL, TBD/Other) tuple

**Editing & Export**:
- `st.data_editor()` with selectbox columns for product coverage (line 332)
- CSV download preserves filtered/edited state via `make_download_csv()`
- Optional disk persistence for VM/Docker deployments (line 357)

## Project-Specific Patterns

### Data Normalization
The `coverage_counts()` function (lines 134-142) is the canonical pattern for analyzing coverage:
```python
# Always uppercase and strip whitespace before comparisons
v = df[col].astype(str).str.upper().str.strip()
y = (v == "Y").sum()  # Direct string equality, not fuzzy matching
```
**When modifying**: Ensure any new coverage-related logic follows this strict uppercase/stripped pattern.

### UI Column Configuration
`st.column_config.SelectboxColumn()` is used exclusively for product columns (line 338) with fixed options: `["Y", "N", "PARTIAL", "TBD", ""]`. This prevents invalid values and maintains data consistency.

### Default Data
`DEFAULT_TEXT` (lines 11-268) contains the full Sunsynk Connect matrix as TSV. This is the fallback dataset when no user input is provided. **Update this when the official matrix changes** rather than hardcoding separate test data.

## Common Development Tasks

### Adding a New Filter
Add to sidebar section (lines 231-246), apply filter to `fdf` DataFrame between lines 310-325. Follow the pattern: `fdf = fdf[fdf[col].isin(values)]`

### Modifying Coverage Display
The top metrics (lines 320-328) and summary table (lines 334-343) both call `coverage_counts()`. **Keep these synchronized** — any change to value counting must update both.

### Parsing New File Formats
All parsing logic centralizes in `parse_matrix_text()`. If you need to handle new formats (Excel, JSON), add them there and test with both TSV and CSV to avoid regressions.

## Dependencies & Runtime
- **Streamlit 1.37.1**: All UI via `st.*` functions. No custom components.
- **Pandas 2.2.2**: All data operations (read_csv, filtering, aggregation)
- **Run**: `streamlit run app.py` (starts dev server on http://localhost:8501)

## Testing Notes
- The default matrix has ~200 features across 5 sections; use subset filters to validate performance
- Disk persistence (line 357) only works on VM/Docker with write permissions; gracefully fails with `st.error()`
- CSV round-trip testing: upload filtered export to verify no column/value corruption

## Notes for AI Agents
- **Preserve the heuristic tab-detection logic** — it's intentionally simple to handle user-pasted content reliably
- **Always validate column existence** before accessing (see line 114-116 pattern)
- **The "Gap view" is a derived secondary view** (line 365+); it's computed from edited data, not stored separately
