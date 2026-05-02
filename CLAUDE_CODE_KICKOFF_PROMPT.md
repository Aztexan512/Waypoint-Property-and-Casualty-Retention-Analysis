# Portfolio Analytics Agent — Kickoff Prompt
**Author:** Luciano Casillas
**Version:** 1.0
**Usage:** Place this file and PORTFOLIO_AGENT_BRIEF.md in the project folder.
Open Claude Code, navigate to the folder, and paste everything below the
horizontal rule as your first message.

---

---

I am building an analytics portfolio project. The full system brief is in
`PORTFOLIO_AGENT_BRIEF.md` in the current directory. Read that file completely
before doing anything else.

**My background:** Senior Data Analyst. Strong in SQL, Python, Streamlit.
This is a portfolio project built during a job search targeting
data analyst roles in insurance and adjacent industries.

**Framework:** WAT (Workflows / Agents / Tasks)
**Project path:** `C:\Users\lucia\OneDrive\Portfolio Projects\`

---

## WORKING NORMS -- apply to every phase

- Read `PORTFOLIO_AGENT_BRIEF.md` fully before any action.
- Never create files or folders until Gate 3 is approved.
- Never put files in the wrong folder. The GitHub structure and the build
  structure are different. The brief defines both.
- Every Python function gets a docstring.
- Every SQL file gets a header comment block: purpose, inputs, outputs,
  author (Luciano Casillas), date created.
- Add a `# DESIGN DECISION:` comment whenever you make a choice not
  explicitly stated in the brief.
- State assumptions explicitly before acting on them.
- Snowflake-compatible ANSI SQL is the standard throughout.
- Python 3.12 required.
- Never truncate code. Always write complete, runnable files.
- No em dashes anywhere in generated content. Use a comma, semicolon,
  or rewrite as two sentences.
- No "leveraging," "delving," "it is worth noting," or "synergies."
- When a phase is complete, output a summary: files created, design
  decisions made, assumptions documented, what comes next.

### Environment notes (VS Code + Python 3.12)

**Pylance import warnings:** If VS Code flags streamlit, pandas, numpy, or
plotly as unresolved imports, this is not a code bug. The packages are
installed and Streamlit runs correctly. The VS Code Python interpreter is
pointed at the wrong Python installation. Fix: `Ctrl+Shift+P` →
"Python: Select Interpreter" → select Python 3.12 from
`AppData\Local\Programs\Python\Python312`. No code changes needed.

### Streamlit runtime rules

**Never write directly to session state keys bound to rendered widgets.**
This raises a `StreamlitAPIException` at runtime. Always use the reset-flag
pattern from Section 15 of the production standard. The pattern is:
1. Button sets `st.session_state["_reset_filters"] = True` and calls `st.rerun()`
2. A guard at the TOP of `render_sidebar()` detects the flag, deletes widget
   keys, reinitializes via `init_session_state()`, clears the flag
3. `init_session_state()` must include EVERY filter key including ALL sliders.
   A slider key missing from `init_session_state()` will not visually reset.

---

## STEP 1 -- Read the brief and confirm understanding

Read `PORTFOLIO_AGENT_BRIEF.md` in full. Then confirm:

- The three-gate process and what each gate produces
- The local build workspace structure vs. the GitHub repo structure
- The folder naming convention
- The data design rules (multi-table origin, denormalization, row count guidance)
- The SQL and Python standards
- The dashboard archetypes
- The quality gates before Git init

Do NOT start Gate 1 yet. Confirm understanding first.

---

## STEP 2 -- Gate 1: Business Questions

After understanding is confirmed, read the job description below and
produce the Gate 1 output.

### Job Description

```
[PASTE JOB DESCRIPTION HERE]
```

### Gate 1 Output Format

Produce exactly this structure. No files are created yet.

