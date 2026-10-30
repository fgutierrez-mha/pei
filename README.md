# PEI Dashboard

Streamlit dashboard with two tabs: **EMR data** and **ExtendedReach data**.
The app reads only pre-computed, identifier-free CSVs from `aggregates/`; it never touches patient-level files.

## Files
| File | Purpose |
|---|---|
| `mhaPEI.py` | Streamlit app (reads `aggregates/*.csv`) |
| `mhaPEIAggregates.py` | Local-only script: Excel exports -> `aggregates/*.csv` |
| `requirements.txt`, `.streamlit/config.toml` | Dependencies and blue theme |

## Refresh the data (on the PC that holds the Excel files)
1. Put `Encounters.xlsx`, `Vitals.xlsx`, `Labs.xlsx` and `GeneralActivities_Split.xlsx` in `Desktop\PEI`.
2. `python mhaPEIAggregates.py [data_folder] [output_folder]`
3. `streamlit run mhaPEI.py`

## Variables
| Name | Where | Default | Meaning |
|---|---|---|---|
| `data_folder` (arg 1) | `mhaPEIAggregates.py` | `Desktop\PEI` | Folder with the Excel files |
| `output_folder` (arg 2) | `mhaPEIAggregates.py` | `./aggregates` | Where CSVs are written |
| `PEI_AGG_DIR` | `mhaPEI.py` (env var) | `./aggregates` | Folder the app reads |
| `CANCEL`, `RESCHED`, `NOSHOW` | top of `mhaPEIAggregates.py` | `cancel` / `resched` / no-show phrases | Keywords matched against `Visit Status` |
| `AGE_BINS`, `AGE_LABELS` | top of `mhaPEIAggregates.py` | 0-17, 18-29, 30-44, 45-64, 65+ | Age groups |

Definitions: *seen* = visit not cancelled/rescheduled/no-show; *patients on record* = unique patient IDs in Encounters;
*rescheduled* = status says so, or the patient has a later kept visit; chronic-condition classes use each patient's
latest reading (blood pressure uses the last reading in a cell; thresholds are in `mhaPEIAggregates.py`).

## Privacy
Raw Excel files, `.csv`, `.html` are git-ignored (`.gitignore`); only `aggregates/*.csv` may be committed. The CSVs
hold exact counts with no small-number suppression, so commit them only to a **private** repo. Streamlit Community
Cloud has no HIPAA BAA, which is acceptable only because no patient-level data is hosted.
