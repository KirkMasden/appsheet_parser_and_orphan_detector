# AppSheet Parser and Orphan Detector Suite

The **AppSheet Parser Suite** is a collection of modular Python scripts that analyze AppSheet application documentation exports (HTML format). It transforms complex and often opaque internal structures into clean, structured CSV files, enabling deep insights into component usage, dependencies, and technical debt.

### 🔍 Key Features

- Parses AppSheet HTML documentation into structured CSVs
- Identifies **orphaned views**, **columns**, **actions**, **slices**, and **format rules**
- Traces **navigation paths**, **grouped action chains**, and **column dependencies**
- Offers interactive analyzers for exploring cross-component references
- Modular design: 18+ focused scripts with clear dependencies and extensibility

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

```bash
python master_parser_and_orphan_detector.py "MyApp_Data/Application Documentation.html"
```

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

Other project documents at the repository root, for anyone who wants to go deeper: `APPSHEET_BEHAVIOR.md` records AppSheet's display rules as this project has observed or documented them, with the strength of each source; `CONSOLIDATION_PLAN.md` and `RELEASE_CHECKLIST.md` record the design and the worklist. They are working documents and are not needed to use the suite.

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

### 📄 License

MIT License

---

### 🙋 Author

**Kirk Masden**  
[GitHub](https://github.com/KirkMasden) ・ [Website](https://kirkmasden.com)
