# AICamp: Zeitreihen und Spektren

Dieses Repository enthält die Notebooks und Skripte zum Zeitreihen- und Spektren-Workshop.

## 1. Repository herunterladen

Es gibt mehrere Möglichkeiten, an den Code zu gelangen.

### Option A: Mit Git (empfohlen, z.B. für VS Code)

```bash
git clone git@github.com:pertlnadja/aicamp.git
cd aicamp
```

Danach den Ordner in VS Code öffnen (`Datei > Ordner öffnen...`), idealerweise mit installierter **Python-Extension** und **Jupyter-Extension** (VS Code schlägt diese beim Öffnen eines `.ipynb`-Files meist automatisch vor).

### Option B: Als ZIP herunterladen

Falls Git nicht zur Verfügung steht:

1. Auf der Repo-Seite auf **"Code" → "Download ZIP"** klicken
2. ZIP an einem beliebigen Ort entpacken
3. Den entpackten Ordner in VS Code oder Jupyter öffnen

### Option C: Google Colab

Colab kann Notebooks direkt aus GitHub öffnen (**Datei → Notebook öffnen → GitHub**, dann Repo-URL einfügen).

## 2. Umgebung einrichten

Vorausgesetzt: **Python 3.10+** ist installiert.

### Virtuelle Umgebung anlegen und aktivieren

**Mit `venv`:**
```bash
python -m venv .venv
```
Aktivieren: `.venv\Scripts\Activate.ps1` (Windows) oder `source .venv/bin/activate` (macOS/Linux)

**Mit `uv`:**
```bash
uv venv
```
Aktivieren wie oben, oder Befehle direkt mit `uv run ...` ausführen.

**Mit `conda`:**
```bash
conda create -n zeitreihen-workshop python=3.11
conda activate zeitreihen-workshop
```

### Abhängigkeiten installieren

```bash
uv sync
```

Das installiert alle in `pyproject.toml` definierten Abhängigkeiten in die (bei Bedarf automatisch erstellte) virtuelle Umgebung.

Ohne `uv`, mit `pip`:

```bash
pip install .
```

## 3. Notebook starten

Mit aktivierter Umgebung im Projektordner:

```bash
jupyter notebook
```

Es öffnet sich der Jupyter-Browser – dort das gewünschte Notebook (z.B. `workshop/data_exploration.ipynb`) anklicken.

**Alternative:** In VS Code das `.ipynb`-File direkt öffnen und oben rechts den passenden Python-Kernel (die gerade erstellte `.venv`) auswählen – Zellen lassen sich dann direkt in VS Code ausführen, ganz ohne separaten Browser-Tab.

## 4. Notebook ausführen

- Zellen der Reihe nach mit **Umschalt+Enter** ausführen
- Bei Fragen/Problemen während des Workshops: einfach melden!

## 5. Streamlit-App starten

Streamlit-Apps lassen sich wie folgt mit der aktivierten Umgebung starten.
Im jeweiligen Ordner:

```bash
pip install streamlit
streamlit run app.py
```

Streamlit öffnet die App automatisch im Standard-Browser (üblicherweise unter
`http://localhost:8501`). Falls sich kein Fenster öffnet, kann die angezeigte URL aus dem
Terminal manuell im Browser aufgerufen werden.

Zum Beenden: im Terminal **Strg+C** drücken.