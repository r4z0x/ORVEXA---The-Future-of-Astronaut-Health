# ORVEXA — Astronaut Health Monitoring Prototype

Current version: **1.1.0**. See `CHANGELOG.md` for fixes and verification notes.

ORVEXA is a native desktop application built with **Python and PySide6 (Qt)** for **Windows and Linux**. It runs in its own application window; no browser or web server is required.

## Quick Start

Requirements: 64-bit Windows 10/11 or a modern Linux desktop environment, and **Python 3.10–3.13**. Python 3.12 is recommended. Python 3.14+ is not supported by the pinned Qt version.

Extract the entire archive to a writable folder. Do not run files directly from the ZIP archive.

### Windows

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/ and enable **Add python.exe to PATH**.
2. Open PowerShell in the project folder and run:

   ```powershell
   py -3.11 launch.py
   ```

   You may use `py -3.12 launch.py` if Python 3.12 is installed.
3. On first launch, `launch.py` creates `.venv` and installs Qt. An internet connection is required for the initial dependency installation.

### Linux

From the extracted project folder, run:

```bash
python3.12 launch.py
```

`launch.py` creates `.venv`, installs Qt, and starts the application. A graphical X11 or Wayland session is required; a headless server cannot display the application window.

On Ubuntu/Debian, install these system packages if `venv` or Qt libraries are missing:

```bash
sudo apt install python3-venv libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0
```

### Manual Launch

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## Features

- Dark, space-inspired desktop interface with Mission Overview, Health Metrics, AI Assistant, Workouts, Reports, and Settings.
- Manual entry of resting heart rate, SpO₂, temperature, sleep duration, fatigue, baseline heart rate, and reported symptoms.
- Charts for saved measurements across 24 hours, 7 days, and 30 days, preserving actual time intervals. Before the first manual entry, clearly labeled sample data is displayed. Empty periods are shown without invented measurements.
- AI analysis and chat through the **OpenAI API** or a **local Ollama** model.
- AI-generated draft workout plans using ARED, CEVIS, and mobility exercises suitable for a microgravity context.
- Workout timer, pause, next-exercise controls, and saving of complete or partial sessions. The log records actual timer duration.
- Local SQLite database, persistent history, and JSON/CSV export.
- Paginated history (200 records per page); full export includes the entire database. Large charts retain peaks and troughs when display points are reduced.
- Settings and chat drafts are preserved while navigating and waiting for responses. Up to 8 recent chat messages are included as context.


## NASA Science sourses

NASA Research References
ORVEXA is designed around astronaut health monitoring concepts and physiological considerations relevant to human spaceflight. The project’s health indicators, recovery monitoring concepts, and exercise-related features are aligned with research and publicly available educational resources from NASA.

The following NASA resources provide scientific and operational context for the project:

1. NASA Human Research Program (HRP)
https://humanresearchroadmap.nasa.gov/evidence/

NASA’s Human Research Program documents health and performance risks associated with human spaceflight, including cardiovascular changes, sleep loss, fatigue, bone health, and reduced physical performance. These research areas are relevant to ORVEXA’s health monitoring categories.

2. NASA Open Science Data Repository (OSDR)
https://osdr.nasa.gov/

NASA’s Open Science Data Repository provides access to spaceflight-related biological, physiological, behavioral, and other research datasets. It represents a potential source for future research-based data integration and validation of ORVEXA.

3. NASA — Astronaut Exercise
https://www.nasa.gov/missions/station/iss-research/astronaut-exercise/

This resource describes exercise countermeasures used aboard the International Space Station, including the Advanced Resistive Exercise Device (ARED) and Cycle Ergometer with Vibration Isolation and Stabilization (CEVIS). These systems provide context for ORVEXA’s microgravity-oriented workout concepts.

4. NASA — Human System Risks
https://www.nasa.gov/hhp/human-system-risks/

NASA’s overview of human-system risks provides additional context on health and performance challenges during spaceflight, including cardiovascular, musculoskeletal, behavioral health, and sleep-related risks.

Data and Implementation Note
ORVEXA is an independent research prototype. It does not directly connect to NASA systems, onboard spacecraft sensors, or live astronaut health databases. All measurements are entered manually by the user and stored locally on the computer.

NASA resources listed above are provided as scientific and operational references. The current prototype does not automatically download or process NASA OSDR datasets. Future versions may explore integration with publicly available spaceflight research datasets.


## AI Setup

