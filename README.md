# IronFlame: Stealth Programming Assistant Screen Overlay

![OS: Windows](https://img.shields.io/badge/OS-Windows_10%2F11-0078D4?style=flat-square&logo=windows&logoColor=white)
![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![UI: PySide6](https://img.shields.io/badge/UI-PySide6-41CD52?style=flat-square&logo=qt&logoColor=white)
![API: Gemini](https://img.shields.io/badge/API-Gemini_3.x-8E75C2?style=flat-square&logo=google-gemini&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen?style=flat-square)

An enterprise-grade, high-performance programming companion overlay window designed for live-coding sessions, technical interviews, and hackathons. 

Using native Windows APIs, the overlay window is completely excluded from desktop graphics capture streams. While remaining fully visible on your physical monitor, it appears transparent (invisible) to anyone viewing your screen share on Zoom, MS Teams, Discord, OBS, or screen-recording software.

> [!IMPORTANT]
> **Windows Security Notice**:
> Capture exclusion requires Windows 10 (version 2004 / Build 19041) or Windows 11. It utilizes native OS-level buffers to omit the window graphics from screen capture APIs.

---

## Core Capabilities

*   **Display Capture Exclusion (Win32 Affinity)**: Employs `SetWindowDisplayAffinity` (`WDA_EXCLUDEFROMCAPTURE`) to ensure the solution window does not appear on screenshots, video recordings, or screen shares.
*   **Focus Bypass & Proctor Immunity**: Combines `WS_EX_NOACTIVATE` (Win32 extended style) and `WindowDoesNotAcceptFocus` (Qt window flag). The overlay window never steals active focus, bypassing focus-switching trackers used by proctoring software.
*   **Real-time Streaming Engine**: Incorporates the official `google-genai` client running inside an asynchronous background `QThread` to stream markdown text tokens in real time.
*   **Multi-Model Failover Protocol**: Automatically falls back through multiple high-performance Gemini models (`gemini-3.1-flash-lite` -> `gemini-3.5-flash` -> `gemini-3-flash` -> `gemini-2.5-flash`) to bypass 429 rate limits seamlessly.
*   **Interactive vs. Click-Through States**: Toggle between **Stealth Mode** (mouse clicks pass right through the window directly to your editor/IDE) and **Edit Mode** (drag, scroll, copy text, or resize).
*   **Pygments Syntax Highlighting**: Lightweight HTML syntax highlighting for Python, C++, Java, JS, Go, Rust, and SQL, matching the popular Monokai dark palette.
*   **Hot-Reloading Configuration**: Integrates `QFileSystemWatcher` to live-reload hotkey binds, themes, font sizes, and opacity values instantly when `config.json` is saved.
*   **Zero-Focus Fullscreen Capture**: Takes snapshots of target displays in the background using `mss`, without flashing windows or stealing keyboard inputs.

---

## Directory Structure

```
proud-bardeen/
│
├── .env                  # Secure local file for GEMINI_API_KEY
├── config.json           # Styling, capture monitor, and hotkey bindings
├── stealth_app.py        # Application entry point & controller
├── overlay_ui.py         # Translucent window GUI & region capture overlays
├── build_stealth.py      # Automated PyInstaller compilation script
│
├── solvers/
│   ├── __init__.py       # Package initialization
│   ├── base.py           # BaseSolver abstract class interface
│   └── gemini.py         # Multi-model fallback solver implementation
│
└── dist/                 # Standalone build distribution directory
    ├── DesktopWindowHelper.exe
    ├── config.json
    └── .env
```

---

## Hotkey Mappings
Can be customized under `config.json` (keys are hot-reloaded dynamically on save):

| Event | Hotkey | Action |
| :--- | :--- | :--- |
| **Solve Region** | `Ctrl + Alt + S` | Dim screen and drag-select a specific region to solve. |
| **Solve Fullscreen** | `Ctrl + Alt + F` | Capture entire screen and solve without losing editor focus. |
| **Toggle Visibility** | `Ctrl + Alt + H` | Boss Key: Instantly hide/show the solution panel. |
| **Toggle Interaction** | `Ctrl + Alt + I` | Switch between Click-Through (Stealth) and Mouse-Capture (Edit). |
| **Copy Code** | `Ctrl + Alt + C` | Extract and copy the first code block to clipboard. |
| **History Cycle** | `Ctrl + Alt + [` / `]` | Move backward/forward through the last 5 questions in-memory. |
| **Clear Display** | `Ctrl + Alt + L` | Flush current overlay screen and clear the history slot. |
| **Quit App** | `Ctrl + Alt + Q` | Close the background listeners and shut down cleanly. |
| **Set Opacity** | `Ctrl + ScrollWheel` | Adjust panel transparency on the fly. |

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Windows 10 (version 2004 / Build 19041) or Windows 11

### Step 1: Install Dependencies
Run the following command in your terminal to install the necessary packages:
```bash
pip install PySide6 pynput pillow mss google-genai pygments python-dotenv pyinstaller
```

### Step 2: Configure Environment Variables
Create a file named `.env` in the root folder (or edit `dist/.env` if running the compiled version) and add your API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 3: Run the Application
Start the program directly from Python:
```bash
python stealth_app.py
```

---

## Packaging into a Standalone Binary

You can compile the overlay into a single executable that runs silently as a background process (no console window) and is named generically to look like a standard Windows service:

1. Compile the program:
   ```bash
   python build_stealth.py
   ```
2. Navigate to the `dist/` directory:
   ```bash
   cd dist/
   ```
3. Run the compiled service:
   - Double-click `DesktopWindowHelper.exe`.
   - It will run in the background. Look for `DesktopWindowHelper.exe` under "Background processes" in Windows Task Manager.

> [!TIP]
> **Code Obfuscation**:
> To prevent reverse-engineering of the Python bytecode, compile using `pyarmor` before generating the final binary:
> ```bash
> pip install pyarmor
> pyarmor pack -e " --onefile --noconsole --name=DesktopWindowHelper --collect-submodules=solvers" stealth_app.py
> ```
