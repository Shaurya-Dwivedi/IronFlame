import os
import sys
import json
import ctypes
from ctypes import wintypes
from dotenv import load_dotenv
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QObject, Signal, QThread, QRect, QFileSystemWatcher
from pynput import keyboard

# Load dotenv to get GEMINI_API_KEY
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Import local components
from overlay_ui import SelectionOverlay, SolutionOverlay
from solvers.gemini import GeminiSolver

# --- Win32 API Constants and Prototypes ---
user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long

user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long

user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, 
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, 
    wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL


def apply_display_affinity(hwnd: int):
    """Sets the window to exclude from screen capture (GDI/WGC/OBS/Discord)."""
    if hwnd:
        success = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        return success
    return False


def apply_click_through(hwnd: int, enabled: bool):
    """Toggles WS_EX_TRANSPARENT window style to allow/block clicks, keeping WS_EX_NOACTIVATE."""
    if not hwnd:
        return
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    
    # Always keep WS_EX_NOACTIVATE style to prevent focus steal
    style |= WS_EX_NOACTIVATE
    
    if enabled:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    # Force style update immediately
    user32.SetWindowPos(
        hwnd, None, 0, 0, 0, 0, 
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
    )


# --- Thread-Safe Keyboard Hotkey Signal Emitter ---
class HotkeyEmitter(QObject):
    """Emits Qt signals when global hotkeys are pressed by pynput's listener thread."""
    solve_region = Signal()
    solve_fullscreen = Signal()
    toggle_visibility = Signal()
    toggle_interactive = Signal()
    copy_code = Signal()
    history_prev = Signal()
    history_next = Signal()
    clear = Signal()
    quit_app = Signal()


# --- Worker Thread for Multimodal Streaming ---
class SolverWorkerThread(QThread):
    """Communicates with the AI Solver backend in a non-blocking background thread."""
    chunk_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, solver: GeminiSolver, screenshot_path: str, user_prompt: str = ""):
        super().__init__()
        self.solver = solver
        self.screenshot_path = screenshot_path
        self.user_prompt = user_prompt

    def run(self):
        try:
            # Yield chunks from Gemini streaming generator
            generator = self.solver.solve_screenshot_stream(self.screenshot_path, self.user_prompt)
            for chunk in generator:
                if chunk:
                    self.chunk_received.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# --- Main Application Controller ---