```
GATE 1 -- BUSINESS QUESTIONS
==============================
Industry:       [identified industry]
Domain:         [analytical domain this role focuses on]
Role Level:     [junior / mid / senior / lead]
Stakeholders:   [who this role presents to]
Primary Tools:  [SQL, Python, specific tools mentioned in JD]

FICTIONAL COMPANY CANDIDATE
============================
Name:           [Company Name]
Industry:       [industry]
Description:    [one sentence -- what the business does and its scale]
Analyst Frame:  As the senior data analyst at [Company Name], I have been
                asked to [specific analytical mandate derived from the JD].

BUSINESS QUESTIONS (8-11)
==========================
These questions are grounded in the industry and role. Each one connects
to a real decision the business needs to make.

Q01. [Question]
     Business problem: [what decision does this answer?]
     Analytical approach: [descriptive / diagnostic / predictive / prescriptive]
     Primary skill demonstrated: [SQL / Python / modeling / visualization]

Q02. [Question]
     Business problem: [what decision does this answer?]
     Analytical approach: [...]
     Primary skill demonstrated: [...]

[continue through Q08-Q11]

SELECT 4-6 QUESTIONS
====================
Respond with the question numbers you want to include in the project.
Example: "Q01, Q03, Q05, Q07, Q09"

The agent will proceed to Gate 2 after your selection.
```

Halt after producing Gate 1 output. Wait for Luciano to select questions.

---

## STEP 3 -- Gate 2: Schema and Data Design

After Luciano selects questions, produce the Gate 2 output.

### Gate 2 Output Format

```
GATE 2 -- SCHEMA AND DATA DESIGN
==================================
Project folder name:  [fictional-company]-[domain-action]
Full path:            C:\Users\lucia\OneDrive\Portfolio Projects\[project-name]\

FICTIONAL COMPANY (confirmed)
==============================
Name:        [Company Name]
Description: [one sentence]
Analyst frame: [one sentence -- the analytical mandate]

DATA DESIGN
============
Row count range:    [low]-[high] rows
Recommended:        [specific number with one-line rationale]
Time window:        [n] months ([start date] to [end date])
Target column:      [column name] ([binary 0/1 -- what 1 means])
Seed:               42

SOURCE TABLES ([n] tables)
===========================
These tables reflect how data actually lives in a real [industry] system.
They are joined into one denormalized analysis-ready CSV.
Source table files live in _build/tools/raw_tables/ and are gitignored.
The schema (ERD + table definitions) is committed to GitHub.

Table 1: [table_name]
  Grain:   [what one row represents]
  Rows:    ~[count]
  Key columns: [col1], [col2], [col3]
  Joins to: [table_name] on [key]

Table 2: [table_name]
  Grain:   [what one row represents]
  Rows:    ~[count]
  Key columns: [col1], [col2], [col3]
  Joins to: [table_name] on [key]

[continue for all tables]

DENORMALIZED CSV: [project].csv
================================
Final column list (all columns in the analysis-ready CSV):
[list every column with type and brief description]

Leakage-prone columns (documented, excluded from model training):
[list any columns that would constitute data leakage]

CONFIRM OR ADJUST
==================
Respond with one of:
  "approve"              -- proceed to Gate 3 as proposed
  "adjust [item]"        -- change a specific item then proceed
  "adjust rows [n]"      -- use a specific row count
  "adjust window [n]mo"  -- use a different time window
```

Halt after producing Gate 2 output. Wait for Luciano to approve or adjust.

---

## STEP 4 -- Gate 3: Tab Structure and Charts

After Gate 2 is approved, produce the Gate 3 output.
This is the longest gate. It produces a written spec and an HTML mockup.

### Gate 3 Output Format -- Written Spec First

