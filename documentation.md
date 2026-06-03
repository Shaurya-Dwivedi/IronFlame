# IronFlame: Technical Documentation

IronFlame is an enterprise-grade, screen-share-hidden, non-focus-stealing desktop overlay application that assists developers with coding tasks. It acts as an ambient coding companion, capturing selected screen regions and streaming solutions from Gemini multimodal models directly onto a glassmorphic window overlay.

---

## 1. System Architecture

IronFlame utilizes a clean, decoupled architecture separating the front-end display container, system-level event hooks, and AI solver implementations.

### Component Map
*   **stealth_app.py (Controller)**: The main program entry point. Manages application state, initializes OS-level keyboard hooks, spawns worker threads, applies window styles, and coordinates communication.
*   **overlay_ui.py (UI Layer)**: Houses custom widgets:
    *   `SelectionOverlay`: Spans the active display with a translucent canvas, capturing screen boundaries via a drag-select box.
    *   `SolutionOverlay`: A customized, frameless window container rendering HTML styled text with a vertical splitter separation.
*   **solvers/ (AI Service Layer)**: Handles vision capturing and API processing.
    *   `BaseSolver`: Abstract interface defining multimodal interfaces.
    *   `GeminiSolver`: Concrete implementation wrapping the Google GenAI SDK.

### Multi-Threaded Execution Model
To prevent freezing the desktop interface, IronFlame runs three concurrent execution contexts:
1.  **Main UI Thread**: Runs the PySide6 event loop, rendering overlays, executing animations, and updating QSS stylesheets.
2.  **Global Keyboard Hook Thread**: Spawned by `pynput` to listen to low-level Windows keyboard messages. Translates hotkey matches to the main thread via Qt signals.
3.  **Solver Worker Thread (`QThread`)**: Spawned dynamically on each screenshot solve. Streams chunks of text asynchronously from the Gemini client, sending tokens back to the UI thread using Qt signals.

---

## 2. Advanced Stealth & Proctor Immunity

IronFlame is engineered to bypass graphic buffers and OS focus trackers, making it invisible to screen sharing and proctor tools.

### Graphics Exclusion (Capture Bypass)
The Solution Overlay utilizes the Win32 `SetWindowDisplayAffinity` API:
```python
user32.SetWindowDisplayAffinity(hwnd, 0x00000011) # WDA_EXCLUDEFROMCAPTURE
```
This forces the Desktop Window Manager (DWM) to omit the window's visual bounds when generating graphics capturing buffers for screen capture clients. Any screenshare, recording, or local screenshot tool (like OBS, Zoom, Meet, Teams) captures a transparent void in place of the window, while the user sees the window on their physical monitor.
To prevent the operating system from resetting this affinity flag during focus shifts or window state modifications, this value is re-applied inside PySide6 overrides for `focusInEvent` and `changeEvent`.

### Window Enumeration Bypass (Google Meet Window Share Hidden)
Screen sharing pickers enumerate top-level windows using `EnumWindows`. IronFlame hides itself from these lists via two methods:
1.  **Hidden Parent Window**: We instantiate a completely hidden parent widget (`dummy_parent`) and make our main overlay window a child of it. Windows excludes owned children of tool windows from alt-tab and sharing enumerations.
2.  **Caption Stripping**: Chrome's window capturer ignores visible windows that return a title text length of zero. We explicitly set the window titles of the parent and overlay to empty strings.

### Focus Loss Bypass
To bypass security filters that flag user focus loss (such as switching tabs or clicking out of a test window):
*   **No Activation Flag**: The Solution Overlay extended style is forced to include `WS_EX_NOACTIVATE` (`0x08000000`):
    ```python
    style |= WS_EX_NOACTIVATE
    ```
    This informs the OS window manager that the window should never become the active foreground window. Even if clicked or dragged, the underlying active editor or browser maintains its active focus, preventing focus-out triggers.
*   **Mouse Click-Through**: In **Stealth Mode**, the overlay extended style includes `WS_EX_TRANSPARENT` (`0x00000020`). All mouse moves, scrolls, and clicks bypass the window layer, interacting directly with the IDE or browser underneath.

---

## 3. Solver Pipeline & Multimodal Fallbacks

The AI integration layer is designed for speed, safety, and reliability.

### The Streaming Pipeline
1.  **Overlay Hide**: The UI instantly hides itself for 50 milliseconds to clear the display buffer.
2.  **Screen Capture**: `mss` grabs the configured monitor pixel dimensions or selected region coordinates, saving a temporary image in the scratch directory.
3.  **UI Restoration**: The overlay window is restored immediately (taking less than 60ms total, invisible to the eye).
4.  **Worker Spawn**: `SolverWorkerThread` starts and feeds the image to the Gemini vision models.
5.  **Streaming Output**: Raw tokens are received in real-time, parsed by a custom Pygments regex wrapper into colored HTML blocks, and rendered dynamically in the `QTextBrowser`.

### Prioritized Fallbacks
To handle strict API rate limits (such as the 20 RPD limit on standard Flash models) and 429 errors:
*   The solver operates on a fallback model array:
    `["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash"]`
*   **Sync Verification**: When connecting to the streaming endpoint, the worker evaluates the first chunk. If an authentication, validation, or rate limit exception is caught, the thread discards the connection immediately and seamlessly attempts the next model in the fallback chain without crashing the UI.

---

## 4. Configuration & Hot-Reloading

IronFlame features an active file-watcher system:
*   **QFileSystemWatcher**: Watches the local `config.json` path.
*   **Runtime Re-binding**: On save, the controller parses settings. Opacity, font sizes, dimensions, and keyboard shortcuts are updated in memory without restarting the application context.
*   **Secure Environment**: API Keys are separated into `.env`. The PyInstaller build compilation script (`build_stealth.py`) is written to preserve local `.env` and `config.json` configurations in `dist/` on rebuilds.

---

## 5. Hotkeys Reference

| Action | Config Bind | Functionality |
| :--- | :--- | :--- |
| **Region Capture** | `solve_region` | Dim screen and drag-select a specific area to solve. |
| **Fullscreen Capture** | `solve_fullscreen` | Capture the entire display buffer without focus loss. |
| **Boss Key** | `toggle_visibility` | Instantly hide/show the overlay window. |
| **Toggle Interaction** | `toggle_interactive` | Toggle between click-through and scroll/text selection. |
| **Copy Code** | `copy_code` | Parse and copy the first code block to the system clipboard. |
| **Cycle History** | `history_prev` / `history_next` | Navigate back and forth through the last 5 solves in-memory. |
| **Clear Display** | `clear` | Flush current overlay screen and clear the active history slot. |
| **Quit** | `quit` | Exit background threads and terminate processes. |