class StealthOverlayApp(QObject):
    """Controls the lifecycle, window states, settings, and hotkeys of the overlay app."""

    def __init__(self, config_path: str):
        super().__init__()
        self.config_path = config_path
        self.load_config()

        # Initialize emitter and solver
        self.hotkey_emitter = HotkeyEmitter()
        self.solver = GeminiSolver(model_name=self.config["gemini_model"])

        # Setup main Solution Overlay UI
        ui_cfg = self.config["ui"]
        self.solution_overlay = SolutionOverlay(
            width=ui_cfg["width"],
            height=ui_cfg["height"],
            default_opacity=ui_cfg["opacity"],
            font_size=ui_cfg["font_size"]
        )
        
        # Initial positioning on the right side of primary monitor
        screen_geo = QtGui.QGuiApplication.primaryScreen().geometry()
        x = screen_geo.width() - ui_cfg["width"] - 30
        y = (screen_geo.height() - ui_cfg["height"]) // 2
        self.solution_overlay.move(x, y)

        # Hook Display Affinity update triggers
        self.solution_overlay.showEvent = self.on_overlay_show
        
        # Keep references to active worker threads/selection widgets
        self.worker_thread = None
        self.selection_window = None
        
        # Connect hotkey emitter signals to handler slots
        self.connect_signals()
        
        # Show solution overlay window and apply initial state
        self.solution_overlay.show()
        self.set_stealth_mode(True) # Start in click-through by default

        # Set up hotkey listener
        self.hotkey_listener = None
        self.setup_hotkeys()

        # Set up Config Watcher for live hot-reloading
        self.config_watcher = QFileSystemWatcher([self.config_path])
        self.config_watcher.fileChanged.connect(self.on_config_changed)

    def load_config(self):
        """Reads configuration from config.json."""
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}. Loading defaults.")
            self.config = {
                "gemini_model": "gemini-2.5-flash",
                "capture_monitor": 0,
                "hotkeys": {
                    "solve_region": "<ctrl>+<alt>+s",
                    "solve_fullscreen": "<ctrl>+<alt>+f",
                    "toggle_visibility": "<ctrl>+<alt>+h",
                    "toggle_interactive": "<ctrl>+<alt>+i",
                    "copy_code": "<ctrl>+<alt>+c",
                    "history_prev": "<ctrl>+<alt>+[",
                    "history_next": "<ctrl>+<alt>+]",
                    "clear": "<ctrl>+<alt>+l",
                    "quit": "<ctrl>+<alt>+q"
                },
                "ui": {
                    "width": 450,
                    "height": 650,
                    "opacity": 0.85,
                    "font_size": 13,
                    "theme": "glassmorphic_dark"
                }
            }

    def connect_signals(self):
        """Maps Qt signals to controller actions."""
        self.hotkey_emitter.solve_region.connect(self.trigger_region_capture)
        self.hotkey_emitter.solve_fullscreen.connect(self.trigger_fullscreen_capture)
        self.hotkey_emitter.toggle_visibility.connect(self.toggle_overlay_visibility)
        self.hotkey_emitter.toggle_interactive.connect(self.toggle_interactive_mode)
        self.hotkey_emitter.copy_code.connect(self.copy_code_block)
        self.hotkey_emitter.history_prev.connect(lambda: self.solution_overlay.cycle_history(-1))
        self.hotkey_emitter.history_next.connect(lambda: self.solution_overlay.cycle_history(1))
        self.hotkey_emitter.clear.connect(self.solution_overlay.clear_overlay)
        self.hotkey_emitter.quit_app.connect(self.quit_application)

    def on_overlay_show(self, event):
        """Event hook called when overlay is rendered. Sets initial Windows display affinity."""
        self.solution_overlay.apply_display_affinity()
        # Override paint events to re-apply affinity continuously
        self.solution_overlay.focusInEvent = lambda e: self.reapply_wda()
        self.solution_overlay.changeEvent = lambda e: self.on_state_change(e)

    def reapply_wda(self):
        """Robust method to ensure the overlay remains excluded from capture."""
        apply_display_affinity(int(self.solution_overlay.winId()))

    def on_state_change(self, event):
        """Triggers WDA check on window changes."""
        if event.type() in [QtCore.QEvent.Type.WindowStateChange, QtCore.QEvent.Type.ActivationChange]:
            self.reapply_wda()

    def set_stealth_mode(self, stealth: bool):
        """Toggles between click-through state (stealth) and interactive mode."""
        self.solution_overlay.update_interactive_style(not stealth)
        apply_click_through(int(self.solution_overlay.winId()), stealth)

    def toggle_interactive_mode(self):
        """Flips current interaction state."""
        new_stealth = not self.solution_overlay.is_interactive
        self.set_stealth_mode(new_stealth)

    def toggle_overlay_visibility(self):
        """Instantly shows/hides the overlay window (boss key)."""
        if self.solution_overlay.isVisible():
            self.solution_overlay.hide()
        else:
            self.solution_overlay.show()
            self.reapply_wda()

    def copy_code_block(self):
        """Triggers copy code on overlay."""
        self.solution_overlay.copy_code_to_clipboard()

    # ------------------ Capture and Solver Pipeline ------------------
    def trigger_region_capture(self):
        """Hides the overlay, presents selection screen, and grabs screen area."""
        # 1. Temporarily hide solution overlay to prevent self-capture
        self.solution_overlay.hide()
        
        # 2. Get target monitor geometry
        monitor_idx = self.config.get("capture_monitor", 0)
        screens = QtGui.QGuiApplication.screens()
        
        if 0 < monitor_idx <= len(screens):
            screen = screens[monitor_idx - 1]
        else:
            screen = QtGui.QGuiApplication.primaryScreen()
            
        geometry = screen.geometry()
        
        # Create full-screen drag selection window
        self.selection_window = SelectionOverlay(geometry)
        self.selection_window.region_selected.connect(self.on_region_selected)
        # Show solution overlay again if they cancel
        self.selection_window.destroyed.connect(lambda: self.solution_overlay.show() if not self.solution_overlay.isVisible() else None)
        
        self.selection_window.show()

    def on_region_selected(self, rect: QRect):
        """Saves selected region image to temp and spins up solver worker thread."""
        self.solution_overlay.show()
        self.reapply_wda()
        
        self.solution_overlay.start_loading("REGION")

        # Capture using mss
        import mss
        import mss.tools
        
        # Prepare output path
        temp_dir = os.path.join(BASE_DIR, "scratch")
        os.makedirs(temp_dir, exist_ok=True)
        screenshot_path = os.path.join(temp_dir, "region_solve.png")

        try:
            with mss.mss() as sct:
                # Capture exact coordinates
                monitor = {
                    "top": rect.y(),
                    "left": rect.x(),
                    "width": rect.width(),
                    "height": rect.height()
                }
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=screenshot_path)
                
            self.start_solver_thread(screenshot_path)
        except Exception as e:
            self.on_solver_error(f"Region screenshot capture failed: {e}")

    def trigger_fullscreen_capture(self):
        """Hides overlay, captures entire configured monitor, and starts solver."""
        self.solution_overlay.hide()
        
        # Small sleep to ensure window is completely hidden from graphics buffer
        QtCore.QTimer.singleShot(100, self.perform_fullscreen_capture)

    def perform_fullscreen_capture(self):
        self.solution_overlay.show()
        self.reapply_wda()
        self.solution_overlay.start_loading("SCREEN")

        import mss
        import mss.tools
        
        temp_dir = os.path.join(BASE_DIR, "scratch")
        os.makedirs(temp_dir, exist_ok=True)
        screenshot_path = os.path.join(temp_dir, "fullscreen_solve.png")

        try:
            monitor_idx = self.config.get("capture_monitor", 0)
            with mss.mss() as sct:
                # mss index 0 = all monitors combined, 1 = monitor 1, 2 = monitor 2
                # Convert config index (0-based) to mss index (1-based)
                mss_idx = monitor_idx + 1 if monitor_idx < len(sct.monitors) - 1 else 1
                monitor = sct.monitors[mss_idx]
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=screenshot_path)
                
            self.start_solver_thread(screenshot_path)
        except Exception as e:
            self.on_solver_error(f"Fullscreen screenshot capture failed: {e}")

    def start_solver_thread(self, screenshot_path: str):
        """Spins up a QThread to handle the streaming solver."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()

        # Instantiate worker
        self.worker_thread = SolverWorkerThread(self.solver, screenshot_path)
        
        # Connect signals
        # The first token replaces loading placeholder, subsequent tokens append
        self.first_token = True
        self.worker_thread.chunk_received.connect(self.on_token_received)
        self.worker_thread.finished.connect(self.on_solver_finished)
        self.worker_thread.error.connect(self.on_solver_error)
        
        self.worker_thread.start()

    def on_token_received(self, chunk: str):
        if self.first_token:
            # First write clears the "Solving..." screen state
            self.solution_overlay.summary_browser.clear()
            self.first_token = False
        self.solution_overlay.append_stream_chunk(chunk)

    def on_solver_finished(self):
        self.solution_overlay.finish_loading()

    def on_solver_error(self, err_msg: str):
        self.solution_overlay.progress_bar.setVisible(False)
        self.solution_overlay.title_label.setText("SOLVER ERROR")
        self.solution_overlay.summary_browser.setHtml(f"<span style='color: #F87171;'><b>Error:</b> {err_msg}</span>")

    # ------------------ Hotkeys and Listener management ------------------
    def setup_hotkeys(self):
        """Initializes and starts the pynput global keyboard hook thread."""
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        hk = self.config["hotkeys"]
        
        # Maps the pynput triggers to emitter triggers (cross-thread safe)
        hotkey_bindings = {
            hk["solve_region"]: lambda: self.hotkey_emitter.solve_region.emit(),
            hk["solve_fullscreen"]: lambda: self.hotkey_emitter.solve_fullscreen.emit(),
            hk["toggle_visibility"]: lambda: self.hotkey_emitter.toggle_visibility.emit(),
            hk["toggle_interactive"]: lambda: self.hotkey_emitter.toggle_interactive.emit(),
            hk["copy_code"]: lambda: self.hotkey_emitter.copy_code.emit(),
            hk["history_prev"]: lambda: self.hotkey_emitter.history_prev.emit(),
            hk["history_next"]: lambda: self.hotkey_emitter.history_next.emit(),
            hk["clear"]: lambda: self.hotkey_emitter.clear.emit(),
            hk["quit"]: lambda: self.hotkey_emitter.quit_app.emit()
        }

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_bindings)
            self.hotkey_listener.start()
        except Exception as e:
            print(f"Failed to bind hotkeys: {e}")

    def on_config_changed(self, path: str):
        """Fires when config.json is saved. Automatically re-applies changes."""
        print("config.json modified, reloading...")
        # Avoid reloading too fast (file lock issues in Windows)
        QtCore.QTimer.singleShot(200, self.reload_config)

    def reload_config(self):
        self.load_config()
        # Update solver model
        self.solver.model_name = self.config["gemini_model"]
        # Update UI dimensions/opacity/font sizes
        self.solution_overlay.update_ui_config(self.config["ui"])
        # Update Hotkeys
        self.setup_hotkeys()

    def quit_application(self):
        """Properly exits threads and shuts down the QApplication."""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
        
        QtWidgets.QApplication.quit()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Hide from taskbar window property at application level
    app.setQuitOnLastWindowClosed(True)
    
    config_file = os.path.join(BASE_DIR, "config.json")
    
    # Check if API Key is set, warn if not
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARNING] GEMINI_API_KEY environment variable is missing. Set it in .env file.")
        
    controller = StealthOverlayApp(config_file)
    sys.exit(app.exec())
