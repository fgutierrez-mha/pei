# PEI Dashboard

Streamlit dashboard with two tabs: **EMR data** and **ExtendedReach data**.
The app reads only pre-computed, identifier-free CSVs from `aggregates/`; it never touches patient-level files.

## Files
| File | Purpose |
|---|---|
| `mhaPEI.py` | Streamlit app (reads `aggregates/*.csv`) |
| `mhaPEIAggregates.py` | Local-only script: Excel exports -> `aggregates/*.csv` |
| `assets/mha_logo.png` | Logo shown in the dashboard header (resized copy of `MHA Logo Vector.png`) |
| `requirements.txt`, `.streamlit/config.toml` | Dependencies and blue theme |

## Refresh the data (on the PC that holds the Excel files)
1. Put `Encounters.xlsx`, `Vitals.xlsx`, `Labs.xlsx` and `GeneralActivities_Split.xlsx` in `Desktop\PEI`.
2. `python mhaPEIAggregates.py [data_folder] [output_folder]`
3. `streamlit run mhaPEI.py`

## Using the dashboard
Each tab has a **Time Period** picker: All Time, Last 12 / 6 / 3 Months, Year to Date, or Custom (pick From and To months).
It filters the monthly charts; demographics and chronic-condition views cover all patients.

## Variables
| Name | Where | Default | Meaning |
|---|---|---|---|
| `data_folder` (arg 1) | `mhaPEIAggregates.py` | `Desktop\PEI` | Folder with the Excel files |
| `output_folder` (arg 2) | `mhaPEIAggregates.py` | `./aggregates` | Where CSVs are written |
| `PEI_AGG_DIR` | `mhaPEI.py` (env var) | `./aggregates` | Folder the app reads |
| `SEEN`, `CANCEL`, `RESCHED`, `NOSHOW` | top of `mhaPEIAggregates.py` | see file | Keywords matched against `Visit Status` |
| `AGE_BINS`, `AGE_LABELS` | top of `mhaPEIAggregates.py` | 0-17, 18-29, 30-44, 45-64, 65+ | Age groups |

Definitions: *seen* = Visit Status is completed, checked out or checked in (`SEEN`); *cancellation type* = Visit Status of cancelled/rescheduled rows (the Reason column is free text and is not published; Visit Type free text is bucketed as "Other (free text)"); *patients on record* = unique patient IDs in Encounters;
*rescheduled* = status says so, or the patient has a later kept visit; chronic-condition classes use each patient's
latest reading (blood pressure uses the last reading in a cell; thresholds are in `mhaPEIAggregates.py`).

## Privacy
Raw Excel files, `.csv`, `.html` are git-ignored (`.gitignore`); only `aggregates/*.csv` may be committed. The CSVs
hold exact counts (no small-number suppression) and no identifiers or free text. Streamlit Community Cloud has no HIPAA BAA, which
is acceptable only because no patient-level data is hosted.
