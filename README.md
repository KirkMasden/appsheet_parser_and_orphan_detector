# AppSheet Parser and Orphan Detector Suite

The **AppSheet Parser Suite** is a collection of modular Python scripts that analyze AppSheet application documentation exports (HTML format). It transforms complex and often opaque internal structures into clean, structured CSV files, enabling deep insights into component usage, dependencies, and technical debt.

### 🔍 Key Features

- Parses AppSheet HTML documentation into structured CSVs
- Identifies **orphaned views**, **columns**, **actions**, **slices**, and **format rules**
- Detects column/action pairs that can **never display**, regardless of reachability — a different question from orphan detection
- Traces **navigation paths**, **grouped action chains**, and **column dependencies**
- Offers interactive analyzers for exploring cross-component references
- Modular design: 22 focused scripts with clear dependencies and extensibility

---

### 📘 Full Technical Documentation

The full documentation—including setup, architecture, and phase-by-phase explanations—is hosted here:

👉 [Read the full documentation](https://files.kirkmasden.com/AppSheet/appsheet-parser-docs-complete.html)

---

### 🛠️ Setup Instructions

#### 1. Clone the repository

```bash
git clone https://github.com/KirkMasden/appsheet_parser_and_orphan_detector.git
cd appsheet_parser_and_orphan_detector
```

#### 2. Set up a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
pip install beautifulsoup4
```

#### 3. Getting your app's documentation HTML

This suite parses your AppSheet app's documentation, which the AppSheet editor makes available as a web page. Open that page and save it as HTML — this becomes the `Application Documentation.html` file referenced below. The suite also expects a few supplementary text files (`actions.txt`, `views1.txt`, `views2.txt`, and optionally `bot_actions.txt`), as shown in the folder structure example further down. Place all of these files together in a data folder alongside this repository, as in that example.

Which editor: the documentation page is available from both the current AppSheet editor and the legacy editor. The three supplementary text files (`actions.txt`, `views1.txt`, `views2.txt`) are captured by select-all-and-paste from pages of the **legacy** editor, as the linked instructions describe; `bot_actions.txt` is written by hand, because the documentation export predates AppSheet automation and carries no bot information. If Google retires the legacy editor, the capture step is the one that will need revisiting — the parser itself does not depend on it.

👉 See [Downloading the Application Documentation HTML](https://files.kirkmasden.com/AppSheet/appsheet-parser-docs-complete.html#setup) for the full instructions.

👉 For a screenshot showing where to find it in the AppSheet editor, see [this post by Steve on the Google Developer forum](https://discuss.google.dev/t/search-your-app-documentation-for-specific-details-and-where-you-used-certain-expressions-and-more/74029/2).

#### 4. Run the suite

`MyApp_Data` sits alongside the repository, not inside it (see the folder structure below) — from inside `appsheet_parser_and_orphan_detector` after step 1's `cd`, that means going up one level for both the input file and the output location:

```bash
python master_parser_and_orphan_detector.py "../MyApp_Data/Application Documentation.html" -o ..
```

`-o` sets where the timestamped output folder is created; without it, the default is the current directory — which, run from inside the repo as above, would put your output folder inside the repository itself rather than alongside `MyApp_Data`. `-o ..` puts it in the parent folder instead, matching the layout below.

This will create a timestamped folder with CSV outputs and offer to launch the interactive dependency analyzer.

If you intend to work with the output through an AI assistant (next section), answer `n` to that offer — the interactive analyzer is optional and the CSVs are already complete when it appears. Running the suite from a script with no terminal attached raises `EOFError` at that same prompt; all output has been written by then, so this is a known cosmetic limitation rather than a failed parse.

---

### 🤖 Working with the output through an AI assistant

The CSVs can be read directly, but the suite is designed to be used through an AI coding assistant such as Claude Code, which can read the parse output, run the analyzer modules, and answer questions about your app in plain language. This is the primary way the suite is meant to be used; the interactive menus are an optional alternative.

1. Start the assistant **in this repository's directory**, so that it reads `CLAUDE.md` (or `AGENTS.md` for tools other than Claude Code). Those two files tell it what each CSV contains, which module answers which kind of question, and — most importantly — what the suite cannot see.
2. Tell it where your timestamped output folder is.
3. Ask a question about your app. The kind of question it is built for, in the maintainer's own words:

   *"I made this action and expected it to show up on the view but it isn't. Find out why."*

   *"I'm looking at such-and-such view but I can't remember how the user gets here. Please tell me the ways, including via dashboards, etc."*

   *"Check to see if I have any actions that aren't being used and can be deleted."*

Expect the assistant to ask you to look at your running app and report what you see. That is by design: the export records what your app *defines*, not what it *displays*, and some questions can only be settled by tapping a button and watching what happens.

**What the suite does not see.** The suite reports whether a navigation path *exists* in your app definition, not whether it can *fire* — conditions that depend on live data, column-level `Show_If`, and anything done by bots are outside what a static parse can settle, so a view or action reported as reachable may not be, and an orphan reported is a **candidate**, not a confirmed dead component. `CLAUDE.md`'s section "What this suite does not see" states these limits precisely, and `STATUS.md` records every known defect; read both before acting on a finding, and treat "delete this" as a decision for you, not the tool.

Other project documents, for anyone who wants to go deeper: `APPSHEET_BEHAVIOR.md`, at the repository root, records AppSheet's display rules as this project has observed or documented them, with the strength of each source. `maintainer/RELEASE_CHECKLIST.md` and `maintainer/CONSOLIDATION_PLAN.md` record the pre-publication worklist and a completed refactor plan — the maintainer's own working documents, not aimed at a user or an agent, which is why they live in their own `maintainer/` directory rather than at the root alongside `STATUS.md` and `APPSHEET_BEHAVIOR.md`. None of the three are needed to use the suite.

---

### 📂 Folder Structure Example

```
AppSheetAnalysis/
├── appsheet_parser_and_orphan_detector/  # This repository
├── MyApp_Data/
│   ├── Application Documentation.html
│   ├── actions.txt
│   ├── views1.txt
│   ├── views2.txt
│   └── bot_actions.txt (optional)
└── venv/
```

---

### 🗂️ Workspace layout for sheet_derivation

`sheet_derivation/` is a second tool in this same repository: it reads a captured Google Sheets workbook (via `sheet_capture.gs`) and derives artifacts describing it, joining against the app-side CSVs above where the two overlap. It uses its own workspace layout, in the same parent directory as this repository (the **workspace**):

```
AppSheetAnalysis/
├── appsheet_parser_and_orphan_detector/  # This repository
├── apps/
│   └── <snapshot>/
│       ├── Application Documentation.html
│       ├── actions.txt
│       ├── views1.txt
│       ├── views2.txt
│       ├── formulas.json
│       └── values.json
└── output/
    └── <snapshot>/
        ├── app/             # the app-side CSVs
        ├── sheet/           # the stage 2-5 JSONL and CSV artifacts
        ├── gates/           # gate reports (maintainer use)
        └── investigations/  # agent-written reports
```

Recommended snapshot naming, for runs from now on: `<appname>_<YYYYMMDD_HHMMSS>` — the same name for both the `apps/<snapshot>/` directory and its `output/<snapshot>/` counterpart, so the two are found together by construction. (Directories from before this convention used a doubled timestamp and role words like `baseline`/`regression_reference`; those stay exactly as they are — see `STATUS.md`'s 2026-09-14 entry.)

**The input side is flat, deliberately.** One directory per snapshot under `apps/`, named however the user likes, holding all six prepared files undifferentiated — the four app-side files from AppSheet's own export and the paste procedure above, and the two capture files from `sheet_capture.gs`. One app export and one sheet capture per snapshot, so the pairing cannot drift.

**The output side is structured, deliberately.** `output/<snapshot>/` mirrors the snapshot name and separates what was produced into `app/`, `sheet/`, `gates/`, and `investigations/`.

**The rule behind the asymmetry:** flat where a human assembles, structured where a human or an agent reads. Assembling a snapshot's input is the step a user can get wrong — six files with fixed names in one folder is the easiest shape to get right by hand, and the easiest to get visibly wrong (a folder with four files looks, at a glance, like a folder with all six). Reading the output is a different job, done by a human or an agent who benefits from the structure instead. Do not "fix" this into one shape or the other — the asymmetry is the point, not an inconsistency.

Because a flat input directory can silently be missing half of what a snapshot needs, `python -m sheet_derivation.snapshot <snapshot_dir>` reports exactly what it found and what it didn't — which app-side files are present, which capture files are present, and anything present but not recognized — rather than leaving a missing half invisible until something downstream fails confusingly.

`sheet_derivation`'s own stages, its runner, and its maintainer gate-check scripts are all still ordinary command-line programs — every one of them (`python -m sheet_derivation.stageN`, `python -m sheet_derivation.run`, `python -m sheet_derivation.gates.<name>`) can be run directly from a terminal, same as the app-side parsers and detectors above. An `apps/<snapshot>/` directory can be passed directly as a capture directory to any of them (its `formulas.json`/`values.json` are found the same way any other capture directory's files are); nothing about this layout is required for direct invocation to work, and an explicit path argument always overrides any default.

**The gate scripts' own `--output-dir` default is `<workspace>/output/gates` — not any snapshot's own `output/<snapshot>/gates/`.** It exists so an ad hoc gate-check run has somewhere sensible to land without an argument, but it is one shared location, not a per-snapshot one: a later run there overwrites an earlier one's reports. For a run whose reports are meant to be kept as part of a specific snapshot's record, pass `--output-dir` explicitly, pointed at that snapshot's own `output/<snapshot>/gates/`.

Existing parse-output directories from before this layout, and `sheet_derivation_output/`, are untouched by this convention — they stay exactly where they are, cited exactly as before; only new runs use `apps/`/`output/`.

---

### 📄 License

MIT License

---

### 🙋 Author

**Kirk Masden**  
[GitHub](https://github.com/KirkMasden) ・ [Website](https://kirkmasden.com)
