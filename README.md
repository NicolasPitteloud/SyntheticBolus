# Synthetic Bolus Web Application

Directly integrate an **RT bolus structure** into a CT dataset.

This web app modifies **HU values** in the CT pixel array using a bolus structure from an **RT Structure Set**. This allows the **Ethos Management Platform** to handle external bolus seamlessly.

---

## Features
- Cross-platform: **Linux · macOS · Windows**
- Direct HU editing of the CT array
- Full DICOM viewer for analysis
- Detailed help inside web browser
- config.py file with editable parameters

---

## How It Works
1. Load CT series and RT Structure Set.
2. Extract the bolus structure contours and convert to mask.
3. Overwrite CT pixel array HU values within the bolus mask (to the configured bolus HU in /utils/config.py).
4. Generate a new synthetic CT registered to the original CT, with new DICOM tags.

## ⚠️ Medical Use Disclaimer ⚠️

This software is provided **for research and educational purposes only**.
It is **not intended for direct clinical use** without independent validation and approval within your institution.

The author assumes **no responsibility or liability** for any outcome resulting from the use of this software, including (but not limited to) injury, treatment errors, or data corruption.

Users are solely responsible for:
- Verifying outputs against ground truth and clinical standards
- Performing QA in line with institutional and regulatory requirements
- Ensuring compliance with local laws and medical device regulations

---

## Requirements
- **Python 3.9+** (may work with earlier versions)

---

## Installation

```bash
# 1) Clone
git clone https://github.com/NicolasPitteloud/SyntheticBolus.git
cd SyntheticBolus

# 2) Create a virtual environment
python -m venv .venv

# 3) Activate the virtual environment
# Linux / macOS (bash/zsh):
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat

# 4) Install backend dependencies
pip install -r backend/requirements.txt

# 5) Run the application with:
python app.py
