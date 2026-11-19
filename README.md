# AppSheet Parser and Orphan Detector Suite

**Project status (2026-11-19).** This release closes the edits and improvements I have planned for now. I'm stepping back from the project for a while, and I'm not sure when I'll have the time or inclination to do more. Known next steps are listed in `STATUS.md`. Forking and improvements from others are welcome.

The **AppSheet Parser Suite** reads an AppSheet app's documentation export and the Google Sheets workbook behind it, and turns both into structured files that an AI coding agent can read. Rather than running the scripts and interpreting CSV files yourself, you ask your agent questions about your app in ordinary language and it does the work.

Finding orphaned components — views, actions, columns, slices and format rules that nothing uses any more — is still there, and is now one use among many.

### 🔍 How it works

The relationships that matter in an AppSheet app — which action attaches to which column, which views render it, which sheet columns feed which — are not readily apparent in the AppSheet documentation and Google Sheets files. They have to be worked out. That derivation is what the scripts do, and it is what makes more advanced analysis by an AI agent possible. The scripts produce:

- Structured CSVs of every view, action, column, slice and format rule in your app, with the navigation paths, grouped action chains and dependencies between them
- A formula inventory, a per-sheet schema, a column dependency graph and a dangling-reference list derived from your Google Sheets workbook, joined against the app's own column names
- A formula checkup that compares each spreadsheet formula behind an app column with the copy AppSheet stores of it, taking into account whether the app can add or edit rows in that table, and gives a mild heads-up where the two have drifted apart or a formula could be overwritten
- Orphan candidates — views, columns, actions, slices and format rules that nothing appears to use any more
- Inline actions whose own condition contradicts the `Show_If` of the column they attach to, so the button can never appear whatever the data holds

Your agent uses this parsed data when answering natural language questions about your app. Questions not directly answered by the scripts can often be answered by AI inference. In addition, the suite includes interactive analyzers for exploring view, column and action dependencies directly from a terminal, should you prefer to browse directly instead of relying on AI.

---

### 📘 Full Documentation