Both AI providers are supported. Until a model is connected, analysis opens Settings. The built-in workout plan is explicitly labeled as a **Sample Plan** and is not presented as an AI result.

### OpenAI

Open **Settings → AI Connection**:

1. Select `OpenAI`.
2. Enter an OpenAI API key with available API credit and access to the selected model.
3. The default model is `gpt-4.1-mini`. You may enter another Responses API model that supports JSON Schema.
4. Select **Save Connection**, return to Mission Overview, and choose **Run AI Analysis**.

API usage is billed separately from a ChatGPT subscription. The key is held in memory until the application closes; it is not written to SQLite or included in reports. Alternatively, set the `OPENAI_API_KEY` environment variable before launch. Health metrics, your question, and limited chat context are sent to OpenAI only when you request an analysis or response. Requests use `store: false`.

### Ollama — Local Model

1. Install Ollama: https://ollama.com/ .
2. Download a model. For example:

   ```bash
   ollama pull qwen2.5:7b
   ```

3. Make sure Ollama is running. If needed, start it with `ollama serve`.
4. In ORVEXA Settings, select `Ollama`, enter the installed model name (for example, `qwen2.5:7b`), and use `http://127.0.0.1:11434` as the URL.
5. Save the connection and request an analysis. You may select another installed model that supports structured output.

Downloading a model requires internet access, memory, and disk space. After download, inference through Ollama runs locally. ORVEXA accepts only Ollama addresses on the same computer.

## Data Storage

- Windows: `%LOCALAPPDATA%\ORVEXA\orvexa.sqlite3`.
- Linux: `$XDG_DATA_HOME/orvexa/orvexa.sqlite3` or `~/.local/share/orvexa/orvexa.sqlite3`.
- Set `ORVEXA_DATA_DIR` to use a custom data directory.

This is a regular local database and is not encrypted. JSON exports include profile settings, measurements, analyses, and workouts; CSV exports include measurements. The file extension determines the export format (`.json` or `.csv`). Report writes are atomic: a failed save does not truncate an existing report.

Timestamps are stored in UTC and displayed in the computer's local time. Changing the baseline heart rate does not create a new measurement or rewrite previous records. Each analysis is stored with its metric context and is not reused after the profile or measurements change.

Version 1.0 databases are upgraded automatically without deleting history. To update, extract the new version into a separate folder and keep using the existing data folder. Close the previous application before starting the new version.

The **Cancel Request** control keeps the interface usable. A request already sent may still finish on the provider's side; its result is ignored after cancellation. Changes to measurements or model settings also prevent an outdated response from overwriting the current state.

## Prototype Limitations and Safety

No sensors or spacecraft systems are connected. Measurements are entered manually. The expedition information in the banner is illustrative sample content.

ORVEXA is a research prototype, not a medical device. It does not diagnose conditions or clear anyone for exercise. When symptoms or configured alert values are present, the workout plan is paused pending review by the mission medical officer. Demonstration thresholds do not replace mission clinical protocols. Resistance, intensity, and technique for real exercise must be approved by qualified medical and exercise specialists.

The project is Python source code, **not a packaged `.exe`**. This archive does not include BAT or SH launch scripts; start the application with the Python command shown above. The application and Qt were tested on Linux; Windows execution was not available in the original verification environment. Live requests to OpenAI/Ollama require your API key or a running local model and were not verified without those credentials/services; provider adapters were tested with a controlled local test server.

## Tests

After installing dependencies, run:

```bash
python -m unittest discover -v
```

Tests cover validation, exercise guardrails, both AI adapters, HTTP communication with a local test server, incomplete responses and network errors, database migration, field drafts, request cancellation, timers, partial workouts, atomic export, the launcher, and large data sets. GUI tests use Qt offscreen and do not require a visible desktop.

## Project Structure

```text
main.py                 QApplication entry point
launch.py               Environment setup and launcher
orvexa/ui.py            Main window and application views
orvexa/widgets.py       Native cards, charts, and hero banner
orvexa/dialogs.py       Measurement entry and workout dialogs
orvexa/domain.py        Data models, validation, and guardrails
orvexa/ai.py            OpenAI Responses API and Ollama clients
orvexa/storage.py       SQLite storage and export
orvexa/charts.py        Chart downsampling that preserves extremes
orvexa/reports.py       Atomic JSON/CSV report writing
tests/                  Logic and interface tests
```

Earth image credit: NASA via Unsplash, photo-1446776811953-b23d57bd21aa. Golos Text is distributed under the SIL Open Font License; see `assets/FONT-LICENSE.txt`.

