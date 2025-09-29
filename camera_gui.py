#!/usr/bin/env python3
"""
Simple Camera Configuration GUI for Frigate + MemryX
A simplified GUI focused solely on camera configuration - matches config_gui.py design
"""

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QCheckBox, QComboBox, QSpinBox, QFormLayout, 
                               QTextEdit, QGroupBox, QScrollArea, QFrame, QMessageBox, 
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QTabWidget)
from PySide6.QtGui import QFont, QPixmap, QCloseEvent
from PySide6.QtCore import Qt, Signal
import yaml
import sys
import os
import glob

class MyDumper(yaml.Dumper):
    """Custom YAML dumper for better formatting"""
    def write_line_break(self, data=None):
        super().write_line_break(data)
        # add an extra line break for top-level keys
        if len(self.indents) == 1:  
            super().write_line_break()

class CocoClassesDialog(QDialog):
    """Dialog to show available COCO classes - exact copy from config_gui.py"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COCO Classes")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Create text area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        
        # Load and display classes
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            classes_path = os.path.join(script_dir, "assets", "coco-classes.txt")
            with open(classes_path, 'r') as f:
                self.text_area.setText(f.read())
        except Exception as e:
            self.text_area.setText("Error loading COCO classes list.")
        
        # Set a reasonable size for the dialog
        self.text_area.setMinimumWidth(400)
        self.text_area.setMinimumHeight(500)
        
        layout.addWidget(self.text_area)
        
        # Add OK button
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)



class SimpleCameraGUI(QWidget):
    """Simple Camera Configuration GUI - exact design from config_gui.py"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frigate + MemryX Camera Config")
        
        # Get screen size (available geometry excludes taskbar/docks)
        screen = QApplication.primaryScreen()
        size = screen.availableGeometry()
        screen_width = size.width()
        screen_height = size.height()

        # Make window 50:65 ratio (50% screen width, 65% screen height)
        win_width = int(screen_width * 0.5)
        win_height = int(screen_height * 0.65)
        self.resize(win_width, win_height)

        # Center the window
        self.move(
            (screen_width - win_width) // 2,
            (screen_height - win_height) // 2
        )

        # Global Layout
        layout = QVBoxLayout(self)

        # --- Frigate Launcher Theme (Exact Match) ---
        self.professional_theme = """
            QMainWindow, QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fafbfc, stop:1 #f1f3f5);
                color: #111111;
                font-family: 'Segoe UI', 'Inter', 'system-ui', '-apple-system', sans-serif;
            }
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
                background: white;
                border: none;
                color: #111111;
            }
            QTabWidget, QTabWidget::pane, QTabBar, QTabBar::tab, QTabWidget QWidget {
                background: white;
                color: #111111;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e0;
                border-radius: 10px;
                margin-top: 6px;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f9fa, stop:1 #e9ecef);
                color: #111111;
                padding: 14px 22px;
                margin: 2px 1px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                border: 1px solid #dee2e6;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a90a4, stop:1 #38758a);
                color: #ffffff;
                border: 1px solid #38758a;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e3f2fd, stop:1 #bbdefb);
                color: #1976d2;
                border: 1px solid #90caf9;
            }
            QGroupBox {
                font-weight: 600;
                border: 2px solid #cbd5e0;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                background: white;
                color: #111111;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #111111;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a90a4, stop:1 #38758a);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 14px 26px;
                font-weight: 600;
                font-size: 14px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5b9bb0, stop:1 #428299);
            }
            QPushButton:pressed {
                background: #2d6374;
            }
            QPushButton:disabled {
                background: #a0aec0;
                color: #718096;
            }
            QTextEdit {
                border: 1px solid #cbd5e0;
                border-radius: 8px;
                background: white;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 14px;
                color: #111111;
                selection-background-color: #bee3f8;
                selection-color: #2a4365;
            }
            QTextEdit:focus {
                border: 2px solid #4a90a4;
            }
            QLineEdit {
                border: 1px solid #cbd5e0;
                border-radius: 8px;
                background: white;
                padding: 10px 12px;
                font-size: 14px;
                color: #111111;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                selection-background-color: #bee3f8;
                selection-color: #2a4365;
            }
            QLineEdit:focus {
                border: 2px solid #4a90a4;
            }
            QSpinBox {
                font-size: 16px;        /* bigger text */
                min-width: 36px;       /* wider */
                min-height: 20px;       /* taller */
                padding: 4px 10px;      /* more space inside */
            }
            QLabel {
                color: #111111;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel[header="true"] {
                font-size: 24px;
                font-weight: 700;
                color: #4a90a4;
            }
            QCheckBox {
                color: #111111;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #cbd5e0;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #4a90a4;
                border: 2px solid #38758a;
            }
            QFrame[separator="true"] {
                background: #cbd5e0;
                height: 1px;
                margin: 10px 0;
            }
            QFormLayout QLabel {
                font-weight: 600;
                color: #111111;
                font-size: 13px;
            }
            QLabel a {
                color: #4a90a4;
                text-decoration: none;
                font-weight: 600;
            }
            QLabel a:hover {
                color: #38758a;
            }
        """

        self.setStyleSheet(self.professional_theme)

        ################################
        # Header with Logos + Title
        ################################
        header = QHBoxLayout()
        
        # MemryX logo with blended styling
        memryx_logo = QLabel()
        memryx_logo.setPixmap(QPixmap("assets/memryx.png").scaledToHeight(70, Qt.SmoothTransformation))
        memryx_logo.setStyleSheet("""
            QLabel {
                background: rgba(255, 255, 255, 0.8);
                border-radius: 15px;
                padding: 8px;
                margin: 5px;
                border: 1px solid rgba(68, 68, 85, 0.2);
            }
        """)
        memryx_logo.setAlignment(Qt.AlignCenter)
        
        # Title
        title = QLabel("Frigate + MemryX Configurator")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("header", True)
        
        # Frigate logo with blended styling
        frigate_logo = QLabel()
        frigate_logo.setPixmap(QPixmap("assets/frigate.png").scaledToHeight(70, Qt.SmoothTransformation))
        frigate_logo.setStyleSheet("""
            QLabel {
                background: rgba(255, 255, 255, 0.8);
                border-radius: 15px;
                padding: 8px;
                margin: 5px;
                border: 1px solid rgba(68, 68, 85, 0.2);
            }
        """)
        frigate_logo.setAlignment(Qt.AlignCenter)
        
        header.addWidget(memryx_logo)
        header.addWidget(title, stretch=1)
        header.addWidget(frigate_logo)
        layout.addLayout(header)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setProperty("separator", True)
        layout.addWidget(line)

        ################################
        # Tabs - only camera tab
        ################################
        tabs = QTabWidget()

        # --- Camera Tab (exact copy from config_gui.py structure) ---
        cams_tab = QWidget()
        cams_layout = QVBoxLayout(cams_tab)

        # Camera count controls - modern professional look
        cams_count_frame = QFrame()
        cams_count_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px 8px;
                margin-bottom: 6px;
            }
        """)
        cams_count_layout = QHBoxLayout(cams_count_frame)
        cams_count_layout.setContentsMargins(2, 2, 2, 2)
        cams_count_layout.setSpacing(8)

        cams_count_label = QLabel("Number of Cameras")
        cams_count_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #222;")
        self.cams_count = QSpinBox()
        self.cams_count.setRange(1, 32)
        self.cams_count.setValue(1)
        self.cams_count.setStyleSheet("font-size: 13px; min-width: 32px; min-height: 18px; padding: 2px 6px;")
        self.cams_count.valueChanged.connect(self.on_camera_count_changed)
        cams_count_layout.addWidget(cams_count_label)
        cams_count_layout.addWidget(self.cams_count)

        cams_count_layout.addStretch()
        cams_layout.addWidget(cams_count_frame)

        # Sub-tabs for cameras
        self.cams_subtabs = QTabWidget()
        cams_layout.addWidget(self.cams_subtabs)

        # Add only the camera tab
        tabs.addTab(cams_tab, "🎥 Cameras")

        # Build initial camera tabs
        self.camera_tabs = []  # Initialize camera_tabs list
        
        # Initialize change tracking
        self.has_unsaved_changes = False
        self.original_config = None
        self.launcher_parent = None  # Reference to parent launcher (if opened from launcher)
        
        # Load existing cameras from config if available
        self.load_existing_cameras()
        
        layout.addWidget(tabs)

        ################################
        # Save button
        ################################
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Config")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #4a90a4;
                color: white;
                padding: 14px 28px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                min-width: 120px;
            }
            QPushButton:hover {
                background: #38758a;
            }
            QPushButton:pressed {
                background: #2d6374;
            }
        """)
        save_btn.clicked.connect(self.save_config)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

    def load_existing_cameras(self):
        """Load existing camera configurations from config.yaml if available"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "frigate", "config", "config.yaml")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                if config and "cameras" in config and config["cameras"]:
                    cameras = config["cameras"]
                    
                    # Set camera count to match existing cameras
                    self.cams_count.setValue(len(cameras))
                    
                    # Store original config for change detection
                    self.original_config = cameras.copy()
                    
                    # Rebuild tabs with existing camera count
                    self.rebuild_camera_tabs_with_existing_data(cameras)
                    return
                    
            except Exception as e:
                print(f"Error loading existing cameras: {e}")
        
        # Fallback: build default single camera tab
        self.rebuild_camera_tabs(self.cams_count.value())

    def rebuild_camera_tabs_with_existing_data(self, existing_cameras):
        """Rebuild camera tabs with existing camera data"""
        camera_list = list(existing_cameras.items())
        
        # Clear existing tabs
        self.cams_subtabs.clear()
        self.camera_tabs.clear()
        
        for idx, (camera_name, camera_config) in enumerate(camera_list):
            cam_widget = QWidget()
            form = QFormLayout(cam_widget)
            
            # Extract existing data from config
            ffmpeg_inputs = camera_config.get("ffmpeg", {}).get("inputs", [])
            camera_url = ffmpeg_inputs[0].get("path", "") if ffmpeg_inputs else ""
            
            # Parse RTSP URL to extract username, password, IP
            username = ""
            password = ""
            ip_address = ""
            
            if camera_url.startswith("rtsp://"):
                try:
                    # Parse rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0
                    url_part = camera_url[7:]  # Remove rtsp://
                    if "@" in url_part:
                        auth_part, rest = url_part.split("@", 1)
                        if ":" in auth_part:
                            username, password = auth_part.split(":", 1)
                        if ":" in rest:
                            ip_address = rest.split(":", 1)[0]
                        else:
                            ip_address = rest.split("/", 1)[0]
                except:
                    pass  # Keep defaults if parsing fails
            
            # Extract objects
            objects_list = camera_config.get("objects", {}).get("track", [])
            objects_text = ",".join(objects_list) if objects_list else "person,car,dog"
            
            # Extract recording settings
            record_config = camera_config.get("record", {})
            record_enabled = record_config.get("enabled", False)
            record_alerts_days = record_config.get("alerts", {}).get("retain", {}).get("days", 7)
            record_detections_days = record_config.get("detections", {}).get("retain", {}).get("days", 3)
            
            # Create form fields with existing data
            camera_name_field = QLineEdit(camera_name)
            username_field = QLineEdit(username)
            username_field.setPlaceholderText("Enter camera username")
            password_field = QLineEdit(password)
            password_field.setPlaceholderText("Enter camera password")
            ip_address_field = QLineEdit(ip_address)
            ip_address_field.setPlaceholderText("192.168.1.100")
            camera_url_field = QLineEdit(camera_url)
            camera_url_field.setPlaceholderText("rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0")
            camera_url_field.setEnabled(False)  # Disabled by default
            
            objects_field = QTextEdit(objects_text)
            objects_field.setMinimumHeight(100)
            objects_field.setMaximumHeight(200)
            objects_field.setStyleSheet("font-size: 14px; font-family: 'Segoe UI', 'Inter', sans-serif;")
            
            record_enabled_field = QCheckBox("Enable Recording")
            record_enabled_field.setChecked(record_enabled)
            
            record_alerts_field = QSpinBox()
            record_alerts_field.setRange(0, 365)
            record_alerts_field.setValue(record_alerts_days)
            record_alerts_field.setSuffix(" days")
            
            record_detections_field = QSpinBox()
            record_detections_field.setRange(0, 365)
            record_detections_field.setValue(record_detections_days)
            record_detections_field.setSuffix(" days")
            
            # Create container for recording settings
            record_settings_widget = QWidget()
            record_settings_layout = QFormLayout(record_settings_widget)
            record_settings_layout.setContentsMargins(20, 0, 0, 0)
            record_settings_layout.addRow("Days to keep alert recordings:", record_alerts_field)
            record_settings_layout.addRow("Days to keep detection recordings:", record_detections_field)
            record_settings_widget.setVisible(record_enabled)  # Show if recording is enabled
            
            # Connect record checkbox to show/hide retention settings
            record_enabled_field.toggled.connect(record_settings_widget.setVisible)
            
            # Auto-generate RTSP URL when username, password, or IP changes
            def create_update_function(u_field, p_field, i_field, url_field):
                def update_rtsp_url():
                    if not url_field.isEnabled():  # Only auto-generate if URL field is disabled
                        user = u_field.text().strip()
                        pwd = p_field.text().strip()
                        ip = i_field.text().strip()
                        if user and pwd and ip:
                            rtsp_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel=1&subtype=0"
                            url_field.setText(rtsp_url)
                        else:
                            url_field.setText("")
                    self.mark_as_changed()
                return update_rtsp_url
            
            update_function = create_update_function(username_field, password_field, ip_address_field, camera_url_field)
            username_field.textChanged.connect(update_function)
            password_field.textChanged.connect(update_function)
            ip_address_field.textChanged.connect(update_function)
            
            # Connect change tracking to all fields
            camera_name_field.textChanged.connect(self.mark_as_changed)
            username_field.textChanged.connect(self.mark_as_changed)
            password_field.textChanged.connect(self.mark_as_changed)
            ip_address_field.textChanged.connect(self.mark_as_changed)
            camera_url_field.textChanged.connect(self.mark_as_changed)
            objects_field.textChanged.connect(self.mark_as_changed)
            record_enabled_field.toggled.connect(self.mark_as_changed)
            record_alerts_field.valueChanged.connect(self.mark_as_changed)
            record_detections_field.valueChanged.connect(self.mark_as_changed)
            
            # Layout form
            form.addRow("Camera Name", camera_name_field)
            form.addRow("Username", username_field)
            form.addRow("Password", password_field)
            form.addRow("IP Address", ip_address_field)
            
            # Camera URL (optional, disabled by default)
            url_layout = QHBoxLayout()
            url_layout.addWidget(camera_url_field)
            enable_url_btn = QPushButton("Enable Manual URL")
            enable_url_btn.setMaximumWidth(150)
            enable_url_btn.setStyleSheet("""
                QPushButton {
                    background: #4b5563;
                    color: white;
                    padding: 8px 14px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                    border: none;
                }
                QPushButton:hover {
                    background: #374151;
                }
                QPushButton:pressed {
                    background: #1f2937;
                }
            """)
            
            def create_toggle_function(url_field, btn):
                def toggle_url_field():
                    if url_field.isEnabled():
                        url_field.setEnabled(False)
                        btn.setText("Enable Manual URL")
                    else:
                        url_field.setEnabled(True)
                        btn.setText("Auto Generate URL")
                    self.mark_as_changed()
                return toggle_url_field
            
            enable_url_btn.clicked.connect(create_toggle_function(camera_url_field, enable_url_btn))
            url_layout.addWidget(enable_url_btn)
            url_container = QWidget()
            url_container.setLayout(url_layout)
            form.addRow("Camera URL (Optional)", url_container)
            
            # Create objects row with help link
            objects_row = QHBoxLayout()
            objects_row.addWidget(objects_field)
            help_link = QLabel('&nbsp;<a href="#" style="color: #1976d2; font-weight: bold; text-decoration: none;">📋 View COCO Classes</a>')
            help_link.setTextFormat(Qt.RichText)
            help_link.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
            help_link.linkActivated.connect(lambda: CocoClassesDialog(self).exec())
            objects_row.addWidget(help_link)
            objects_container = QWidget()
            objects_container.setLayout(objects_row)
            form.addRow("Objects to Track", objects_container)
            
            # Recording section
            form.addRow("Recording", record_enabled_field)
            form.addRow("", record_settings_widget)
            
            # Add dynamic tab name update
            def create_tab_update_function(name_field, widget):
                def update_tab_name():
                    new_name = name_field.text()
                    current_index = self.cams_subtabs.indexOf(widget)
                    if current_index >= 0:
                        self.cams_subtabs.setTabText(current_index, new_name)
                    self.mark_as_changed()
                return update_tab_name
            
            camera_name_field.textChanged.connect(create_tab_update_function(camera_name_field, cam_widget))
            
            # Add to subtabs with the camera name
            self.cams_subtabs.addTab(cam_widget, camera_name)
            
            # Save refs
            self.camera_tabs.append({
                "camera_name": camera_name_field,
                "username": username_field,
                "password": password_field,
                "ip_address": ip_address_field,
                "camera_url": camera_url_field,
                "objects": objects_field,
                "record_enabled": record_enabled_field,
                "record_alerts": record_alerts_field,
                "record_detections": record_detections_field,
            })

    def mark_as_changed(self):
        """Mark that the configuration has unsaved changes"""
        self.has_unsaved_changes = True

    def on_camera_count_changed(self, count):
        """Handle camera count change"""
        self.rebuild_camera_tabs(count)
        self.mark_as_changed()

    def rebuild_camera_tabs(self, count: int):
        """Rebuild camera tabs - exact copy from config_gui.py"""
        # Step 1: Save existing values
        saved_data = []
        for cam in self.camera_tabs:
            saved_data.append({
                "camera_name": cam["camera_name"].text(),
                "username": cam["username"].text(),
                "password": cam["password"].text(),
                "ip_address": cam["ip_address"].text(),
                "camera_url": cam["camera_url"].text(),
                "objects": cam["objects"].toPlainText(),
                "record_enabled": cam["record_enabled"].isChecked(),
                "record_alerts": cam["record_alerts"].value(),
                "record_detections": cam["record_detections"].value(),
            })

        # Step 2: Clear tabs and rebuild
        self.cams_subtabs.clear()
        self.camera_tabs.clear()

        # Load existing camera names from config if available
        camera_names = []
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frigate", "config", "config.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                if config and "cameras" in config:
                    camera_names = list(config["cameras"].keys())
            except:
                pass

        for idx in range(count):
            cam_widget = QWidget()
            form = QFormLayout(cam_widget)

            # Restore data if exists, else defaults
            data = saved_data[idx] if idx < len(saved_data) else {}

            # Camera Name - automatically generated
            camera_name = QLineEdit(data.get("camera_name", f"camera_{idx+1}"))
            
            # Username
            username = QLineEdit(data.get("username", ""))
            username.setPlaceholderText("Enter camera username")
            
            # Password - open text as requested
            password = QLineEdit(data.get("password", ""))
            password.setPlaceholderText("Enter camera password")
            
            # IP Address
            ip_address = QLineEdit(data.get("ip_address", ""))
            ip_address.setPlaceholderText("192.168.1.100")
            
            # Camera URL - optional, disabled by default
            camera_url = QLineEdit(data.get("camera_url", ""))
            camera_url.setPlaceholderText("rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0")
            camera_url.setEnabled(False)  # Disabled by default
            
            # Objects to track
            objects = QTextEdit(data.get("objects", "person,car,dog"))
            objects.setMinimumHeight(100)
            objects.setMaximumHeight(200)
            objects.setStyleSheet("font-size: 14px; font-family: 'Segoe UI', 'Inter', sans-serif;")
            
            # Record option - disabled by default
            record_enabled = QCheckBox("Enable Recording")
            record_enabled.setChecked(data.get("record_enabled", False))
            
            # Recording retention settings (hidden by default)
            record_alerts = QSpinBox()
            record_alerts.setRange(0, 365)
            record_alerts.setValue(data.get("record_alerts", 7))
            record_alerts.setSuffix(" days")
            
            record_detections = QSpinBox()
            record_detections.setRange(0, 365)
            record_detections.setValue(data.get("record_detections", 3))
            record_detections.setSuffix(" days")
            
            # Create container for recording settings
            record_settings_widget = QWidget()
            record_settings_layout = QFormLayout(record_settings_widget)
            record_settings_layout.setContentsMargins(20, 0, 0, 0)
            record_settings_layout.addRow("Days to keep alert recordings:", record_alerts)
            record_settings_layout.addRow("Days to keep detection recordings:", record_detections)
            record_settings_widget.setVisible(False)  # Hidden by default
            
            # Connect record checkbox to show/hide retention settings
            record_enabled.toggled.connect(record_settings_widget.setVisible)
            
            # Auto-generate RTSP URL when username, password, or IP changes
            def update_rtsp_url():
                if not camera_url.isEnabled():  # Only auto-generate if URL field is disabled
                    user = username.text().strip()
                    pwd = password.text().strip()
                    ip = ip_address.text().strip()
                    if user and pwd and ip:
                        rtsp_url = f"rtsp://{user}:{pwd}@{ip}:554/cam/realmonitor?channel=1&subtype=0"
                        camera_url.setText(rtsp_url)
                    else:
                        camera_url.setText("")
            
            username.textChanged.connect(update_rtsp_url)
            password.textChanged.connect(update_rtsp_url)
            ip_address.textChanged.connect(update_rtsp_url)
            
            # Connect change tracking to all fields
            camera_name.textChanged.connect(self.mark_as_changed)
            username.textChanged.connect(self.mark_as_changed)
            password.textChanged.connect(self.mark_as_changed)
            ip_address.textChanged.connect(self.mark_as_changed)
            camera_url.textChanged.connect(self.mark_as_changed)
            objects.textChanged.connect(self.mark_as_changed)
            record_enabled.toggled.connect(self.mark_as_changed)
            record_alerts.valueChanged.connect(self.mark_as_changed)
            record_detections.valueChanged.connect(self.mark_as_changed)

            # Layout form - only requested fields
            form.addRow("Camera Name", camera_name)
            form.addRow("Username", username)
            form.addRow("Password", password)
            form.addRow("IP Address", ip_address)
            
            # Camera URL (optional, disabled by default)
            url_layout = QHBoxLayout()
            url_layout.addWidget(camera_url)
            enable_url_btn = QPushButton("Enable Manual URL")
            enable_url_btn.setMaximumWidth(150)
            enable_url_btn.setStyleSheet("""
                QPushButton {
                    background: #4b5563;
                    color: white;
                    padding: 8px 14px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                    border: none;
                }
                QPushButton:hover {
                    background: #374151;
                }
                QPushButton:pressed {
                    background: #1f2937;
                }
            """)
            def toggle_url_field():
                if camera_url.isEnabled():
                    camera_url.setEnabled(False)
                    enable_url_btn.setText("Enable Manual URL")
                else:
                    camera_url.setEnabled(True)
                    enable_url_btn.setText("Auto Generate URL")
                self.mark_as_changed()
            enable_url_btn.clicked.connect(toggle_url_field)
            url_layout.addWidget(enable_url_btn)
            url_container = QWidget()
            url_container.setLayout(url_layout)
            form.addRow("Camera URL (Optional)", url_container)
            
            # Create objects row with help link
            objects_row = QHBoxLayout()
            objects_row.addWidget(objects)
            help_link = QLabel('&nbsp;<a href="#" style="color: #1976d2; font-weight: bold; text-decoration: none;">📋 View COCO Classes</a>')
            help_link.setTextFormat(Qt.RichText)
            help_link.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
            help_link.linkActivated.connect(lambda: CocoClassesDialog(self).exec())
            objects_row.addWidget(help_link)
            objects_container = QWidget()
            objects_container.setLayout(objects_row)
            form.addRow("Objects to Track", objects_container)
            
            # Recording section
            form.addRow("Recording", record_enabled)
            form.addRow("", record_settings_widget)  # Recording retention settings

            # Add dynamic tab name update
            def update_tab_name():
                new_name = camera_name.text()
                current_index = self.cams_subtabs.indexOf(cam_widget)
                if current_index >= 0:
                    self.cams_subtabs.setTabText(current_index, new_name)
                self.mark_as_changed()
            
            camera_name.textChanged.connect(update_tab_name)

            # Add to subtabs with the camera name
            cam_name = camera_name.text()
            self.cams_subtabs.addTab(cam_widget, cam_name)

            # Save refs - only for fields we actually have
            self.camera_tabs.append({
                "camera_name": camera_name,
                "username": username,
                "password": password,
                "ip_address": ip_address,
                "camera_url": camera_url,
                "objects": objects,
                "record_enabled": record_enabled,
                "record_alerts": record_alerts,
                "record_detections": record_detections,
            })

    def save_config(self):
        """Save configuration - update only cameras in existing config"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        config_path = os.path.join(config_dir, "config.yaml")
        
        # Check if config.yaml exists
        if not os.path.exists(config_path):
            QMessageBox.warning(
                self, "Configuration Not Found", 
                "No existing Frigate configuration found!\n\n"
                "Please use the Manual Setup tab in the main launcher to:\n"
                "1. Complete system prerequisites\n"
                "2. Set up Frigate properly\n"
                "3. Generate the initial configuration\n\n"
                "Then return here to configure your cameras."
            )
            return
        
        # Load existing configuration
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config is None:
                config = {}
                
        except Exception as e:
            QMessageBox.critical(
                self, "Configuration Load Error", 
                f"Error loading existing configuration:\n{str(e)}\n\n"
                "Please check if the config.yaml file is valid."
            )
            return

        # Build cameras configuration only
        cameras_config = {}
        for cam in self.camera_tabs:
            # Generate RTSP URL if not manually provided
            camera_url = cam["camera_url"].text()
            if not camera_url or not cam["camera_url"].isEnabled():
                # Auto-generate RTSP URL from username, password, IP
                username = cam["username"].text()
                password = cam["password"].text()
                ip = cam["ip_address"].text()
                if username and password and ip:
                    camera_url = f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"
                else:
                    camera_url = "rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0"  # Default placeholder

            # Determine roles based on recording setting
            roles = ["detect"]
            if cam["record_enabled"].isChecked():
                roles.append("record")

            cam_config = {
                "ffmpeg": {
                    "inputs": [
                        {
                            "path": camera_url,
                            "roles": roles
                        }
                    ]
                },
                "detect": {
                    "width": 1920,
                    "height": 1080,
                    "fps": 20,
                    "enabled": True
                },
                "objects": {
                    "track": [obj.strip() for obj in cam["objects"].toPlainText().split(',') if obj.strip()]
                },
                "snapshots": {
                    "enabled": False,
                    "bounding_box": True,
                    "retain": {
                        "default": 1
                    }
                }
            }

            if cam["record_enabled"].isChecked():
                cam_config["record"] = {
                    "enabled": True,
                    "alerts": {
                        "retain": {
                            "days": cam["record_alerts"].value()
                        }
                    },
                    "detections": {
                        "retain": {
                            "days": cam["record_detections"].value()
                        }
                    }
                }

            cameras_config[cam["camera_name"].text()] = cam_config

        # Update only the cameras section in the existing config
        config["cameras"] = cameras_config

        # Save the updated configuration
        try:
            # Suppress config change popup in parent launcher if available
            if self.launcher_parent:
                self.launcher_parent.suppress_config_change_popup = True
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)
            
            # Mark as saved and close the GUI
            self.has_unsaved_changes = False
            
            QMessageBox.information(
                self, "Camera Configuration Updated", 
                f"Camera configuration updated successfully!\n\n"
                f"Updated {len(cameras_config)} camera(s) in:\n{config_path}\n\n"
                "All other settings (detectors, model, etc.) were preserved.\n\n"
                "The camera configuration window will now close."
            )
            
            # Re-enable config change popup after a short delay and update mtime
            if self.launcher_parent:
                # Update the config file modification time to prevent popup
                try:
                    self.launcher_parent.config_file_mtime = os.path.getmtime(config_path)
                except:
                    pass
                
                # Re-enable popup after 2 seconds
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: setattr(self.launcher_parent, 'suppress_config_change_popup', False))
            
            # Close the GUI window
            self.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving configuration:\n{str(e)}")
            # Re-enable popup on error as well
            if self.launcher_parent:
                self.launcher_parent.suppress_config_change_popup = False

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - check for unsaved changes"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                'You have unsaved camera configuration changes.\n\n'
                'Click "Save Config" button to save your changes before closing.\n\n'
                'Do you want to close without saving?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                event.accept()  # Close without saving
            else:
                event.ignore()  # Don't close, let user save first
        else:
            event.accept()  # No changes, safe to close

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Simple Camera GUI")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("MemryX")
    
    window = SimpleCameraGUI()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()