👉 [Read the full documentation](https://files.kirkmasden.com/AppSheet/appsheet-parser-docs-complete.html)

The setup instructions are on that page, not here: downloading the suite, preparing your app's files, capturing your Google Sheets workbook, and pointing your agent at the result. Please start there. What follows below is the repository's own reference — the folder layout, the exact commands, and where the other project documents are.

The documentation for the original version of the suite, for anyone who would rather run the scripts directly from a terminal, is kept here:

👉 [Original documentation](https://files.kirkmasden.com/AppSheet/appsheet-parser-docs-original.html)

---

### 📂 Folder layout

Your working folder holds the extracted suite, with `apps/` and `output/` alongside it:

```
AppSheetAnalysis/
├── appsheet_parser_and_orphan_detector-main/   (the extracted suite)
├── apps/
│   └── MyApp_20260914_101500/
│       ├── Application Documentation.html
│       ├── actions.txt
│       ├── views1.txt
│       ├── views2.txt
│       ├── bot_actions.txt (optional)
│       ├── MyWorkbook_formulas_20260914-101500.json
│       └── MyWorkbook_values_20260914-101500.json
└── output/
    └── MyApp_20260914_101500/
        ├── app/             # the app-side CSVs
        ├── sheet/           # the stage 2-5 JSONL and CSV artifacts
        ├── gates/           # gate reports (maintainer use)
        └── investigations/  # agent-written reports
```

**Note**: The names shown above are examples. `MyApp_20260914_101500` is a folder you create and can call anything you like, though a name combining the app name with the date and time of the capture may be advantageous if you wind up analyzing successive versions of the same app; the output folder is given the same name, so the two stay together. The two JSON files are written by `sheet_capture.gs`, which adds a timestamp to each name so that successive captures of the same workbook do not overwrite one another. You do not need to rename them. If you do rename them, all that matters is that one contains `formulas` and the other contains `values`, in lower case, and that both end in `.json` — the rest of the name is ignored. What does matter is where they sit: both files, and all the others, go directly in the one folder, never in a subfolder. Keep only one pair there; if two files in the folder both look like formula captures, the scripts will stop and tell you rather than guess which you meant.


---

### 🤖 Working through an AI agent

Give your agent two paths: the folder holding your app's files, and `CLAUDE.md` in this repository (or `AGENTS.md`, for agents other than Claude Code). That markdown file tells it what each CSV contains, which module answers which kind of question, and — most importantly — what the suite cannot see. Ask it to parse the data, then ask your question.

The kind of question it is built for:

> *"I made this action and expected it to show up on the view but it isn't. Find out why."*

> *"I'm looking at such-and-such view but I can't remember how the user gets here. Please tell me the ways, including via dashboards, etc."*

> *"Trace the value shown in such-and-such column back to where it is calculated in the spreadsheet."*

Expect your agent to ask you to look at your running app and report what you see. That is by design: the export records what your app *defines*, not what it *displays*, and some questions can only be settled by tapping a button and watching what happens.

**What the suite does not see.** The suite reports whether a navigation path *exists* in your app definition, not whether it can *fire* — conditions that depend on live data, column-level `Show_If`, and anything done by bots are outside what a static parse can settle. So a view or action reported as reachable may not be, and an orphan reported is a **candidate**, not a confirmed dead component. `CLAUDE.md`'s section "What this suite does not see" states these limits precisely, and `STATUS.md` records every known defect; read both before acting on a finding, and treat "delete this" as a decision for you, not the tool.

---

### ▶️ Running the scripts yourself

Your agent runs these for you. They are documented here for anyone who would rather run them by hand.

The scripts need Python 3 and one third-party library, `beautifulsoup4`. To install them yourself, in a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
pip install beautifulsoup4
```

Both commands below are run from inside the extracted suite's own folder, so `apps/` and `output/` — one level up — are reached with `../`. The two are always separate commands: nothing here runs both together. Run the app side first if you want the sheet side's last step, the join between the app's columns and the sheet's headers, to have something to join against.

The app side:

```bash
python master_parser_and_orphan_detector.py "../apps/MyApp_20260914_101500/Application Documentation.html" -o "../output/MyApp_20260914_101500/app" --output-as-is
```

The sheet side:

```bash
python -m sheet_derivation.run "../apps/MyApp_20260914_101500" "../output/MyApp_20260914_101500/sheet"
```

`--output-as-is` is what makes the first command write straight into the directory given by `-o`. Without it, the command creates its own timestamped subfolder underneath instead.

The sheet-side command finds what it needs by itself when the folders are laid out as above. It reads `Application Documentation.html` from the input folder, and takes the app-side results from `output/MyApp_20260914_101500/app`, beside its own `sheet` folder, printing a line saying which it used. If there are no app-side results there, it warns that the join will be ABSENT and says how to fix it. To use app-side results kept somewhere else, add `--appside-parse-dir` followed by that folder; it is optional, and when given it wins.

Before any stage runs, the sheet-side command checks that the app's export and the capture belong to the same workbook: every worksheet the export names for its Google Sheets tables should appear among the capture's sheets. If they all do, it says so in one line. If some are missing, it names them and carries on. If none are, it stops, because a mismatched pair still produces reports that look valid. If you are certain the two belong together, add `--allow-mismatch` to continue with a warning. The check cannot tell two versions of the same app apart, since their workbooks have the same sheet names. `python -m sheet_derivation.snapshot "../apps/MyApp_20260914_101500"` runs the same check, along with a list of which input files are present, so you can find a mismatch before parsing. It also compares the view names in `views1.txt` and `views2.txt`, and the action names in `actions.txt`, with the app's export, warning when some are missing and stopping when almost none match.

The scripts check that your files come from the same app, but they can't tell two copies of the same app apart. Please keep each set of files together.

The app-side command ends by offering to launch the interactive dependency analyzer. Answer `y` to explore dependencies now, or `n` if you only want the CSVs — they are already complete by the time the offer appears. Run from a script with no terminal attached, that same prompt raises `EOFError`; all output has been written by then, so this is a known cosmetic limitation rather than a failed parse.

`sheet_derivation`'s individual stages and its maintainer gate-check scripts are ordinary command-line programs too — `python -m sheet_derivation.stageN`, `python -m sheet_derivation.gates.<name>` — and an `apps/MyApp_20260914_101500/` folder can be passed directly to any of them.

---

### 📄 Other documents in this repository

- `CLAUDE.md` / `AGENTS.md` — identical in content; what an AI agent reads to work with the suite
- `STATUS.md` — known defects, recent fixes, and remaining work
- `APPSHEET_BEHAVIOR.md` — AppSheet's own display rules as this project has observed or documented them, with the strength of each source
- `AGENT_REPORT_FORMAT.md` — agent-facing: what to verify before reporting a finding, and the shape that report should take
- `maintainer/` — the maintainer's own working documents, not needed to use the suite

---

### 📄 License

MIT License

---

### 🙋 Author

**Kirk Masden**  
[GitHub](https://github.com/KirkMasden) ・ [Website](https://kirkmasden.com)
