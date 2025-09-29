#!/usr/bin/env python3
"""
Advanced Configuration GUI for Frigate + MemryX
A comprehensive GUI for advanced Frigate configuration management
"""

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
                               QPushButton, QCheckBox, QComboBox, QSpinBox,
                               QFileDialog, QTextEdit, QTabWidget, QFormLayout, QListWidget, 
                               QListWidgetItem, QHBoxLayout, QFrame, QMessageBox, QGroupBox, QButtonGroup, QRadioButton, QDialog, QScrollArea) 
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt
import yaml
import sys
import os
import glob

class MyDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        super().write_line_break(data)
        # add an extra line break for top-level keys
        if len(self.indents) == 1:  
            super().write_line_break()

class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Settings")
        self.setModal(True)
        
        # Layout
        layout = QVBoxLayout()
        
        # Info label about config file path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        config_path = os.path.join(config_dir, "config.yaml")
        
        # Add message before showing the path
        msg_label = QLabel("You can manually update the config file in this path:")
        msg_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(msg_label)
        
        path_label = QLabel("Config File Path:")
        path_label.setStyleSheet("font-size: 15px; font-weight: bold; padding: 5px;")
        self.path_text = QLineEdit(config_path)
        self.path_text.setReadOnly(True)
        self.path_text.setStyleSheet("padding: 12px; font-size: 14px; background-color: #f5f5f5;")
        self.path_text.setMinimumWidth(400)
        
        # Note with documentation link
        note_label = QLabel(
            'For detailed configuration options, please visit the: '
            '<a style="color: #2c6b7d;" href="https://docs.frigate.video/configuration/reference">'
            'Frigate Configuration Reference</a>'
        )
        note_label.setOpenExternalLinks(True)
        note_label.setWordWrap(True)
        note_label.setStyleSheet("font-size: 14px; padding: 15px; line-height: 1.4;")
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        back_btn = QPushButton("Go Back")
        
        # Modify OK button to exit with code 2 (indicating manual edit)
        ok_btn.clicked.connect(lambda: (
            self.accept(),
            QApplication.instance().closeAllWindows(),
            QApplication.instance().exit(2)  # Exit code 2 for manual edit
        ))
        back_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(back_btn)
        btn_layout.addWidget(ok_btn)
        
        # Add widgets to layout
        layout.addWidget(path_label)
        layout.addWidget(self.path_text)
        layout.addWidget(note_label)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.resize(600, 250)  # Set a larger size

class CocoClassesDialog(QDialog):
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
            classes_path = os.path.join(script_dir, "assets/coco-classes.txt")
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

class CameraSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Camera Setup Guide - Frigate + MemryX")
        self.setModal(True)
        
        # Set window properties
        self.setMinimumSize(900, 800)
        self.resize(1000, 850)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header section
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #3498db, stop:1 #2980b9);
                border-radius: 0px;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 15)
        
        # Title
        title_label = QLabel("🎥 Camera Setup Guide")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        
        # Subtitle
        subtitle_label = QLabel("Learn how to connect and configure your IP camera for Frigate + MemryX")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
                background: transparent;
                margin-top: 5px;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setWordWrap(True)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        
        # Content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #3498db;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #2980b9;
            }
        """)
        
        # Create text area with HTML content
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                border: none;
                background-color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                padding: 20px;
            }
        """)
        
        # Enhanced HTML content with better styling
        html_content = """
        <html>
        <head>
            <style>
                body { 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.7; 
                    color: #2c3e50; 
                    margin: 0;
                    padding: 20px;
                    background-color: #ffffff;
                }
                .step-container {
                    background: #f8f9fa;
                    border-left: 5px solid #3498db;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 0 8px 8px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .step-title { 
                    color: #2980b9; 
                    font-size: 20px;
                    font-weight: bold;
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                }
                .step-subtitle { 
                    color: #34495e; 
                    font-size: 16px;
                    font-weight: 600;
                    margin: 15px 0 10px 0;
                }
                .method-container {
                    background: white;
                    border: 1px solid #e9ecef;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 10px 0;
                }
                code { 
                    background-color: #e8f4fd; 
                    padding: 3px 6px; 
                    border-radius: 4px; 
                    font-family: 'Consolas', 'Monaco', monospace;
                    color: #2980b9;
                    font-weight: 500;
                }
                pre { 
                    background-color: #f8f9fa; 
                    color: #2c3e50;
                    padding: 15px; 
                    border-radius: 6px; 
                    font-family: 'Consolas', 'Monaco', monospace;
                    overflow-x: auto;
                    border: 1px solid #dee2e6;
                    font-size: 14px;
                    font-weight: 600;
                }
                ul, ol { 
                    margin: 10px 0;
                    padding-left: 25px;
                }
                li { 
                    margin-bottom: 8px;
                    line-height: 1.6;
                }
                .important {
                    background: linear-gradient(135deg, #fff3cd, #ffeaa7);
                    border: 1px solid #f39c12;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 15px 0;
                    border-left: 4px solid #f39c12;
                }
                .example {
                    background: linear-gradient(135deg, #e8f5e8, #d4edda);
                    border: 1px solid #27ae60;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 15px 0;
                    border-left: 4px solid #27ae60;
                }
                .troubleshooting {
                    background: linear-gradient(135deg, #ffe8e8, #f8d7da);
                    border: 1px solid #e74c3c;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 15px 0;
                    border-left: 4px solid #e74c3c;
                }
                .icon {
                    font-size: 24px;
                    margin-right: 10px;
                }
                .success {
                    color: #27ae60;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="step-container">
                <div class="step-title">
                    <span class="icon">🔌</span> Step 1: Connect Your Camera
                </div>
                
                <div class="method-container">
                    <div class="step-subtitle">Option A: Wi-Fi Camera</div>
                    <ol>
                        <li><strong>Power on your camera</strong> and wait for it to initialize</li>
                        <li><strong>Download the camera's mobile app</strong> (check the manual, packaging, or QR code)</li>
                        <li>Use the app to configure Wi-Fi:
                            <ul>
                                <li>Search for available cameras</li>
                                <li>Select your Wi-Fi network</li>
                                <li>Enter your Wi-Fi password</li>
                                <li>Wait for connection confirmation</li>
                            </ul>
                        </li>
                    </ol>
                </div>
                
                <div class="method-container">
                    <div class="step-subtitle">Option B: Wired/PoE Camera</div>
                    <ol>
                        <li>Connect camera to your <strong>router or PoE switch</strong> using Ethernet cable</li>
                        <li>Power on the camera (PoE cameras get power from the cable)</li>
                        <li>Camera will automatically receive an IP address from your router</li>
                    </ol>
                </div>
            </div>
            
            <div class="step-container">
                <div class="step-title">
                    <span class="icon">🌐</span> Step 2: Find the Camera's IP Address
                </div>
                <p>You need the camera's <strong>IP address</strong> for Frigate to communicate with it.</p>
                
                <div class="method-container">
                    <div class="step-subtitle">Method A: Camera Mobile App</div>
                    <p>Most camera apps display the IP address under <strong>Settings → Network Info</strong> or <strong>Device Info</strong>.</p>
                </div>
                
                <div class="method-container">
                    <div class="step-subtitle">Method B: Router Admin Panel</div>
                    <ol>
                        <li>Open browser and go to <code>192.168.1.1</code> or <code>192.168.0.1</code></li>
                        <li>Login with router credentials (often on router label)</li>
                        <li>Navigate to <strong>Connected Devices</strong> or <strong>DHCP Client List</strong></li>
                        <li>Look for your camera (may show as brand name or "IP Camera")</li>
                        <li>Note the assigned IP address (e.g., <code>192.168.1.45</code>)</li>
                    </ol>
                </div>
                
                <div class="method-container">
                    <div class="step-subtitle">Method C: Network Scan (Linux)</div>
                    <p>Open terminal and run: <code>arp -a</code> or use network scanner tools.</p>
                </div>
            </div>
            
            <div class="step-container">
                <div class="step-title">
                    <span class="icon">🔑</span> Step 3: Get Camera Credentials
                </div>
                <p>Frigate needs <strong>username and password</strong> to access the RTSP stream. These are <em>not</em> your Wi-Fi credentials!</p>
                
                <div class="method-container">
                    <div class="step-subtitle">For Wi-Fi Cameras</div>
                    <ul>
                        <li>Open the camera's mobile app</li>
                        <li>Go to <strong>Camera Settings → RTSP Settings → Credentials</strong></li>
                        <li>Some apps auto-generate credentials or let you set custom ones</li>
                        <li>Common defaults: <code>admin/admin</code> or <code>admin/123456</code></li>
                    </ul>
                </div>
                
                <div class="method-container">
                    <div class="step-subtitle">For Wired/PoE Cameras</div>
                    <ul>
                        <li>Open browser and go to camera's IP (e.g., <code>http://192.168.1.45</code>)</li>
                        <li>Login with default credentials (check manual or camera label)</li>
                        <li>Navigate to <strong>Network → RTSP Settings</strong></li>
                        <li>Set or note the RTSP username and password</li>
                    </ul>
                </div>
                
                <div class="important">
                    <strong>⚠️ Important:</strong> If credentials contain special characters (@, :, /), they must be URL-encoded. 
                    For example: @ becomes %40, : becomes %3A
                </div>
            </div>
            
            <div class="step-container">
                <div class="step-title">
                    <span class="icon">🎥</span> Step 4: Construct RTSP URL
                </div>
                <p>The RTSP URL format that Frigate uses:</p>
                
                <pre><code>rtsp://username:password@CAMERA_IP:PORT/stream_path</code></pre>
                
                <ul>
                    <li><strong>username/password:</strong> From Step 3</li>
                    <li><strong>CAMERA_IP:</strong> From Step 2 (e.g., 192.168.1.45)</li>
                    <li><strong>PORT:</strong> Usually 554 (RTSP default)</li>
                    <li><strong>stream_path:</strong> Varies by manufacturer (/live, /stream, /h264, etc.)</li>
                </ul>
                
                <div class="example">
                    <strong>✅ Example URLs:</strong><br>
                    <code>rtsp://admin:123456@192.168.1.45:554/live</code><br>
                    <code>rtsp://user:password@192.168.1.100:554/stream1</code><br>
                    <code>rtsp://admin:admin@192.168.0.50:554/h264</code>
                </div>
            </div>
            
            <div class="step-container">
                <div class="step-title">
                    <span class="icon">📏</span> Step 5: Find Camera Resolution (Optional)
                </div>
                <p>Frigate needs the correct <strong>width × height</strong> for optimal detection:</p>
                
                <ul>
                    <li><strong>Camera App:</strong> Check <strong>Video Settings → Resolution</strong></li>
                    <li><strong>Web Interface:</strong> Look under <strong>Video/Stream Settings</strong></li>
                    <li><strong>Manual/Specs:</strong> Check product documentation</li>
                    <li><strong>Common values:</strong> 1920×1080 (Full HD), 1280×720 (HD), 640×480 (VGA)</li>
                </ul>
            </div>
            
            <div class="troubleshooting">
                <div class="step-title">
                    <span class="icon">🛠️</span> Troubleshooting Tips
                </div>
                <ul>
                    <li><strong>Can't find IP address?</strong> Reboot camera and router, then scan again</li>
                    <li><strong>RTSP URL not working?</strong> Double-check username, password, and stream path</li>
                    <li><strong>Connection refused?</strong> Verify RTSP is enabled in camera settings</li>
                    <li><strong>Wrong credentials?</strong> Try factory reset and use default credentials</li>
                    <li><strong>Stream path unknown?</strong> Try common paths: /live, /stream, /h264, /cam1</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0; padding: 20px; background: #e8f5e8; border-radius: 8px;">
                <span class="success" style="font-size: 18px;">🎉 Success!</span><br>
                <span style="font-size: 16px; color: #27ae60;">Your camera is now ready to connect with <strong>Frigate + MemryX</strong></span>
            </div>
        </body>
        </html>
        """
        
        self.text_area.setHtml(html_content)
        scroll_area.setWidget(self.text_area)
        
        # Footer with buttons
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #e9ecef;
            }
        """)
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(20, 15, 20, 15)
        
        # Close button
        close_btn = QPushButton("✓ Got it!")
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2980b9, stop:1 #1f618d);
            }
            QPushButton:pressed {
                background: #1f618d;
            }
        """)
        close_btn.clicked.connect(self.accept)
        
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        
        # Add all sections to main layout
        layout.addWidget(header_widget)
        layout.addWidget(scroll_area, 1)  # Give scroll area most space
        layout.addWidget(footer_widget)
        
        self.setLayout(layout)

class ConfigGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Frigate + MemryX Config Generator")
        
        # Get screen size (available geometry excludes taskbar/docks)
        screen = QApplication.primaryScreen()
        size = screen.availableGeometry()
        screen_width = size.width()
        screen_height = size.height()

        # Make width 70% of screen, height 80% of screen
        win_width = int(screen_width * 0.7)
        win_height = int(screen_height * 0.8)
        self.resize(win_width, win_height)

        # Center the window
        self.move(
            (screen_width - win_width) // 2,
            (screen_height - win_height) // 2
        )

        self.config_saved = False   # track if user pressed save
        self.advanced_settings_exit = False  # New flag to track exit via Advanced Settings

        # Global Layout
        layout = QVBoxLayout(self)

        # Theme removed - using only professional light theme

        # --- Professional Light Theme (Matching Frigate Launcher Colors) ---
        self.professional_theme = """
            QWidget { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f7f7f7, stop:1 #e9ecef); color: #2d3748; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; font-size: 16px; }
            QTabWidget::pane { border: 1px solid #bbb; border-radius: 12px; background: #fff; margin-top: 10px; }
            QTabBar::tab { background: #e0e0e0; color: #2d3748; padding: 12px 28px; margin: 4px; border-radius: 12px; font-size: 17px; font-weight: 700; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QTabBar::tab:selected { background: #2c6b7d; color: #fff; }
            QTabBar::tab:hover { background: #234f60; color: #fff; }
            QGroupBox { border: 1px solid #bbb; border-radius: 14px; margin-top: 14px; padding: 14px; padding-top: 8px; background: #f5f5f5; font-size: 16px; font-weight: 600; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QGroupBox::title { color: #2d3748; font-weight: 600; }
            QGroupBox::indicator { width: 18px; height: 18px; border: 2px solid #2c6b7d; border-radius: 4px; background-color: #fff; }
            QGroupBox::indicator:checked { background-color: #2c6b7d; }
            QGroupBox::indicator:hover { border-color: #234f60; }
            QPushButton { background-color: #2c6b7d; color: #fff; padding: 14px 32px; border-radius: 12px; font-size: 17px; font-weight: 700; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QPushButton:hover { background-color: #234f60; }
            QPushButton:disabled { background: #bbb; color: #888; }
            QLineEdit, QTextEdit { border-radius: 10px; border: 2px solid #2c6b7d; padding: 10px; background: #fff; color: #2d3748; font-size: 16px; font-weight: 600; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QLineEdit:disabled, QTextEdit:disabled { background: #eee; color: #aaa; border: 2px solid #bbb; }
            QComboBox { border: 1.5px solid #2c6b7d; border-radius: 10px; background: #fafdff; padding: 8px 18px; color: #2d3748; font-size: 16px; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QComboBox:focus { border: 2px solid #2c6b7d; }
            QComboBox:hover { background: #e0e0e0; }
            QCheckBox { color: #2d3748; font-size: 16px; font-weight: 600; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; padding: 2px; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #2c6b7d; border-radius: 4px; background-color: #fff; }
            QCheckBox::indicator:checked { background-color: #2c6b7d; }
            QCheckBox::indicator:hover { border-color: #234f60; }
            QCheckBox:disabled { color: #aaa; }
            QCheckBox::indicator:disabled { background-color: #eee; border: 2px solid #bbb; }
            QLabel[header="true"] { font-size: 28px; font-weight: bold; color: #2c6b7d; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QLabel[section="true"] { font-size: 19px; font-weight: bold; color: #2d3748; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QLabel[device="true"] { color: #2d3748; background: #e0e0e0; border-radius: 8px; padding: 6px 12px; margin: 2px 0; font-size: 15px; font-weight: 600; }
            QRadioButton { background: #e0e0e0; color: #2d3748; border: 2px solid #bbb; border-radius: 14px; padding: 10px 24px; margin: 0 6px; font-size: 16px; font-weight: 700; font-family: 'Segoe UI', 'Arial', 'Ubuntu', 'system-ui', sans-serif; }
            QRadioButton::indicator { width: 0; height: 0; }
            QRadioButton:checked { background: #2c6b7d; color: #fff; border: 2px solid #2c6b7d; }
            QRadioButton:disabled { color: #aaa; background: #eee; border: 2px solid #bbb; }
            QFrame[separator="true"] { background: #bbb; height: 2px; }
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
        # Tabs
        ################################
        tabs = QTabWidget()

        # --- MQTT Tab
        self.mqtt_enabled = QCheckBox("Enable MQTT")
        self.mqtt_enabled.stateChanged.connect(self.toggle_mqtt_fields)

        self.mqtt_host = QLineEdit()
        self.mqtt_host.setPlaceholderText("mqtt.server.com")
        self.mqtt_port = QLineEdit("1883")
        self.mqtt_topic = QLineEdit("frigate")

        mqtt_layout = QFormLayout()
        mqtt_layout.addRow("Enable", self.mqtt_enabled)
        mqtt_layout.addRow("Host", self.mqtt_host)
        mqtt_layout.addRow("Port", self.mqtt_port)
        mqtt_layout.addRow("Topic Prefix", self.mqtt_topic)

        mqtt_widget = QWidget()
        mqtt_widget.setLayout(mqtt_layout)

        # Professional styling for MQTT docs
        mqtt_docs_bg = "background: #f5f5f5; border-radius: 10px; padding: 8px;"
        mqtt_docs_style = "color: black;"

        # MQTT docs label
        mqtt_docs_label = QLabel(
            'ℹ️ For MQTT integration setup and configuration options, please visit: '
            '<a href="https://docs.frigate.video/integrations/mqtt">MQTT Integration Documentation</a>'
        )
        mqtt_docs_label.setOpenExternalLinks(True)
        mqtt_docs_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        mqtt_docs_label.setWordWrap(True)
        mqtt_docs_label.setStyleSheet(mqtt_docs_style)

        # Wrap inside container
        mqtt_docs_container = QWidget()
        mqtt_docs_layout = QVBoxLayout(mqtt_docs_container)
        mqtt_docs_layout.setContentsMargins(12, 8, 12, 8)
        mqtt_docs_container.setStyleSheet(mqtt_docs_bg)
        mqtt_docs_layout.addWidget(mqtt_docs_label)

        mqtt_layout.addRow(mqtt_docs_container)

        tabs.addTab(mqtt_widget, "MQTT")

        # --- Detector Tab (only MemryX) ---
        detector_layout = QFormLayout()

        detector_label = QLabel("Detector Type: MemryX")
        font = QFont("Arial", 12, QFont.Bold)   # size 12, bold
        detector_label.setFont(font)

        # Detect how many /dev/memx* devices exist (exclude *_feature files)
        device_paths = [d for d in glob.glob("/dev/memx*") if "_feature" not in d]
        num_devices = len(device_paths)

        # Spinbox: user chooses how many devices to use
        self.memryx_devices = QSpinBox()
        self.memryx_devices.setRange(1, max(1, num_devices if num_devices > 0 else 8))
        self.memryx_devices.setValue(num_devices if num_devices > 0 else 1)

        # GroupBox to show available devices
        device_box = QGroupBox("Available Devices")
        device_layout = QVBoxLayout()

        # Detect current theme - using professional color
        header_style = "font-weight: bold; color: #2c6b7d;"
        label_style = "color: black; margin-left: 10px;"
        error_style = "color: red; font-weight: bold;"
        # Create an inner QWidget for the info area
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(12, 8, 12, 8)  # Optional: add padding
        info_bg = "background: #f5f5f5; border-radius: 10px;"
        info_widget.setStyleSheet(info_bg)

        if num_devices > 0:
            header = QLabel(f"✅ Detected {num_devices} MemryX device(s):")
            header.setStyleSheet(header_style)
            info_layout.addWidget(header)
            for d in device_paths:
                lbl = QLabel(f"• {d}")
                lbl.setStyleSheet(label_style)
                info_layout.addWidget(lbl)
        else:
            lbl = QLabel("❌ No MemryX devices detected in the system!")
            lbl.setStyleSheet(error_style)
            info_layout.addWidget(lbl)

        device_layout.addWidget(info_widget)
        device_box.setLayout(device_layout)

        # Add widgets to form
        detector_layout.addRow(detector_label)
        detector_layout.addRow("Number of MemryX Devices", self.memryx_devices)
        detector_layout.addRow(device_box)

        detector_widget = QWidget()
        detector_widget.setLayout(detector_layout)
        tabs.addTab(detector_widget, "Detector")

        # --- Model Tab
        self.model_type = QComboBox()
        self.model_type.addItems(["yolo-generic", "yolonas", "yolox", "ssd"])
        self.model_type.currentTextChanged.connect(self.update_model_defaults)

        # Resolution (Width x Height), options depend on model_type
        self.model_resolution = QComboBox()

        # Input tensor and dtype
        self.input_tensor = QComboBox()
        self.input_tensor.addItems(["nchw", "nhwc", "hwnc", "hwcn"])

        self.input_dtype = QComboBox()
        self.input_dtype.addItems(["float", "float_denorm", "int"])

        # --- Custom model path (QGroupBox) ---
        self.custom_group = QGroupBox("Use custom model path")
        self.custom_group.setCheckable(True)

        # Input tensor and dtype
        self.input_tensor = QComboBox()
        self.input_tensor.addItems(["nchw", "nhwc", "hwnc", "hwcn"])

        self.input_dtype = QComboBox()
        self.input_dtype.addItems(["float", "float_denorm", "int"])

        # --- Custom model path (QGroupBox) ---
        self.custom_group = QGroupBox("Use custom model path")
        self.custom_group.setCheckable(True)
        self.custom_group.setChecked(False)   # default off
        self.custom_group.toggled.connect(self.toggle_custom_model_mode)

        # Path row + custom width/height inside the group
        custom_v = QVBoxLayout()
        path_row = QHBoxLayout()
        self.custom_path = QLineEdit("/config/yolo.zip")
        self.browse_btn = QPushButton("Browse")
        path_row.addWidget(self.custom_path)
        path_row.addWidget(self.browse_btn)
        custom_v.addLayout(path_row)

        # Custom width/height spinboxes (enabled only when group is checked)
        self.custom_width = QSpinBox();  self.custom_width.setRange(1, 8192); self.custom_width.setValue(320)
        self.custom_height = QSpinBox(); self.custom_height.setRange(1, 8192); self.custom_height.setValue(320)
        custom_form = QFormLayout()
        custom_form.addRow("Custom Width", self.custom_width)
        custom_form.addRow("Custom Height", self.custom_height)
        custom_v.addLayout(custom_form)

        self.custom_group.setLayout(custom_v)

        def browse_model_file():
            path, _ = QFileDialog.getOpenFileName(self, "Select Model File", "/config", "Zip Files (*.zip);;All Files (*)")
            if path:
                self.custom_path.setText(path)

        self.browse_btn.clicked.connect(browse_model_file)

        # # Info label about default behavior
        # self.model_note = QLabel(
        #     "ℹ️ Default: Model is normally fetched through runtime, so 'path' can be omitted.\n"
        #     "Enable custom path only if you want to use a local model. When enabled, you can set custom Width/Height."
        # )

        # Professional styling for note
        note_bg = "background: #f5f5f5; border-radius: 10px; padding: 8px;"
        note_style = "color: #444; font-size: 11px;"

        # Info label about default behavior
        self.model_note = QLabel(
            "ℹ️ Default: Model is normally fetched through runtime, so 'path' can be omitted.\n"
            "Enable custom path only if you want to use a local model. When enabled, you can set custom Width/Height."
        )
        self.model_note.setWordWrap(True)
        self.model_note.setStyleSheet(note_style)

        # Wrap inside container
        note_container = QWidget()
        note_layout = QVBoxLayout(note_container)
        note_layout.setContentsMargins(12, 8, 12, 8)
        note_container.setStyleSheet(note_bg)
        note_layout.addWidget(self.model_note)

        # Labelmap path
        self.labelmap_path = QLineEdit("/labelmap/coco-80.txt")

        # Layout
        model_layout = QFormLayout()
        model_layout.addRow("Type", self.model_type)
        model_layout.addRow("Resolution", self.model_resolution)
        model_layout.addRow("Input Tensor", self.input_tensor)
        model_layout.addRow("Input DType", self.input_dtype)
        model_layout.addRow(self.custom_group)  
        model_layout.addRow("Labelmap Path", self.labelmap_path)
        model_layout.addRow(note_container) 

        model_widget = QWidget()
        model_widget.setLayout(model_layout)
        tabs.addTab(model_widget, "Model")

        # --- Allowed resolutions per model
        # display strings must match "W x H"
        self.model_allowed_res = {
            "yolo-generic": ["320 x 320", "640 x 640"],
            "yolonas":      ["320 x 320", "640 x 640"],
            "yolox":        ["640 x 640"],
            "ssd":          ["320 x 320"],
        }

        # --- Defaults for each model type (no width/height here; use resolution list's first item)
        self.model_defaults = {
            "yolo-generic": {"tensor": "nchw", "dtype": "float",        "path": "/config/yolo.zip"},
            "yolonas":      {"tensor": "nchw", "dtype": "float",        "path": "/config/yolonas_320.zip"},
            "yolox":        {"tensor": "nchw", "dtype": "float_denorm", "path": "/config/yolox.zip"},
            "ssd":          {"tensor": "nchw", "dtype": "float",        "path": "/config/ssd.zip"},
        }

        # Initialize defaults and resolution options
        self.update_model_defaults(self.model_type.currentText())
        # Ensure widgets reflect initial custom_mode state
        self.toggle_custom_model_mode(self.custom_group.isChecked())

        # --- FFmpeg Tab ---
        ffmpeg_layout = QFormLayout()

        # GroupBox for optional ffmpeg config
        self.ffmpeg_group = QGroupBox("Enable FFmpeg Config")
        self.ffmpeg_group.setCheckable(True)
        self.ffmpeg_group.setChecked(False)

        ffmpeg_inner_layout = QFormLayout()

        # Add some spacing before hwaccel_args
        ffmpeg_inner_layout.addRow("", QLabel(""))  # Empty row for spacing

        # hwaccel_args dropdown
        self.ffmpeg_hwaccel = QComboBox()
        self.ffmpeg_hwaccel.addItems([
            "preset-rpi-64-h264",
            "preset-rpi-64-h265",
            "preset-vaapi",
            "preset-intel-qsv-h264",
            "preset-intel-qsv-h265",
            "preset-nvidia",
            "preset-jetson-h264",
            "preset-jetson-h265",
            "preset-rkmpp"
        ])
        self.ffmpeg_hwaccel.setCurrentText("preset-vaapi")  # Default value
        self.ffmpeg_hwaccel.setEnabled(False)  # disabled until box checked

        def toggle_ffmpeg(checked):
            self.ffmpeg_hwaccel.setEnabled(checked)

        self.ffmpeg_group.toggled.connect(toggle_ffmpeg)

        ffmpeg_inner_layout.addRow("hwaccel_args", self.ffmpeg_hwaccel)

        self.ffmpeg_group.setLayout(ffmpeg_inner_layout)

        ffmpeg_layout.addRow(self.ffmpeg_group)

        # Professional styling for docs
        docs_bg = "background: #f5f5f5; border-radius: 10px; padding: 8px;"
        docs_style = "color: black;"

        # Docs label
        docs_label = QLabel(
            'ℹ️ See <a href="https://docs.frigate.video/configuration/ffmpeg_presets/">FFmpeg Presets Docs</a> '
            "for more configuration options."
        )
        docs_label.setOpenExternalLinks(True)
        docs_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        docs_label.setWordWrap(True)
        docs_label.setStyleSheet(docs_style)

        # Wrap inside container
        docs_container = QWidget()
        docs_layout = QVBoxLayout(docs_container)
        docs_layout.setContentsMargins(12, 8, 12, 8)
        docs_container.setStyleSheet(docs_bg)
        docs_layout.addWidget(docs_label)

        ffmpeg_layout.addRow(docs_container)

        ffmpeg_widget = QWidget()
        ffmpeg_widget.setLayout(ffmpeg_layout)
        tabs.addTab(ffmpeg_widget, "FFmpeg")

        # --- Camera Tab
        self.camera_tabs = []  # store camera widget sets

        cams_tab = QWidget()
        cams_layout = QVBoxLayout(cams_tab)

        # Number of cameras spinbox
        cams_count_layout = QHBoxLayout()
        
        # Camera Setup Guide button (first in the row)
        setup_guide_btn = QPushButton("📖 Camera Setup Guide")
        setup_guide_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c6b7d;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #234f60;
            }
        """)
        setup_guide_btn.clicked.connect(lambda: CameraSetupDialog(self).exec())
        cams_count_layout.addWidget(setup_guide_btn)
        
        # Add some spacing between guide button and camera count
        cams_count_layout.addSpacing(20)
        
        cams_count_label = QLabel("Number of Cameras")
        self.cams_count = QSpinBox()
        self.cams_count.setRange(1, 32)
        self.cams_count.setValue(1)
        self.cams_count.valueChanged.connect(self.rebuild_camera_tabs)
        cams_count_layout.addWidget(cams_count_label)
        cams_count_layout.addWidget(self.cams_count)
        
        cams_count_layout.addStretch()
        cams_layout.addLayout(cams_count_layout)

        # Sub-tabs for cameras
        self.cams_subtabs = QTabWidget()
        cams_layout.addWidget(self.cams_subtabs)

        tabs.addTab(detector_widget, "🧠 Detector")
        tabs.addTab(model_widget, "📦 Model")
        tabs.addTab(cams_tab, "🎥 Cameras")
        tabs.addTab(ffmpeg_widget, "🎬 FFmpeg")
        tabs.addTab(mqtt_widget, "🟢 MQTT")

        # Build initial camera tabs
        self.rebuild_camera_tabs(self.cams_count.value())

        layout.addWidget(tabs)

        # Disable MQTT fields initially
        self.toggle_mqtt_fields()

        ################################
        # Save and Advanced Settings buttons
        ################################
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Config")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c6b7d;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #234f60;
            }
        """)
        save_btn.clicked.connect(self.save_config)

        adv_btn = QPushButton("Advanced Settings")
        adv_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a7f95;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2c6b7d;
            }
        """)
        adv_btn.clicked.connect(self.show_advanced_settings)
        
        btn_layout.addStretch()  # This pushes the buttons to the right
        btn_layout.addWidget(adv_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Load existing configuration if available
        self.load_existing_config()

    # -------- helpers for resolution & modes --------
    def _parse_resolution(self, text: str):
        # expects like "320 x 320"
        try:
            w, h = [int(p.strip()) for p in text.lower().split("x")]
            return w, h
        except Exception:
            return 320, 320  # safe fallback

    def _set_resolution_options(self, options, prefer=None):
        """Replace items in the resolution combo with 'options'.
        If 'prefer' is in options, select it; else select the first."""
        self.model_resolution.blockSignals(True)
        self.model_resolution.clear()
        self.model_resolution.addItems(options)
        if prefer in options:
            self.model_resolution.setCurrentText(prefer)
        else:
            self.model_resolution.setCurrentIndex(0)
        self.model_resolution.blockSignals(False)

        # Keep custom spinboxes in sync so toggling is seamless
        w, h = self._parse_resolution(self.model_resolution.currentText())
        self.custom_width.setValue(w)
        self.custom_height.setValue(h)

    def toggle_mqtt_fields(self):
        enabled = self.mqtt_enabled.isChecked()
        self.mqtt_host.setEnabled(enabled)
        self.mqtt_port.setEnabled(enabled)
        self.mqtt_topic.setEnabled(enabled)

    def toggle_custom_model_mode(self, checked: bool):
        # When using custom path, enable custom width/height and disable preset resolution
        self.model_resolution.setEnabled(not checked)
        self.custom_path.setEnabled(checked)
        self.browse_btn.setEnabled(checked)
        self.custom_width.setEnabled(checked)
        self.custom_height.setEnabled(checked)

        # If turning custom OFF, sync spinboxes back to selected resolution
        if not checked:
            w, h = self._parse_resolution(self.model_resolution.currentText())
            self.custom_width.setValue(w)
            self.custom_height.setValue(h)

    def update_model_defaults(self, model_name: str):
        # 1) Update resolution options for this model
        options = self.model_allowed_res.get(model_name, ["320 x 320"])
        # choose the first option as default unless we have a previous compatible choice
        current = self.model_resolution.currentText()
        prefer = current if current in options else None
        self._set_resolution_options(options, prefer=prefer)

        # 2) Apply other defaults
        defaults = self.model_defaults.get(model_name, {})
        self.input_tensor.setCurrentText(defaults.get("tensor", "nchw"))
        self.input_dtype.setCurrentText(defaults.get("dtype", "float"))
        self.custom_path.setText(defaults.get("path", "/config/yolo.zip"))

    def rebuild_camera_tabs(self, count: int):
        # Step 1: Save existing values
        saved_data = []
        for cam in self.camera_tabs:
            saved_data.append({
                "camera_name": cam["camera_name"].text(),
                "camera_url": cam["camera_url"].text(),
                "role_detect": cam["role_detect"].isChecked(),
                "role_record": cam["role_record"].isChecked(),
                "detect_width": cam["detect_width"].value(),
                "detect_height": cam["detect_height"].value(),
                "detect_fps": cam["detect_fps"].value(),
                "detect_enabled": cam["detect_enabled"].isChecked(),
                "objects": cam["objects"].toPlainText(),
                "snapshots_enabled": cam["snapshots_enabled"].isChecked(),
                "snapshots_bb": cam["snapshots_bb"].isChecked(),
                "snapshots_retain": cam["snapshots_retain"].value(),
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

            # Use camera name from config if available, otherwise use default
            default_name = camera_names[idx] if idx < len(camera_names) else f"camera_{idx+1}"
            camera_name = QLineEdit(data.get("camera_name", default_name))
            camera_url = QLineEdit(data.get("camera_url", "rtsp://..."))

            role_detect = QCheckBox("Detect")
            role_detect.setChecked(data.get("role_detect", True))
            role_record = QCheckBox("Record")
            role_record.setChecked(data.get("role_record", True))
            roles_layout = QHBoxLayout()
            roles_layout.addWidget(role_detect)
            roles_layout.addWidget(role_record)

            detect_width = QSpinBox(); detect_width.setRange(100, 8000)
            detect_width.setValue(data.get("detect_width", 1920))
            detect_height = QSpinBox(); detect_height.setRange(100, 8000)
            detect_height.setValue(data.get("detect_height", 1080))
            detect_fps = QSpinBox(); detect_fps.setRange(1, 500)
            detect_fps.setValue(data.get("detect_fps", 20))
            detect_enabled = QCheckBox(); detect_enabled.setChecked(data.get("detect_enabled", True))

            objects = QTextEdit(data.get("objects", "person,car,dog"))

            snapshots_enabled = QCheckBox(); snapshots_enabled.setChecked(data.get("snapshots_enabled", False))
            snapshots_bb = QCheckBox(); snapshots_bb.setChecked(data.get("snapshots_bb", True))
            snapshots_retain = QSpinBox(); snapshots_retain.setRange(1, 1000)
            snapshots_retain.setValue(data.get("snapshots_retain", 1))

            record_enabled = QCheckBox(); record_enabled.setChecked(data.get("record_enabled", False))
            record_alerts = QSpinBox(); record_alerts.setRange(1, 1000)
            record_alerts.setValue(data.get("record_alerts", 1))
            record_detections = QSpinBox(); record_detections.setRange(1, 1000)
            record_detections.setValue(data.get("record_detections", 1))

            # Layout form
            form.addRow("Camera Name", camera_name)
            form.addRow("Camera URL", camera_url)
            
            # RTSP info note
            rtsp_note = QLabel(
                "ℹ️ RTSP URL format: rtsp://username:password@ip:port/path"
            )
            rtsp_note.setWordWrap(True)
            rtsp_note.setStyleSheet("""
                QLabel {
                    color: #2c6b7d;
                    font-size: 12px;
                    padding: 5px;
                    background: #f5f5f5;
                    border-radius: 5px;
                    margin: 2px 0;
                }
            """)
            form.addRow("", rtsp_note)  # Empty label for the note row
            
            form.addRow("Roles", roles_layout)
            form.addRow("Camera Width", detect_width)
            form.addRow("Camera Height", detect_height)
            form.addRow("Detect FPS", detect_fps)
            form.addRow("Detect Enabled", detect_enabled)
            # Create objects row with help link
            objects_row = QHBoxLayout()
            objects_row.addWidget(objects)
            help_link = QLabel('&nbsp;<a href="#" style="color: #2c6b7d; text-decoration: none;">📋 View COCO Classes</a>')
            help_link.setTextFormat(Qt.RichText)
            help_link.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
            help_link.linkActivated.connect(lambda: CocoClassesDialog(self).exec())
            objects_row.addWidget(help_link)
            objects_container = QWidget()
            objects_container.setLayout(objects_row)
            form.addRow("Objects to Track", objects_container)
            
            form.addRow("Snapshots Enabled", snapshots_enabled)
            form.addRow("Bounding Box", snapshots_bb)
            form.addRow("Snapshots Retain (days)", snapshots_retain)
            form.addRow("Record Enabled", record_enabled)
            form.addRow("Record Alerts Retain (days)", record_alerts)
            form.addRow("Record Detections Retain (days)", record_detections)

            # Add dynamic tab name update
            def update_tab_name():
                new_name = camera_name.text()
                current_index = self.cams_subtabs.indexOf(cam_widget)
                self.cams_subtabs.setTabText(current_index, new_name)
            
            camera_name.textChanged.connect(update_tab_name)

            # Add to subtabs with the camera name
            cam_name = camera_name.text()
            self.cams_subtabs.addTab(cam_widget, cam_name)

            # Save refs
            self.camera_tabs.append({
                "camera_name": camera_name,
                "camera_url": camera_url,
                "role_detect": role_detect,
                "role_record": role_record,
                "detect_width": detect_width,
                "detect_height": detect_height,
                "detect_fps": detect_fps,
                "detect_enabled": detect_enabled,
                "objects": objects,
                "snapshots_enabled": snapshots_enabled,
                "snapshots_bb": snapshots_bb,
                "snapshots_retain": snapshots_retain,
                "record_enabled": record_enabled,
                "record_alerts": record_alerts,
                "record_detections": record_detections,
            })

    def save_config(self):
        # --- MQTT ---
        mqtt_config = {
            "enabled": self.mqtt_enabled.isChecked()
        }
        if self.mqtt_enabled.isChecked():
            mqtt_config["host"] = self.mqtt_host.text()
            if self.mqtt_port.text():
                mqtt_config["port"] = int(self.mqtt_port.text())
            if self.mqtt_topic.text():
                mqtt_config["topic_prefix"] = self.mqtt_topic.text()

        # --- FFmpeg ---
        ffmpeg_config = {}
        if self.ffmpeg_group.isChecked():
            ffmpeg_config["hwaccel_args"] = self.ffmpeg_hwaccel.currentText()

        # --- Detectors ---
        detectors_config = {}
        for i in range(self.memryx_devices.value()):
            detectors_config[f"memx{i}"] = {
                "type": "memryx",
                "device": f"PCIe:{i}"
            }

        # --- Model ---
        if self.custom_group.isChecked():
            # Use custom width/height + path
            w = self.custom_width.value()
            h = self.custom_height.value()
            model_path = self.custom_path.text()
        else:
            # Use preset resolution selection
            w, h = self._parse_resolution(self.model_resolution.currentText())
            model_path = None  # no path unless the custom group is checked

        model_config = {
            "model_type": self.model_type.currentText(),
            "width": w,
            "height": h,
            "input_tensor": self.input_tensor.currentText(),
            "input_dtype": self.input_dtype.currentText(),
            "labelmap_path": self.labelmap_path.text()
        }
        if model_path:
            model_config["path"] = model_path

        # --- Camera ---
        cameras_config = {}
        for cam in self.camera_tabs:
            roles = []
            if cam["role_detect"].isChecked():
                roles.append("detect")
            if cam["role_record"].isChecked():
                roles.append("record")

            cameras_config[cam["camera_name"].text()] = {
                "ffmpeg": {"inputs": [{"path": cam["camera_url"].text(), "roles": roles}]},
                "detect": {
                    "width": cam["detect_width"].value(),
                    "height": cam["detect_height"].value(),
                    "fps": cam["detect_fps"].value(),
                    "enabled": cam["detect_enabled"].isChecked(),
                },
                "objects": {
                    "track": [o.strip() for o in cam["objects"].toPlainText().split(",") if o.strip()]
                },
                "snapshots": {
                    "enabled": cam["snapshots_enabled"].isChecked(),
                    "bounding_box": cam["snapshots_bb"].isChecked(),
                    "retain": {"default": cam["snapshots_retain"].value()},
                },
                "record": {
                    "enabled": cam["record_enabled"].isChecked(),
                    "alerts": {"retain": {"days": cam["record_alerts"].value()}},
                    "detections": {"retain": {"days": cam["record_detections"].value()}},
                },
            }

        config = {
            "mqtt": mqtt_config,
            "detectors": detectors_config,
            "model": model_config,
        }

        if ffmpeg_config:
            config["ffmpeg"] = ffmpeg_config

        config["cameras"] = cameras_config
        config["version"] = "0.17-0"

        # --- Auto save path ---
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        os.makedirs(config_dir, exist_ok=True)

        save_path = os.path.join(config_dir, "config.yaml")

        # Always overwrite the existing config
        with open(save_path, "w") as f:
            yaml.dump(
                config, 
                f, 
                Dumper=MyDumper, 
                default_flow_style=False, 
                sort_keys=False
            )

        print(f"[SUCCESS] Config saved to {save_path}")

        self.config_saved = True

        # Exit with code 0 (normal save)
        QApplication.instance().exit(0)

    def write_default_config(self):
        """Write a default config.yaml skeleton if user never saved manually"""
        default_config_text = """\
    mqtt:
    enabled: false  # Set this to true if using MQTT for event triggers

    detectors:
    memx0:
        type: memryx
        device: PCIe:0
    # memx1:
    #   type: memryx
    #   device: PCIe:1   # Add more devices if available

    model:
    model_type: yolo-generic   # Options: yolo-generic, yolonas, yolox, ssd
    width: 320
    height: 320
    input_tensor: nchw
    input_dtype: float
    # path: /config/yolo-generic.zip   # Model is normally fetched via runtime
    labelmap_path: /labelmap/coco-80.txt

    cameras:
    cam1:
        ffmpeg:
        inputs:
            - path: rtsp://<username>:<password>@<ip>:<port>/...
            roles:
                - detect
                - record
        detect:
        width: 1920
        height: 1080
        fps: 20
        enabled: true

        objects:
        track:
            - person
            - car
            - dog
            # add more objects here

        snapshots:
        enabled: false
        bounding_box: true
        retain:
            default: 1   # keep snapshots for 1 day

        record:
        enabled: false
        alerts:
            retain:
            days: 1
        detections:
            retain:
            days: 1
        continuous:
            days: 1
        motion:
            days: 0

    version: 0.17-0
    """

        # --- Auto save path ---
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        os.makedirs(config_dir, exist_ok=True)

        save_path = os.path.join(config_dir, "config.yaml")

        with open(save_path, "w") as f:
            f.write(default_config_text)

        return save_path

    def closeEvent(self, event):
        """Triggered when the window closes"""
        # Only show message and exit with code 1 if this is a direct window close
        # (not from Save Config or Advanced Settings)
        if self.config_saved:
            # Normal close after saving
            event.accept()
            return
            
        # Check if config.yaml exists
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        config_path = os.path.join(config_dir, "config.yaml")
        
        save_path = config_path
        if not os.path.exists(config_path):
            # If no config exists, write defaults
            save_path = self.write_default_config()
            
        # Show info about the config file
        QMessageBox.information(
            self,
            "Config File Information",
            f"No configuration was saved manually.\n\n"
            f"A default `config.yaml` file is available at:\n{save_path}\n\n"
            f"👉 Please edit this file if you wish to make changes."
        )
                
        # Exit with code 1 to indicate window was closed without saving
        QApplication.instance().exit(1)
        event.accept()

    def load_existing_config(self):
        """Load values from existing config.yaml if it exists"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(script_dir, "frigate", "config")
        config_path = os.path.join(config_dir, "config.yaml")

        if not os.path.exists(config_path):
            return False

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                return False

            # Load MQTT settings
            if "mqtt" in config:
                mqtt = config["mqtt"]
                self.mqtt_enabled.setChecked(mqtt.get("enabled", False))
                if mqtt.get("host"):
                    self.mqtt_host.setText(mqtt["host"])
                if mqtt.get("port"):
                    self.mqtt_port.setText(str(mqtt["port"]))
                if mqtt.get("topic_prefix"):
                    self.mqtt_topic.setText(mqtt["topic_prefix"])

            # Load FFmpeg settings
            if "ffmpeg" in config:
                self.ffmpeg_group.setChecked(True)
                if "hwaccel_args" in config["ffmpeg"]:
                    preset = config["ffmpeg"]["hwaccel_args"]
                    index = self.ffmpeg_hwaccel.findText(preset)
                    if index >= 0:
                        self.ffmpeg_hwaccel.setCurrentIndex(index)

            # Load Detector settings
            if "detectors" in config:
                detectors = config["detectors"]
                # Count memryx devices in config
                memx_count = sum(1 for key in detectors if key.startswith("memx"))
                self.memryx_devices.setValue(memx_count)

            # Load Model settings
            if "model" in config:
                model = config["model"]
                # Set model type
                if "model_type" in model:
                    index = self.model_type.findText(model["model_type"])
                    if index >= 0:
                        self.model_type.setCurrentIndex(index)

                # If custom path exists, enable custom group and set path
                if "path" in model:
                    self.custom_group.setChecked(True)
                    self.custom_path.setText(model["path"])
                    if "width" in model and "height" in model:
                        self.custom_width.setValue(model["width"])
                        self.custom_height.setValue(model["height"])
                else:
                    # Use resolution from config
                    self.custom_group.setChecked(False)
                    if "width" in model and "height" in model:
                        resolution = f"{model['width']} x {model['height']}"
                        index = self.model_resolution.findText(resolution)
                        if index >= 0:
                            self.model_resolution.setCurrentIndex(index)

                # Set other model parameters
                if "input_tensor" in model:
                    index = self.input_tensor.findText(model["input_tensor"])
                    if index >= 0:
                        self.input_tensor.setCurrentIndex(index)
                
                if "input_dtype" in model:
                    index = self.input_dtype.findText(model["input_dtype"])
                    if index >= 0:
                        self.input_dtype.setCurrentIndex(index)

                if "labelmap_path" in model:
                    self.labelmap_path.setText(model["labelmap_path"])

            # Load Camera settings
            if "cameras" in config:
                cameras = config["cameras"]
                # Set number of cameras
                self.cams_count.setValue(len(cameras))
                
                # Load each camera's settings
                for i, (cam_name, cam_config) in enumerate(cameras.items()):
                    if i >= len(self.camera_tabs):
                        continue

                    cam_tab = self.camera_tabs[i]
                    
                    # Basic settings
                    cam_tab["camera_name"].setText(cam_name)
                    
                    # Get RTSP URL from inputs
                    if "ffmpeg" in cam_config and "inputs" in cam_config["ffmpeg"]:
                        inputs = cam_config["ffmpeg"]["inputs"]
                        if inputs and "path" in inputs[0]:
                            cam_tab["camera_url"].setText(inputs[0]["path"])
                        
                        # Set roles
                        if inputs and "roles" in inputs[0]:
                            roles = inputs[0]["roles"]
                            cam_tab["role_detect"].setChecked("detect" in roles)
                            cam_tab["role_record"].setChecked("record" in roles)

                    # Detect settings
                    if "detect" in cam_config:
                        detect = cam_config["detect"]
                        if "width" in detect:
                            cam_tab["detect_width"].setValue(detect["width"])
                        if "height" in detect:
                            cam_tab["detect_height"].setValue(detect["height"])
                        if "fps" in detect:
                            cam_tab["detect_fps"].setValue(detect["fps"])
                        if "enabled" in detect:
                            cam_tab["detect_enabled"].setChecked(detect["enabled"])

                    # Objects to track
                    if "objects" in cam_config and "track" in cam_config["objects"]:
                        objects = cam_config["objects"]["track"]
                        cam_tab["objects"].setPlainText(",".join(objects))

                    # Snapshots settings
                    if "snapshots" in cam_config:
                        snapshots = cam_config["snapshots"]
                        if "enabled" in snapshots:
                            cam_tab["snapshots_enabled"].setChecked(snapshots["enabled"])
                        if "bounding_box" in snapshots:
                            cam_tab["snapshots_bb"].setChecked(snapshots["bounding_box"])
                        if "retain" in snapshots and "default" in snapshots["retain"]:
                            cam_tab["snapshots_retain"].setValue(snapshots["retain"]["default"])

                    # Record settings
                    if "record" in cam_config:
                        record = cam_config["record"]
                        if "enabled" in record:
                            cam_tab["record_enabled"].setChecked(record["enabled"])
                        if "alerts" in record and "retain" in record["alerts"] and "days" in record["alerts"]["retain"]:
                            cam_tab["record_alerts"].setValue(record["alerts"]["retain"]["days"])
                        if "detections" in record and "retain" in record["detections"] and "days" in record["detections"]["retain"]:
                            cam_tab["record_detections"].setValue(record["detections"]["retain"]["days"])

            return True

        except Exception as e:
            print(f"Error loading config: {str(e)}")
            return False

    def show_advanced_settings(self):
        dialog = AdvancedSettingsDialog(self)
        result = dialog.exec()
        
        if result == QDialog.Accepted:  # OK button clicked
            self.advanced_settings_exit = True
            # Check if config.yaml exists, if not create with defaults
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(script_dir, "frigate", "config")
            config_path = os.path.join(config_dir, "config.yaml")
            
            if not os.path.exists(config_path):
                self.write_default_config()
            
            QApplication.instance().exit(2)  # Exit with code 2 for advanced settings

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConfigGUI()
    window.show()
    sys.exit(app.exec())