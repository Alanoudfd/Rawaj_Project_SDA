# Data included in the submission

- `saudi_events.json`: the supplied Saudi occasions reference used by Strategy generation, validation and the client calendar. Entries marked tentative remain tentative. This file is unchanged from the working source.

## SQLite database snapshots

Two selected SQLite databases from the working project root are included:

- `rawaj.db`: saved application records, including restaurant data, accounts, messages, plans and relationship state.
- `rawaj_outreach_checkpoints_demo3.sqlite`: the separate demo workflow checkpoint state.

Each file is a consistent snapshot made with SQLite's backup API. Committed data from WAL files is included in the snapshot; separate `-wal` and `-shm` files are not required. Integrity checks and per-table row counts were verified against each source snapshot. The original databases were left in place. The copies do not update when the live project changes.

Database files are included for inspection. Application configuration was not changed: by default the app creates a new database under `02_src/`, unless `DATABASE_URL` points to an included copy. Database copies do not include the original `.env` secrets or the handoff file queue and are not a complete live-session restore bundle.

## Optional Research evaluation inputs

The Research evaluation notebook expects a compatible saved research report at:

`01_data/research_evaluation/dearduck_sa_research_20260922_112749.json`

and corresponding images in:

`01_data/research_evaluation/images/`

These files were not present in the working source available for packaging. They have not been fabricated or replaced with unrelated data. Supply the original authorized inputs, or change `REPORT_PATH` in your own notebook copy to a newly generated compatible report and provide matching images named `<content_id>_<index>.<extension>`.

Other legacy scripts may also refer to excluded generated research input files. Generate those inputs before running the scripts. Notebook execution can incur provider costs; local scoring alone is not evidence of a new live evaluation.
