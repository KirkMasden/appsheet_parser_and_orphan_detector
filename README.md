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

👉 See [Downloading the Application Documentation HTML](https://files.kirkmasden.com/AppSheet/appsheet-parser-docs-complete.html#setup) for the full instructions.

👉 For a screenshot showing where to find it in the AppSheet editor, see [this post by Steve on the Google Developer forum](https://discuss.google.dev/t/search-your-app-documentation-for-specific-details-and-where-you-used-certain-expressions-and-more/74029/2).

#### 4. Run the suite

```bash
python master_parser_and_orphan_detector.py "MyApp_Data/Application Documentation.html"
```

This will create a timestamped folder with CSV outputs and offer to launch the interactive dependency analyzer.

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