```
GATE 3 -- DASHBOARD TAB STRUCTURE
====================================
Archetype:  [A -- Discovery / B -- Executive Tracker / Custom]
Rationale:  [one sentence explaining why this archetype fits the JD]

Dashboard title:    [Title]
Dashboard subtitle: [Subtitle -- company name + analytical mandate]

TAB STRUCTURE
==============

Tab 1: [Tab Name]
  Purpose: [what question does this tab answer?]
  Key Finding strip: [one-sentence description of the top insight]
  Charts:
    - [Chart name]: [type] | X: [col] | Y: [col] | Color: [logic]
      Insight: [what should the viewer conclude from this chart?]
    - [Chart name]: [type] | X: [col] | Y: [col] | Color: [logic]
      Insight: [what should the viewer conclude from this chart?]
  KPI tiles (if any): [metric names]

Tab 2: [Tab Name]
  [same structure]

[continue for all tabs -- minimum 5, maximum 7]

SIDEBAR FILTERS
================
1. [Filter name]: multiselect | values: [list]
2. [Filter name]: multiselect | values: [list]
3. [Filter name]: slider | range: [min-max]
4. [Filter name]: multiselect | values: [list]
5. [Filter name]: multiselect | values: [list]

KPI HEADER (4 cards above all tabs)
=====================================
Card 1: [metric name] | sparkline over: [dimension]
Card 2: [metric name] | sparkline over: [dimension]
Card 3: [metric name] | sparkline over: [dimension]
Card 4: [metric name] | sparkline over: [dimension]

FINANCIAL SIMULATOR (Tab: Financial Impact)
============================================
Left slider 1: [name] | range: [min-max] | default: [n] | unit: [%/$]
Left slider 2: [name] | range: [min-max] | default: [n] | unit: [%/$]
Results card shows: [list of computed outputs]
Right chart: [type] showing scenario comparison

RECOMMENDATIONS TIER STRUCTURE
================================
Immediate Actions (0-30 Days):    [2 recommendation titles]
Short-Term Actions (30-90 Days):  [2 recommendation titles]
Strategic Investments (90+ Days): [2 recommendation titles]

CROSS-INDUSTRY TRANSLATION (final tab)
========================================
Source domain:  [this project's industry]
Target industry: [industry for translation -- inferred from JD or default healthcare]
Translation signals:
  [source signal] → [target industry analogue]
  [source signal] → [target industry analogue]
  [source signal] → [target industry analogue]
Three lever cards: [lever 1 title], [lever 2 title], [lever 3 title]

APPROVE SPEC OR ADJUST
=======================
Respond with one of:
  "approve spec"         -- generate HTML mockup then proceed to Gate 3 final
  "adjust [tab] [item]"  -- modify a specific tab or chart then regenerate spec
```

Halt after the written spec. Wait for Luciano to approve the spec before
generating the HTML mockup.

### Gate 3 -- HTML Mockup

After spec is approved, generate the HTML mockup.

The mockup renders every tab vertically in one scrollable HTML file using
the exact color tokens from the production standard. Use realistic
placeholder data so chart proportions match production output.

Apply every rule from the mockup review checklist:
- Every x-axis label is horizontal (tickangle=0)
- No data label clips the axis edge -- y-axis extends 25-30% beyond max value
- Every paired chart row has a vertical dashed steel separator
- Every label uses human-readable Title Case, never raw column names
- Confusion matrix uses NAVY / STEEL_700 scheme, not RED_SOFT
- Every confusion matrix has a "So what" interpretation strip
- Every recommendation card body is a bulleted list
- Tables have 0.5px steel gridlines on every cell
- Financial Impact downstream charts respond to simulator state

After mockup is generated:

```
GATE 3 FINAL -- APPROVAL
==========================
Written spec: [approved date]
HTML mockup:  [generated]

PATTERN_LOG.md will be written with all approved tabs and charts.
PROJECT_MANIFEST.json will be written with full project spec.
CLAUDE_CODE_KICKOFF_PROMPT.md build instructions will be written.
Folder structure will be created at:
  C:\Users\lucia\OneDrive\Portfolio Projects\[project-name]\

Respond with one of:
  "approved -- build"    -- write all files and create folders
  "adjust mockup [item]" -- modify a specific element then re-approve
```

Halt after mockup. Wait for final approval before creating any files or folders.

---

## STEP 5 -- Post-Gate-3 File Creation

After "approved -- build" is received:

### 5A -- Write PATTERN_LOG.md

Document every approved tab and chart in the pattern log format from
the brief. This file stays in the project root (not gitignored) so it
can be referenced in future projects.

### 5B -- Write PROJECT_MANIFEST.json

Populate every field from the brief template. No PLACEHOLDER values
except Streamlit URLs (require deployment) and GitHub description
(confirm with Luciano after README is written).

### 5C -- Create folder structure

