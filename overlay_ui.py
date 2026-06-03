import re
import html
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize
from PySide6.QtGui import QColor, QPen, QPainter, QBrush, QCursor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QSplitter, QTextBrowser, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QFrame
)

# Pygments imports for code styling
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


def markdown_to_html(md_text: str) -> str:
    """
    A simple, robust Markdown parser that converts Markdown into basic HTML 
    supported natively by PySide6 QTextBrowser. Integrates Pygments for syntax highlighting.
    """
    if not md_text:
        return ""
    
    # Escape standard HTML characters first to prevent injection issues in code blocks
    # We will replace them but be careful with code blocks
    parts = md_text.split("```")
    html_output = []
    
    for idx, part in enumerate(parts):
        # Even indices are standard text, odd indices are code blocks
        if idx % 2 == 0:
            text = html.escape(part)
            # Replace headers: ### Header -> <h3>Header</h3>
            text = re.sub(r'^###\s+(.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
            text = re.sub(r'^##\s+(.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
            text = re.sub(r'^#\s+(.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
            
            # Bold: **bold** -> <b>bold</b>
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            # Italic: *italic* or _italic_ -> <i>italic</i>
            text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
            
            # Inline code: `code` -> <code style="background-color: rgba(255,255,255,0.1); padding: 2px 4px; border-radius: 3px;">code</code>
            text = re.sub(r'`(.*?)`', r'<code style="background-color: rgba(255,255,255,0.15); color: #F1F5F9; font-family: Consolas, monospace; padding: 1px 3px; border-radius: 3px;">\1</code>', text)
            
            # Bullet points: - item -> <li>item</li>
            # Handle block lists by wrapping them
            lines = text.split("\n")
            in_list = False
            for l_idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("- ") or stripped.startswith("* "):
                    content = stripped[2:]
                    lines[l_idx] = f"<li>{content}</li>"
                    if not in_list:
                        lines[l_idx] = "<ul>" + lines[l_idx]
                        in_list = True
                else:
                    if in_list:
                        lines[l_idx] = "</ul>" + line
                        in_list = False
            if in_list:
                lines.append("</ul>")
            
            text = "\n".join(lines)
            # Convert newlines to breaks, except around list elements
            text = text.replace("\n", "<br>")
            text = text.replace("</ul><br>", "</ul>")
            text = text.replace("<ul><br>", "<ul>")
            text = text.replace("</li><br>", "</li>")
            html_output.append(text)
        else:
            # Code block parsing
            code_lines = part.split("\n")
            lang = "python"
            code_content = part
            
            # Check if language is specified on the first line
            if code_lines and code_lines[0].strip().lower() in ["python", "py", "cpp", "c++", "java", "javascript", "js", "go", "rust", "sql", "c", "csharp", "cs"]:
                lang = code_lines[0].strip().lower()
                code_content = "\n".join(code_lines[1:])
            
            # Trim leading/trailing whitespace
            code_content = code_content.strip()
            
            highlighted = ""
            if PYGMENTS_AVAILABLE:
                try:
                    if lang in ["cpp", "c++"]:
                        lexer_name = "cpp"
                    elif lang in ["py", "python"]:
                        lexer_name = "python"
                    elif lang in ["js", "javascript"]:
                        lexer_name = "javascript"
                    elif lang in ["cs", "csharp"]:
                        lexer_name = "csharp"
                    else:
                        lexer_name = lang
                    
                    lexer = get_lexer_by_name(lexer_name)
                except Exception:
                    try:
                        lexer = guess_lexer(code_content)
                    except Exception:
                        lexer = get_lexer_by_name("text")
                
                # HTML Formatter with inline styles (noclasses=True) and Monokai color palette
                formatter = HtmlFormatter(nowrap=True, noclasses=True, style='monokai')
                highlighted = highlight(code_content, lexer, formatter)
            else:
                highlighted = html.escape(code_content)
            
            code_block_html = (
                f'<div style="background-color: #0F172A; border: 1px solid rgba(255,255,255,0.08); '
                f'border-radius: 6px; padding: 12px; font-family: Consolas, monospace; font-size: 12px; '
                f'line-height: 1.5; overflow-x: auto; color: #E2E8F0; margin: 10px 0;">'
                f'<pre style="margin: 0; white-space: pre-wrap;">{highlighted}</pre>'
                f'</div>'
            )
            html_output.append(code_block_html)
            
    return "".join(html_output)


class SelectionOverlay(QWidget):
    """
    A translucent screen-spanning overlay window that allows the user to
    click and drag a selection rectangle to capture a specific region.
    """
    region_selected = Signal(QRect)

    def __init__(self, monitor_geometry: QRect):
        super().__init__()
        self.setGeometry(monitor_geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        
        self.begin = QPoint()
        self.end = QPoint()
        self.is_dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        # Semi-transparent dark overlay screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        
        if self.is_dragging:
            # Highlight selected rect as fully clear/transparent
            selected_rect = QRect(self.begin, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selected_rect, Qt.GlobalColor.transparent)
            
            # Reset composition mode to draw the boundary box
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(59, 130, 246, 255), 2)  # Elegant Neon Blue border
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(selected_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.position().toPoint()
            self.end = self.begin
            self.is_dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.end = event.position().toPoint()
            self.is_dragging = False
            rect = QRect(self.begin, self.end).normalized()
            
            # Convert local window coords to global screen coordinates
            global_rect = QRect(
                self.mapToGlobal(rect.topLeft()),
                self.mapToGlobal(rect.bottomRight())
            )
            
            self.hide()
            # Only trigger if the user dragged a minimum size region (to prevent accidental clicks)
            if rect.width() > 10 and rect.height() > 10:
                self.region_selected.emit(global_rect)
            self.close()

    def keyPressEvent(self, event):
        # Escape cancels the region selection
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.close()


class SolutionOverlay(QWidget):
    """
    The main, beautiful, glassmorphic solution display window.
    Applies custom styling, display affinity, and supports interactive/stealth modes.
    """
    opacity_changed = Signal(float)
    
    def __init__(self, width: int = 450, height: int = 700, default_opacity: float = 0.85, font_size: int = 13):
        super().__init__()
        
        self.default_width = width
        self.default_height = height
        self.current_opacity = default_opacity
        self.default_font_size = font_size
        
        self.is_interactive = False  # Starts in stealth click-through mode
        self.full_markdown_history = []
        self.history_index = -1
        
        self.init_ui()

    def init_ui(self):
        # Setup frameless top level overlay window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self.current_opacity)
        self.resize(self.default_width, self.default_height)
        
        # Outer Glass Container (adds padding and rounded corners styling)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.apply_theme()
        
        self.main_layout.addWidget(self.container)
        
        # Inner layout of container
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(15, 12, 15, 12)
        self.content_layout.setSpacing(8)
        
        # Header layout
        self.header_layout = QHBoxLayout()
        
        # Dynamic Badge for Title / Problem
        self.title_label = QLabel("SYSTEM IDLE", self)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch()
        
        # Complexity Badge
        self.complexity_badge = QLabel("", self)
        self.complexity_badge.setObjectName("complexityBadge")
        self.complexity_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.complexity_badge.setVisible(False)
        self.header_layout.addWidget(self.complexity_badge)
        
        # History Indicator Badge
        self.history_badge = QLabel("", self)
        self.history_badge.setObjectName("historyBadge")
        self.history_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.history_badge.setVisible(False)
        self.header_layout.addWidget(self.history_badge)
        
        # Mode Badge (STEALTH vs INTERACTIVE)
        self.mode_badge = QLabel("STEALTH", self)
        self.mode_badge.setObjectName("modeBadge")
        self.mode_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.header_layout.addWidget(self.mode_badge)
        
        self.content_layout.addLayout(self.header_layout)
        
        # Progress Bar / Loading Spinner (hidden by default)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Infinite animation
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setVisible(False)
        self.progress_bar.setObjectName("progressBar")
        self.content_layout.addWidget(self.progress_bar)
        
        # Splitter Panel: Problem summary vs Solution code
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(2)
        
        # 1. Summary Browser (Pattern, Insights, complexity)
        self.summary_browser = QTextBrowser(self)
        self.summary_browser.setOpenExternalLinks(True)
        self.summary_browser.setObjectName("summaryBrowser")
        self.summary_browser.setFont(QFont("Segoe UI", self.default_font_size))
        self.summary_browser.setPlaceholderText("Capture a region (Ctrl+Alt+S) to solve a problem...")
        
        # 2. Code Browser (Optimized Code blocks with Pygments syntax highlighting)
        self.code_browser = QTextBrowser(self)
        self.code_browser.setOpenExternalLinks(True)
        self.code_browser.setObjectName("codeBrowser")
        self.code_browser.setFont(QFont("Consolas", self.default_font_size))
        self.code_browser.setPlaceholderText("Solution code will stream here...")
        
        self.splitter.addWidget(self.summary_browser)
        self.splitter.addWidget(self.code_browser)
        
        # Initial sizing: equal split
        self.splitter.setSizes([200, 450])
        self.content_layout.addWidget(self.splitter)
        
        # Make the window drag-friendly in Interactive Mode
        self.drag_position = QPoint()

    def apply_theme(self):
        """Applies the custom, stunning dark glassmorphic stylesheet."""
        self.container.setStyleSheet(f"""
            QFrame#container {{
                background-color: rgba(15, 23, 42, 0.90); /* Deep slate with high opacity */
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }}
            QLabel#titleLabel {{
                color: #38BDF8; /* Neon Sky Blue */
            }}
            QLabel#complexityBadge {{
                background-color: rgba(168, 85, 247, 0.25); /* Translucent Purple */
                color: #C084FC;
                border: 1px solid rgba(168, 85, 247, 0.4);
                border-radius: 4px;
                padding: 2px 6px;
                margin-right: 4px;
            }}
            QLabel#historyBadge {{
                background-color: rgba(100, 116, 139, 0.25); /* Translucent Slate */
                color: #94A3B8;
                border: 1px solid rgba(100, 116, 139, 0.4);
                border-radius: 4px;
                padding: 2px 6px;
                margin-right: 4px;
            }}
            QLabel#modeBadge {{
                background-color: rgba(239, 68, 68, 0.2); /* Translucent Red (Stealth) */
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QProgressBar#progressBar {{
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 1.5px;
            }}
            QProgressBar#progressBar::chunk {{
                background-color: #38BDF8; /* Neon Sky Blue indicator */
                border-radius: 1.5px;
            }}
            QTextBrowser {{
                background-color: transparent;
                border: none;
                color: #E2E8F0;
                line-height: 1.4;
            }}
            QSplitter::handle {{
                background-color: rgba(255, 255, 255, 0.06);
            }}
        """)

    def update_interactive_style(self, interactive: bool):
        """Changes the mode badge style based on the interactive click-through state."""
        self.is_interactive = interactive
        if self.is_interactive:
            self.mode_badge.setText("EDIT MODE")
            self.mode_badge.setStyleSheet("""
                background-color: rgba(34, 197, 94, 0.25); /* Translucent Green */
                color: #4ADE80;
                border: 1px solid rgba(34, 197, 94, 0.4);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            self.title_label.setText(self.title_label.text().replace(" (STEALTH)", ""))
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            self.mode_badge.setText("STEALTH")
            self.mode_badge.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.2); /* Translucent Red */
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def update_ui_config(self, ui_settings: dict):
        """Hot-reloads UI opacity, dimensions, and font size dynamically."""
        if "opacity" in ui_settings:
            self.current_opacity = ui_settings["opacity"]
            self.setWindowOpacity(self.current_opacity)
        if "font_size" in ui_settings:
            self.default_font_size = ui_settings["font_size"]
            self.summary_browser.setFont(QFont("Segoe UI", self.default_font_size))
            self.code_browser.setFont(QFont("Consolas", self.default_font_size))
        
        # Redraw existing text to apply new font sizes
        if self.history_index >= 0 and self.history_index < len(self.full_markdown_history):
            self.display_solution(self.full_markdown_history[self.history_index], is_stream=False)

    # ------------------ Dynamic Opacity Control ------------------
    def wheelEvent(self, event):
        """Modifies opacity dynamically using Ctrl + Mouse Scroll Wheel."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            num_degrees = event.angleDelta().y() / 8
            num_steps = num_degrees / 15
            
            # Adjust opacity by 0.05 per step
            new_opacity = self.current_opacity + (num_steps * 0.05)
            # Clamp between 0.1 and 1.0
            new_opacity = max(0.1, min(1.0, new_opacity))
            
            self.current_opacity = new_opacity
            self.setWindowOpacity(self.current_opacity)
            self.opacity_changed.emit(self.current_opacity)
            event.accept()
        else:
            super().wheelEvent(event)

    # ------------------ Draggable Window implementation ------------------
    def mousePressEvent(self, event):
        # Dragging is ONLY allowed in Interactive Mode
        if self.is_interactive and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_interactive and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # ------------------ Solver Integration & Rendering ------------------
    def start_loading(self, problem_type: str = "REGION"):
        """Activates loading animation, resets status displays."""
        self.progress_bar.setVisible(True)
        self.title_label.setText(f"SOLVING ({problem_type})...")
        self.complexity_badge.setVisible(False)
        self.summary_browser.setHtml("<span style='color: #94A3B8;'>Taking screenshot, sending image to Gemini API...</span>")
        self.code_browser.setHtml("")

    def append_stream_chunk(self, chunk: str):
        """Appends streaming tokens as they arrive, separating metadata from core text."""
        # Check if this is the start of a streaming session
        self.progress_bar.setVisible(True)
        
        # Accumulate streaming text temporarily in the active history position
        if self.history_index == -1 or self.history_index < len(self.full_markdown_history) - 1:
            # We are writing a new item
            self.full_markdown_history.append(chunk)
            self.history_index = len(self.full_markdown_history) - 1
            if len(self.full_markdown_history) > 5:
                self.full_markdown_history.pop(0)
                self.history_index = len(self.full_markdown_history) - 1
        else:
            self.full_markdown_history[self.history_index] += chunk
            
        self.display_solution(self.full_markdown_history[self.history_index], is_stream=True)

    def finish_loading(self):
        """Completes loading, updates final badges and history states."""
        self.progress_bar.setVisible(False)
        if self.history_index >= 0 and self.history_index < len(self.full_markdown_history):
            self.display_solution(self.full_markdown_history[self.history_index], is_stream=False)

        # Update History badge if multiple exist
        total_history = len(self.full_markdown_history)
        if total_history > 1:
            self.history_badge.setText(f"H: {self.history_index + 1}/{total_history}")
            self.history_badge.setVisible(True)
        else:
            self.history_badge.setVisible(False)

    def display_solution(self, raw_md: str, is_stream: bool = False):
        """
        Parses raw markdown text, extracts metadata badges, formats code, 
        and updates the Splitter's summary and code text browsers.
        """
        parsed_title = "SOLVER ACTIVE"
        parsed_complexity = ""
        cleaned_md = raw_md

        # 1. Parse Metadata Badges from the beginning of the text
        # Title badge: [TITLE: text]
        title_match = re.search(r'^\[TITLE:\s*(.*?)\]', cleaned_md, re.MULTILINE)
        if title_match:
            parsed_title = title_match.group(1).strip()
            # Remove title badge line from display
            cleaned_md = re.sub(r'^\[TITLE:\s*(.*?)\]\n?', '', cleaned_md, flags=re.MULTILINE)
            
        # Complexity badge: [COMPLEXITY: text]
        complexity_match = re.search(r'^\[COMPLEXITY:\s*(.*?)\]', cleaned_md, re.MULTILINE)
        if complexity_match:
            parsed_complexity = complexity_match.group(1).strip()
            # Remove complexity badge line from display
            cleaned_md = re.sub(r'^\[COMPLEXITY:\s*(.*?)\]\n?', '', cleaned_md, flags=re.MULTILINE)

        # Apply parsed Title and Complexity
        self.title_label.setText(parsed_title.upper())
        if parsed_complexity:
            self.complexity_badge.setText(parsed_complexity)
            self.complexity_badge.setVisible(True)
        else:
            self.complexity_badge.setVisible(False)

        # 2. Extract code blocks from Markdown to separate Summary vs Code sections
        code_blocks = re.findall(r'```(?:[a-zA-Z0-9\+\-]+)?\n(.*?)```', cleaned_md, re.DOTALL)
        
        # Remove the code blocks from the summary markdown to keep the summary panel clean
        summary_md = re.sub(r'```(?:[a-zA-Z0-9\+\-]+)?\n.*?```', '', cleaned_md, flags=re.DOTALL)
        
        # Set summary panel content
        summary_html = markdown_to_html(summary_md)
        self.summary_browser.setHtml(summary_html)
        
        # Set code panel content
        if code_blocks:
            # We reconstruct code block markdown to highlight it correctly
            # Gather all code blocks found
            code_md_list = []
            for block in re.finditer(r'(```(?:[a-zA-Z0-9\+\-]+)?\n.*?```)', cleaned_md, re.DOTALL):
                code_md_list.append(block.group(1))
            
            code_html = markdown_to_html("\n\n".join(code_md_list))
            self.code_browser.setHtml(code_html)
        else:
            if is_stream:
                self.code_browser.setHtml("<span style='color: #64748B;'>Streaming code...</span>")
            else:
                self.code_browser.setHtml("<span style='color: #64748B;'>No code block found.</span>")

    def copy_code_to_clipboard(self):
        """Extracts the first code block from the current history item and copies it."""
        if self.history_index == -1 or self.history_index >= len(self.full_markdown_history):
            return
            
        current_md = self.full_markdown_history[self.history_index]
        code_blocks = re.findall(r'```(?:[a-zA-Z0-9\+\-]+)?\n(.*?)```', current_md, re.DOTALL)
        
        if code_blocks:
            code_to_copy = code_blocks[0].strip()
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(code_to_copy)
            # Temporarily flash status label to indicate success
            old_title = self.title_label.text()
            self.title_label.setText("COPIED TO CLIPBOARD!")
            self.title_label.setStyleSheet("color: #4ADE80;") # Green success flash
            
            # Reset title back after 1.5 seconds
            QtCore.QTimer.singleShot(1500, lambda: self.reset_title_label(old_title))

    def reset_title_label(self, original_text: str):
        self.title_label.setText(original_text)
        self.title_label.setStyleSheet("color: #38BDF8;")

    def cycle_history(self, direction: int):
        """Cycles through saved history items in-memory. Direction: -1 (prev), +1 (next)."""
        total_history = len(self.full_markdown_history)
        if total_history <= 1:
            return
            
        new_index = self.history_index + direction
        if 0 <= new_index < total_history:
            self.history_index = new_index
            self.display_solution(self.full_markdown_history[self.history_index], is_stream=False)
            self.history_badge.setText(f"H: {self.history_index + 1}/{total_history}")
            self.history_badge.setVisible(True)

    def clear_overlay(self):
        """Clears text browsers, complexity badge, and current history pointer."""
        self.summary_browser.clear()
        self.code_browser.clear()
        self.complexity_badge.setVisible(False)
        self.title_label.setText("SYSTEM IDLE")
        if self.history_index >= 0 and self.history_index < len(self.full_markdown_history):
            # Clear text in history but keep history list
            self.full_markdown_history.pop(self.history_index)
            self.history_index = len(self.full_markdown_history) - 1
            
        total_history = len(self.full_markdown_history)
        if total_history > 1:
            self.history_badge.setText(f"H: {self.history_index + 1}/{total_history}")
            self.history_badge.setVisible(True)
        else:
            self.history_badge.setVisible(False)
            
        if total_history == 0:
            self.summary_browser.setPlaceholderText("Capture a region (Ctrl+Alt+S) to solve a problem...")
            self.code_browser.setPlaceholderText("Solution code will stream here...")