Create the full local build workspace at:
`C:\Users\lucia\OneDrive\Portfolio Projects\[project-name]\`

```
[project-name]/
├── PROJECT_BRIEF.md              (written in this step)
├── CLAUDE_CODE_KICKOFF_PROMPT.md (this file -- copied to project folder)
├── PATTERN_LOG.md                (written in 5A)
├── PROJECT_MANIFEST.json         (written in 5B)
├── _build/
│   ├── workflows/
│   │   ├── 01_data_model/
│   │   │   ├── ddl/
│   │   │   ├── erd/
│   │   │   └── docs/
│   │   ├── 02_data_generation/
│   │   │   ├── generators/
│   │   │   ├── config/
│   │   │   └── outputs/
│   │   ├── 03_sql_analysis/
│   │   │   └── [one subfolder per approved business question]
│   │   └── 04_modeling/
│   │       ├── eda/
│   │       ├── modeling/
│   │       └── outputs/
│   ├── agents/
│   └── tools/
│       ├── raw_tables/
│       └── reference/
```

Every folder gets a `README.md` with:
- The folder's purpose (one sentence)
- What files will live here when complete
- Which phase populates it

### 5D -- Write PROJECT_BRIEF.md

Write the full project brief into the project folder. This is the
contract document for the build phases. Structure:

```markdown
# [Project Name] -- Project Brief
**Company:** [Fictional Company Name]
**Role Target:** [Job Title]
**Author:** Luciano Casillas
**Date:** [date]
**Project Path:** C:\Users\lucia\OneDrive\Portfolio Projects\[project-name]

## 1. Business Context
[Company description and analytical mandate -- 2 paragraphs]

## 2. Approved Business Questions
[numbered list of the 4-6 approved questions with business problem each solves]

## 3. Data Design
[row count, time window, seed, target column, source table descriptions]

## 4. Source Table Schema
[one section per source table: grain, key columns, join keys]

## 5. Denormalized CSV Column Reference
[full column list with types and descriptions]

## 6. Dashboard Spec
[archetype, tab structure, KPI header, sidebar filters -- from Gate 3]

## 7. Simulation Parameters
[YAML block with all data generation parameters]

## 8. WAT Folder Structure
[the full local build structure]

## 9. GitHub Repo Structure
[the production standard GitHub structure]

## 10. Phase Roadmap
[Phase 1 through Phase 7 with what each produces]
```

### 5E -- Report folder creation

```
STEP 5 COMPLETE -- FOLDER STRUCTURE CREATED
=============================================
Project:    [project-name]
Path:       C:\Users\lucia\OneDrive\Portfolio Projects\[project-name]\
Files written:
  - PROJECT_BRIEF.md
  - PATTERN_LOG.md
  - PROJECT_MANIFEST.json
  [list all folders created]

Ready to proceed to Phase build.
Open PORTFOLIO_AGENT_PHASES.md in a new Claude Code session and paste
the Phase 1 trigger to begin building.

Or say "proceed to Phase 1" here to begin immediately.
```

---

## FUTURE PHASE TRIGGERS

After Gate 3 is approved and the folder structure is created, the build
phases run from `PORTFOLIO_AGENT_PHASES.md`. Use these triggers:

```
"proceed to Phase 1"  -- data model: DDL, ERD, data dictionary, seed files
"proceed to Phase 2"  -- data generation: source tables + denormalized CSV
"proceed to Phase 3"  -- SQL analysis: all business question queries
"proceed to Phase 4"  -- Python notebook: EDA, modeling, SHAP
"proceed to Phase 5"  -- Streamlit dashboard: app.py + benchmarking_app.py
"proceed to Phase 6"  -- documentation: README, PROJECT_OVERVIEW.md,
                         INTERVIEW_PREP.md, portfolio_page.html
"proceed to Phase 7"  -- Git init: transform build folder, promote GitHub
                         files to root, write .gitignore, quality gates
```

Each phase trigger can also be used to resume if a session ends:
```
"resume Phase 3 -- [last file completed]"
```

---

## VERIFICATION GATE (runs before Phase 7)

Before the Git init transformation, verify:

```python
import ast, pandas as pd, json

# 1. app.py syntax
ast.parse(open("_build/workflows/04_modeling/app.py").read())

# 2. No em dashes
assert open("_build/workflows/04_modeling/app.py").read().count("\u2014") == 0

# 3. No RED_700
assert "RED_700" not in open("_build/workflows/04_modeling/app.py").read()

# 4. base_layout exactly 5 keys (see production standard section 22)

# 5. Decile descending
assert 'pd.qcut(-' in open("_build/workflows/04_modeling/app.py").read()

# 6. Dataset clean
df = pd.read_csv("_build/workflows/02_data_generation/outputs/[project].csv")
assert df.isnull().sum().sum() == 0

# 7. Manifest complete
manifest = json.load(open("PROJECT_MANIFEST.json"))
# No PLACEHOLDER values except streamlit_urls and github_settings.description
```

Report results before Phase 7 proceeds.

---

*Kickoff prompt version 1.0 -- Luciano Casillas portfolio system*
