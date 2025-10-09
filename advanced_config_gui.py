#!/usr/bin/env python3
"""
Advanced Configuration GUI for Frigate + MemryX
A comprehensive GUI for advanced Frigate configuration management
"""

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
                               QPushButton, QCheckBox, QComboBox, QSpinBox,
                               QFileDialog, QTextEdit, QTabWidget, QFormLayout, QListWidget, 
                               QListWidgetItem, QHBoxLayout, QFrame, QMessageBox, QGroupBox, QButtonGroup, QRadioButton, QDialog, QScrollArea,
                               QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QSizePolicy) 
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, Signal, QThread, QTimer
import yaml
import sys
import os
import glob
import socket
import struct
import uuid
import time
import threading
import atexit
import traceback
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import re

# Import ONVIF discovery classes from simple_camera_gui instead of duplicating
try:
    from camera_gui import (
        ONVIFDiscoveryWorker,
        ONVIFDiscoveryDialog,  # This is the correct class name
        SimpleCameraGUI,
        cleanup_all_threads,
        _active_onvif_workers
    )
    ONVIF_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import ONVIF classes from simple_camera_gui: {e}")
    ONVIF_AVAILABLE = False

class MyDumper(yaml.Dumper):
    def write_line_break(self, data=None):
        super().write_line_break(data)
        # add an extra line break for top-level keys
        if len(self.indents) == 1:  
            super().write_line_break()
    
    @staticmethod
    def add_camera_spacing(yaml_content):
        """Add extra spacing between camera entries in YAML content"""
        lines = yaml_content.split('\n')
        result_lines = []
        in_cameras_section = False
        camera_indent_level = None
        
        for i, line in enumerate(lines):
            # Check if we're entering the cameras section
            if line.strip() == 'cameras:' or line.rstrip().endswith('cameras:'):
                in_cameras_section = True
                camera_indent_level = None
                result_lines.append(line)
                continue
            
            # Check if we've left the cameras section (new top-level key)
            if in_cameras_section and line and not line.startswith(' ') and not line.startswith('\t') and ':' in line:
                in_cameras_section = False
                camera_indent_level = None
            
            if in_cameras_section and line.strip():
                # Determine camera entry indent level (first camera sets the pattern)
                if camera_indent_level is None and line.startswith(' ') and ':' in line:
                    camera_indent_level = len(line) - len(line.lstrip())
                
                # If this is a camera entry (same indent as first camera, has colon)
                if (camera_indent_level is not None and 
                    line.startswith(' ' * camera_indent_level) and 
                    not line.startswith(' ' * (camera_indent_level + 1)) and
                    ':' in line and
                    line.strip().endswith(':')):
                    
                    # Add blank line before camera entry (except for the first one)
                    if result_lines and result_lines[-1].strip():  # Don't add if previous line is already blank
                        result_lines.append('')
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)

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
        
        # Modify OK button to close appropriately (indicating manual edit)
        def handle_ok_click():
            self.accept()
            # Get parent ConfigGUI to use smart_close
            if hasattr(self.parent(), 'smart_close'):
                self.parent().smart_close(2)
            else:
                # Fallback for standalone mode
                QApplication.instance().exit(2)
        
        ok_btn.clicked.connect(handle_ok_click)
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
        
        # Set window properties - make responsive
        self.setMinimumSize(600, 400)  # Smaller minimum size
        self.resize(1000, 850)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Main layout with scroll area for responsive design
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        main_scroll.setWidget(scroll_content)
        
        # Main dialog layout
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_scroll)
        
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

        # Global Layout with responsive setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Smaller margins for compact layout
        layout.setSpacing(5)

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
        # Tabs with Responsive Design
        ################################
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tabs.setTabPosition(QTabWidget.North)
        
        # Make tabs responsive to content
        tabs.setElideMode(Qt.ElideRight)  # Elide tab text if window is too narrow

        # --- MQTT Tab
        self.mqtt_enabled = QCheckBox("Enable MQTT")
        self.mqtt_enabled.stateChanged.connect(self.toggle_mqtt_fields)

        self.mqtt_host = QLineEdit()
        self.mqtt_host.setPlaceholderText("mqtt.server.com")
        self.mqtt_port = QLineEdit("1883")
        self.mqtt_topic = QLineEdit("frigate")

        # Create MQTT tab with scroll area
        mqtt_scroll = QScrollArea()
        mqtt_scroll.setWidgetResizable(True)
        mqtt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        mqtt_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        mqtt_content = QWidget()
        mqtt_main_layout = QVBoxLayout(mqtt_content)
        mqtt_main_layout.setContentsMargins(10, 10, 10, 10)
        mqtt_main_layout.setSpacing(10)
        
        # MQTT form
        mqtt_form_widget = QWidget()
        mqtt_layout = QFormLayout(mqtt_form_widget)
        mqtt_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        mqtt_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        
        # Make form fields responsive
        self.mqtt_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mqtt_port.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mqtt_topic.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        mqtt_layout.addRow("Enable", self.mqtt_enabled)
        mqtt_layout.addRow("Host", self.mqtt_host)
        mqtt_layout.addRow("Port", self.mqtt_port)
        mqtt_layout.addRow("Topic Prefix", self.mqtt_topic)
        
        mqtt_main_layout.addWidget(mqtt_form_widget)

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

        # Add docs to main mqtt layout\n        mqtt_main_layout.addWidget(mqtt_docs_container)\n        mqtt_main_layout.addStretch()  # Add stretch to push content to top\n        \n        # Set scroll area widget\n        mqtt_scroll.setWidget(mqtt_content)

        tabs.addTab(mqtt_scroll, "MQTT")

        # --- Detector Tab (only MemryX) with Scroll Area ---
        detector_scroll = QScrollArea()
        detector_scroll.setWidgetResizable(True)
        detector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        detector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        detector_content = QWidget()
        detector_main_layout = QVBoxLayout(detector_content)
        detector_main_layout.setContentsMargins(10, 10, 10, 10)
        detector_main_layout.setSpacing(10)
        
        # Detector form
        detector_form_widget = QWidget()
        detector_layout = QFormLayout(detector_form_widget)
        detector_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

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
        self.memryx_devices.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # GroupBox to show available devices
        device_box = QGroupBox("Available Devices")
        device_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
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
        self.custom_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Path row + custom width/height inside the group
        custom_v = QVBoxLayout()
        path_row = QHBoxLayout()
        self.custom_path = QLineEdit("/config/yolo.zip")
        self.custom_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        path_row.addWidget(self.custom_path)
        path_row.addWidget(self.browse_btn)
        custom_v.addLayout(path_row)

        # Custom width/height spinboxes (enabled only when group is checked)
        self.custom_width = QSpinBox();  self.custom_width.setRange(1, 8192); self.custom_width.setValue(320)
        self.custom_width.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.custom_height = QSpinBox(); self.custom_height.setRange(1, 8192); self.custom_height.setValue(320)
        self.custom_height.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        custom_form = QFormLayout()
        custom_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
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

        # --- Camera Tab with Responsive Design ---
        self.camera_tabs = []  # store camera widget sets

        # Create camera tab with scroll area
        camera_scroll = QScrollArea()
        camera_scroll.setWidgetResizable(True)
        camera_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        camera_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        cams_tab = QWidget()
        cams_layout = QVBoxLayout(cams_tab)
        cams_layout.setContentsMargins(5, 5, 5, 5)

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
        setup_guide_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
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
        self.cams_subtabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cams_layout.addWidget(self.cams_subtabs)
        
        # Set camera scroll area
        camera_scroll.setWidget(cams_tab)

        tabs.addTab(detector_widget, "🧠 Detector")
        tabs.addTab(model_widget, "📦 Model")
        tabs.addTab(camera_scroll, "🎥 Cameras")
        tabs.addTab(ffmpeg_widget, "🎬 FFmpeg")
        tabs.addTab(mqtt_scroll, "🟢 MQTT")

        # Build initial camera tabs
        self.camera_tabs = []  # Initialize camera tabs list
        self.previous_camera_count = 1  # Track previous count for auto-switching
        
        # Load existing cameras from config if available (this will rebuild tabs with data)
        self.load_existing_cameras()

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

        # Load existing configuration for other settings (non-camera)
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

    def load_existing_cameras(self):
        """Load existing camera configurations from config.yaml if available"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "frigate", "config", "config.yaml")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_content = f.read()
                    
                # Check if the file is empty
                if not config_content.strip():
                    print("Config file is empty, using default configuration")
                    self.rebuild_camera_tabs(self.cams_count.value())
                    return
                
                # Try parsing with yaml.safe_load
                try:
                    config = yaml.safe_load(config_content)
                except yaml.YAMLError as yaml_error:
                    print(f"YAML parsing error: {yaml_error}")
                    self.rebuild_camera_tabs(self.cams_count.value())
                    return
                
                # Check if config is valid and has cameras
                if config and isinstance(config, dict) and "cameras" in config and config["cameras"]:
                    cameras = config["cameras"]
                    
                    # Validate cameras structure
                    if isinstance(cameras, dict) and cameras:
                        # Set camera count to match existing cameras
                        self.cams_count.setValue(len(cameras))
                        
                        # Rebuild tabs with existing camera data
                        self.rebuild_camera_tabs_with_existing_data(cameras)
                        return
                    else:
                        print("Invalid cameras structure in config file")
                        
            except FileNotFoundError:
                print(f"Config file not found: {config_path}")
            except PermissionError:
                print(f"Permission denied reading config file: {config_path}")
            except Exception as e:
                print(f"Error loading existing cameras: {e}")
                traceback.print_exc()
        
        # Fallback: build default single camera tab
        print("Using default camera configuration")
        self.rebuild_camera_tabs(self.cams_count.value())

    def rebuild_camera_tabs_with_existing_data(self, existing_cameras):
        """Rebuild camera tabs with existing camera data"""
        camera_list = list(existing_cameras.items())
        
        # Clear existing tabs
        self.cams_subtabs.clear()
        self.camera_tabs.clear()
        
        for idx, (camera_name, camera_config) in enumerate(camera_list):
            # Create scroll area for each camera tab
            cam_scroll = QScrollArea()
            cam_scroll.setWidgetResizable(True)
            cam_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            cam_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            cam_widget = QWidget()
            form = QFormLayout(cam_widget)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            
            # Extract existing data from config
            ffmpeg_inputs = camera_config.get("ffmpeg", {}).get("inputs", [])
            camera_url = ffmpeg_inputs[0].get("path", "") if ffmpeg_inputs else ""
            
            # Parse RTSP URL to extract username, password, IP for consistency
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
                            ip_address = rest.split("/")[0]
                except:
                    pass  # Keep defaults if parsing fails
            
            # Extract roles from inputs
            roles = ffmpeg_inputs[0].get("roles", []) if ffmpeg_inputs else []
            role_detect = "detect" in roles
            role_record = "record" in roles
            
            # Extract detect settings
            detect_config = camera_config.get("detect", {})
            detect_width = detect_config.get("width", 2560)
            detect_height = detect_config.get("height", 1440)
            detect_fps = detect_config.get("fps", 5)
            detect_enabled = detect_config.get("enabled", True)
            
            # Extract objects
            objects_list = camera_config.get("objects", {}).get("track", [])
            objects_text = ",".join(objects_list) if objects_list else "person,car,dog"
            
            # Extract snapshot settings
            snapshots_config = camera_config.get("snapshots", {})
            snapshots_enabled = snapshots_config.get("enabled", True)
            snapshots_bb = snapshots_config.get("bounding_box", True)
            snapshots_retain = snapshots_config.get("retain", {}).get("default", 14)
            
            # Extract recording settings
            record_config = camera_config.get("record", {})
            record_enabled = record_config.get("enabled", False)
            record_alerts_days = record_config.get("alerts", {}).get("retain", {}).get("days", 7)
            record_detections_days = record_config.get("detections", {}).get("retain", {}).get("days", 3)
            
            # Create form fields with existing data
            camera_name_field = QLineEdit(camera_name)
            camera_name_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Add IP/username/password fields for consistency with rebuild_camera_tabs
            ip_address_field = QLineEdit(ip_address)
            ip_address_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            ip_address_field.setPlaceholderText("192.168.1.100")
            
            username_field = QLineEdit(username)
            username_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            username_field.setPlaceholderText("admin")
            
            password_field = QLineEdit(password)
            password_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            password_field.setPlaceholderText("password")
            
            camera_url_field = QLineEdit(camera_url)
            camera_url_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            camera_url_field.setPlaceholderText("rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0")
            
            # Camera roles
            role_detect_field = QCheckBox("Detect")
            role_detect_field.setChecked(role_detect)
            role_record_field = QCheckBox("Record")
            role_record_field.setChecked(role_record)
            
            # Detect settings
            detect_width_field = QSpinBox()
            detect_width_field.setRange(320, 3840)
            detect_width_field.setValue(detect_width)
            detect_width_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            detect_height_field = QSpinBox()
            detect_height_field.setRange(240, 2160)
            detect_height_field.setValue(detect_height)
            detect_height_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            detect_fps_field = QSpinBox()
            detect_fps_field.setRange(1, 30)
            detect_fps_field.setValue(detect_fps)
            detect_fps_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            detect_enabled_field = QCheckBox("Enable Detection")
            detect_enabled_field.setChecked(detect_enabled)
            
            # Objects
            objects_field = QTextEdit(objects_text)
            objects_field.setMaximumHeight(80)
            objects_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Snapshots
            snapshots_enabled_field = QCheckBox("Enable Snapshots")
            snapshots_enabled_field.setChecked(snapshots_enabled)
            
            snapshots_bb_field = QCheckBox("Bounding Box")
            snapshots_bb_field.setChecked(snapshots_bb)
            
            snapshots_retain_field = QSpinBox()
            snapshots_retain_field.setRange(1, 365)
            snapshots_retain_field.setValue(snapshots_retain)
            snapshots_retain_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Recording
            record_enabled_field = QCheckBox("Enable Recording")
            record_enabled_field.setChecked(record_enabled)
            
            record_alerts_field = QSpinBox()
            record_alerts_field.setRange(0, 365)
            record_alerts_field.setValue(record_alerts_days)
            record_alerts_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            record_detections_field = QSpinBox()
            record_detections_field.setRange(0, 365)
            record_detections_field.setValue(record_detections_days)
            record_detections_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Layout form with responsive design
            form.addRow("Camera Name:", camera_name_field)
            form.addRow("IP Address:", ip_address_field)
            form.addRow("Username:", username_field)
            form.addRow("Password:", password_field)
            form.addRow("Camera URL:", camera_url_field)
            
            # Roles layout
            roles_layout = QHBoxLayout()
            roles_layout.addWidget(role_detect_field)
            roles_layout.addWidget(role_record_field)
            roles_layout.addStretch()
            form.addRow("Roles:", roles_layout)
            
            # Detect settings
            detect_group = QGroupBox("Detection Settings")
            detect_layout = QFormLayout(detect_group)
            detect_layout.addRow("Width:", detect_width_field)
            detect_layout.addRow("Height:", detect_height_field)
            detect_layout.addRow("FPS:", detect_fps_field)
            detect_layout.addRow("", detect_enabled_field)
            form.addRow(detect_group)
            
            form.addRow("Objects to Track:", objects_field)
            
            # Snapshots
            snapshots_group = QGroupBox("Snapshots")
            snapshots_layout = QFormLayout(snapshots_group)
            snapshots_layout.addRow("", snapshots_enabled_field)
            snapshots_layout.addRow("", snapshots_bb_field)
            snapshots_layout.addRow("Retain (days):", snapshots_retain_field)
            form.addRow(snapshots_group)
            
            # Recording
            recording_group = QGroupBox("Recording")
            recording_layout = QFormLayout(recording_group)
            recording_layout.addRow("", record_enabled_field)
            recording_layout.addRow("Alert Days:", record_alerts_field)
            recording_layout.addRow("Detection Days:", record_detections_field)
            form.addRow(recording_group)
            
            # Add delete button (same as in rebuild_camera_tabs)
            delete_btn = QPushButton("🗑️ Delete Camera")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                    margin-top: 10px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #bd2130;
                }
            """)
            
            # Connect delete button with closure to capture current index
            def create_delete_handler(camera_index):
                return lambda: self.delete_camera(camera_index)
            
            delete_btn.clicked.connect(create_delete_handler(idx))
            
            form.addRow("", delete_btn)  # Empty label for the delete button row
            
            # Store references
            cam_data = {
                "camera_name": camera_name_field,
                "ip_address": ip_address_field,
                "username": username_field,
                "password": password_field,
                "camera_url": camera_url_field,
                "role_detect": role_detect_field,
                "role_record": role_record_field,
                "detect_width": detect_width_field,
                "detect_height": detect_height_field,
                "detect_fps": detect_fps_field,
                "detect_enabled": detect_enabled_field,
                "objects": objects_field,
                "snapshots_enabled": snapshots_enabled_field,
                "snapshots_bb": snapshots_bb_field,
                "snapshots_retain": snapshots_retain_field,
                "record_enabled": record_enabled_field,
                "record_alerts": record_alerts_field,
                "record_detections": record_detections_field,
                "delete_btn": delete_btn,  # Add delete button reference
            }
            
            self.camera_tabs.append(cam_data)
            
            # Set scroll area widget and add to tabs
            cam_scroll.setWidget(cam_widget)
            
            # Add tab
            camera_display_name = camera_name if camera_name else f"Camera {idx + 1}"
            self.cams_subtabs.addTab(cam_scroll, camera_display_name)
        
        # Update delete button visibility after all cameras are loaded
        self.update_delete_button_visibility()

    def rebuild_camera_tabs(self, count: int):
        # Step 1: Save existing values
        saved_data = []
        for cam in self.camera_tabs:
            saved_data.append({
                "camera_name": cam["camera_name"].text(),
                "ip_address": cam["ip_address"].text(),
                "username": cam["username"].text(), 
                "password": cam["password"].text(),
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
            # Create scroll area for each camera tab
            cam_scroll = QScrollArea()
            cam_scroll.setWidgetResizable(True)
            cam_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            cam_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            
            cam_widget = QWidget()
            form = QFormLayout(cam_widget)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setContentsMargins(10, 10, 10, 10)
            form.setSpacing(8)

            # Restore data if exists, else defaults
            data = saved_data[idx] if idx < len(saved_data) else {}

            # Prioritize saved camera name, then config, then default
            if data.get("camera_name"):
                # Use saved camera name if available
                camera_name_text = data["camera_name"]
            else:
                # Fall back to config name or default
                camera_name_text = camera_names[idx] if idx < len(camera_names) else f"camera_{idx+1}"
            
            camera_name = QLineEdit(camera_name_text)
            camera_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Enhanced camera connection fields (IP, Username, Password first)
            ip_address = QLineEdit(data.get("ip_address", ""))
            ip_address.setPlaceholderText("192.168.1.100")
            ip_address.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            username = QLineEdit(data.get("username", ""))
            username.setPlaceholderText("admin")
            username.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            password = QLineEdit(data.get("password", ""))
            # password.setEchoMode(QLineEdit.Password)  # Remove password hiding
            password.setPlaceholderText("password")
            password.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Camera URL field (now auto-generated)
            camera_url = QLineEdit(data.get("camera_url", ""))
            camera_url.setPlaceholderText("Auto-generated RTSP URL will appear here")
            camera_url.setEnabled(False)  # Disabled by default for auto-generation
            camera_url.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Discover Camera button (will be placed next to IP address)
            discover_btn = QPushButton("🔍 Discover Camera")
            discover_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            discover_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196f3;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1976d2;
                }
                QPushButton:pressed {
                    background-color: #0d47a1;
                }
            """)
            
            # IP Address layout with Discover button
            ip_layout = QHBoxLayout()
            ip_layout.addWidget(ip_address)
            ip_layout.addWidget(discover_btn)
            ip_layout.setSpacing(10)
            ip_widget = QWidget()
            ip_widget.setLayout(ip_layout)
            
            # Manual URL toggle (will be placed near Camera URL field)
            manual_url_btn = QPushButton("✏️ Manual URL")
            manual_url_btn.setCheckable(True)
            manual_url_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            manual_url_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff9800;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #f57c00;
                }
                QPushButton:checked {
                    background-color: #e65100;
                }
            """)
            
            # Camera URL layout with Manual URL button
            camera_url_layout = QHBoxLayout()
            camera_url_layout.addWidget(camera_url)
            camera_url_layout.addWidget(manual_url_btn)
            camera_url_layout.setSpacing(10)
            camera_url_widget = QWidget()
            camera_url_widget.setLayout(camera_url_layout)
            
            # Hidden manufacturer selection (for unknown manufacturers)
            manufacturer_frame = QFrame()
            manufacturer_frame.hide()
            manufacturer_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # Allow horizontal expansion
            manufacturer_frame.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 2px solid #ffeaa7;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 10px 0;
                }
            """)
            manufacturer_layout = QVBoxLayout(manufacturer_frame)
            manufacturer_layout.setSpacing(15)
            manufacturer_layout.setContentsMargins(20, 20, 20, 20)
            
            manufacturer_label = QLabel("🏢 Manufacturer not detected automatically. Please select:")
            manufacturer_label.setStyleSheet("""
                QLabel {
                    font-weight: bold; 
                    color: #856404;
                    font-size: 14px;
                    margin-bottom: 8px;
                    padding: 5px;
                }
            """)
            
            manufacturer_combo = QComboBox()
            manufacturer_combo.addItems([
                "Select manufacturer...",
                "Hikvision", "Dahua", "Amcrest", "Reolink", 
                "Axis", "Foscam", "Vivotek", "Bosch", 
                "Sony", "Uniview", "-- None of the above --"
            ])
            manufacturer_combo.setMinimumWidth(400)  # Increased width for full text visibility
            manufacturer_combo.setMinimumHeight(35)  # Ensure proper height
            manufacturer_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # Allow horizontal expansion
            manufacturer_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)  # Auto-adjust to content
            manufacturer_combo.setStyleSheet("""
                QComboBox {
                    padding: 10px 15px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    background: white;
                    min-height: 30px;
                    min-width: 400px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QComboBox:focus {
                    border: 2px solid #2c6b7d;
                    background: #f8f9fa;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 25px;
                    padding-right: 5px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 6px solid transparent;
                    border-right: 6px solid transparent;
                    border-top: 8px solid #666;
                    width: 0;
                    height: 0;
                    margin-right: 5px;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 2px solid #ddd;
                    border-radius: 5px;
                    selection-background-color: #2c6b7d;
                    selection-color: white;
                    outline: none;
                    min-width: 400px;
                    padding: 5px;
                }
                QComboBox QAbstractItemView::item {
                    padding: 12px 15px;
                    border-bottom: 1px solid #eee;
                    min-height: 25px;
                    font-size: 14px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #f0f8ff;
                    color: #2c6b7d;
                }
                QComboBox QAbstractItemView::item:selected {
                    background-color: #2c6b7d;
                    color: white;
                }
            """)
            
            manufacturer_layout.addWidget(manufacturer_label)
            manufacturer_layout.addWidget(manufacturer_combo)
            
            # Manual URL section (hidden by default) - reusing proven code from simple_camera_gui.py
            manual_url_section = QFrame()
            manual_url_section.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 5px;
                }
            """)
            manual_url_layout = QVBoxLayout(manual_url_section)
            manual_url_header = QLabel("✏️ Enter Custom Camera URL:")
            manual_url_header.setStyleSheet("font-weight: bold; color: #495057; font-size: 14px;")
            manual_url_layout.addWidget(manual_url_header)
            
            custom_url_field = QLineEdit()
            custom_url_field.setPlaceholderText("rtsp://username:password@ip:554/your/camera/path")
            custom_url_field.setStyleSheet("""
                QLineEdit {
                    padding: 6px 10px;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    font-family: monospace;
                }
            """)
            manual_url_layout.addWidget(custom_url_field)
            manual_url_section.hide()  # Hidden by default
            manufacturer_layout.addWidget(manual_url_section)
            
            # Store references for easy access
            camera_url.manufacturer_selection_frame = manufacturer_frame
            camera_url.manufacturer_combo = manufacturer_combo
            camera_url.manual_url_section = manual_url_section
            camera_url.custom_url_field = custom_url_field
            camera_url.manual_url_header = manual_url_header
            
            # Other form fields
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
            detect_fps.setValue(data.get("detect_fps", 5))
            detect_enabled = QCheckBox(); detect_enabled.setChecked(data.get("detect_enabled", True))

            objects = QTextEdit(data.get("objects", "person,car,dog"))

            snapshots_enabled = QCheckBox(); snapshots_enabled.setChecked(data.get("snapshots_enabled", False))
            snapshots_bb = QCheckBox(); snapshots_bb.setChecked(data.get("snapshots_bb", True))
            snapshots_retain = QSpinBox(); snapshots_retain.setRange(0, 1000)
            snapshots_retain.setValue(data.get("snapshots_retain", 0))

            record_enabled = QCheckBox(); record_enabled.setChecked(data.get("record_enabled", False))
            record_alerts = QSpinBox(); record_alerts.setRange(0, 1000)
            record_alerts.setValue(data.get("record_alerts", 0))
            record_detections = QSpinBox(); record_detections.setRange(0, 1000)
            record_detections.setValue(data.get("record_detections", 0))

            # Layout form with enhanced camera fields
            form.addRow("Camera Name", camera_name)
            form.addRow("IP Address", ip_widget)  # IP address with discover button
            form.addRow("Username", username)
            form.addRow("Password", password)
            form.addRow("Manufacturer", manufacturer_frame)  # Manufacturer selection with proper label
            form.addRow("Camera URL", camera_url_widget)  # Camera URL with manual URL button
            
            # RTSP info note
            rtsp_note = QLabel(
                "ℹ️ Use 'Discover Camera' for automatic setup, or toggle 'Manual URL' for custom RTSP URLs"
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

            # Add delete button (only show if more than 1 camera)
            delete_btn = QPushButton("🗑️ Delete Camera")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                    margin-top: 10px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #bd2130;
                }
            """)
            
            # Connect delete button with closure to capture current index
            def create_delete_handler(camera_index):
                return lambda: self.delete_camera(camera_index)
            
            delete_btn.clicked.connect(create_delete_handler(idx))
            
            form.addRow("", delete_btn)  # Empty label for the delete button row

            # Enhanced Signal Connections for Auto URL Generation
            def setup_field_connections():
                """Setup signal connections for auto URL generation"""
                # Connect discover button
                discover_btn.clicked.connect(lambda: self.discover_camera(ip_address, username, password, camera_url))
                
                # Connect manual URL toggle
                manual_url_btn.toggled.connect(lambda checked: self.toggle_manual_url(camera_url, checked))
                
                # Connect manufacturer selection with proper closure
                def on_manufacturer_changed(text):
                    """Handle manufacturer selection with proper variable capture"""
                    try:
                        self.on_manufacturer_selected(text, ip_address, username, password, camera_url, manufacturer_frame)
                    except Exception as e:
                        print(f"Error in manufacturer selection: {e}")
                
                manufacturer_combo.currentTextChanged.connect(on_manufacturer_changed)
                
                # Also connect via currentIndexChanged for better reliability
                def on_manufacturer_index_changed(index):
                    """Handle manufacturer selection by index"""
                    try:
                        text = manufacturer_combo.itemText(index)
                        if text and text != "Select manufacturer...":
                            self.on_manufacturer_selected(text, ip_address, username, password, camera_url, manufacturer_frame)
                    except Exception as e:
                        print(f"Error in manufacturer index selection: {e}")
                
                manufacturer_combo.currentIndexChanged.connect(on_manufacturer_index_changed)
                
                # Connect custom URL field changes
                def on_custom_url_changed():
                    """Handle custom URL field changes"""
                    try:
                        if hasattr(camera_url, 'custom_url_field'):
                            custom_text = camera_url.custom_url_field.text().strip()
                            if custom_text:
                                camera_url.setText(custom_text)
                                camera_url.setEnabled(True)  # Enable manual mode
                    except Exception as e:
                        print(f"Error in custom URL change: {e}")
                
                # Connect the custom URL field if it exists
                if hasattr(camera_url, 'custom_url_field'):
                    camera_url.custom_url_field.textChanged.connect(on_custom_url_changed)
                
                # Connect field changes for auto URL generation
                ip_address.textChanged.connect(lambda: self.update_rtsp_url(ip_address, username, password, camera_url))
                username.textChanged.connect(lambda: self.update_rtsp_url(ip_address, username, password, camera_url))
                password.textChanged.connect(lambda: self.update_rtsp_url(ip_address, username, password, camera_url))
            
            setup_field_connections()

            # Add dynamic tab name update
            def update_tab_name():
                new_name = camera_name.text()
                current_index = self.cams_subtabs.indexOf(cam_widget)
                self.cams_subtabs.setTabText(current_index, new_name)
            
            camera_name.textChanged.connect(update_tab_name)

            # Add to subtabs with the camera name
            cam_name = camera_name.text()
            self.cams_subtabs.addTab(cam_widget, cam_name)

            # Save refs (including new fields)
            self.camera_tabs.append({
                "camera_name": camera_name,
                "ip_address": ip_address,
                "username": username,
                "password": password,
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
                "delete_btn": delete_btn,  # Add delete button reference
            })
        
        # Auto-switch to the last tab if camera count increased
        if count > self.previous_camera_count:
            # Switch to the last (newest) camera tab
            last_tab_index = self.cams_subtabs.count() - 1
            if last_tab_index >= 0:
                self.cams_subtabs.setCurrentIndex(last_tab_index)
        
        # Update delete button visibility for all cameras
        self.update_delete_button_visibility()
        
        # Update previous count for next comparison
        self.previous_camera_count = count

    def update_delete_button_visibility(self):
        """Update visibility of delete buttons based on camera count"""
        show_delete = len(self.camera_tabs) > 1
        for cam in self.camera_tabs:
            if "delete_btn" in cam:
                cam["delete_btn"].setVisible(show_delete)

    def delete_camera(self, camera_index):
        """Delete a camera with confirmation dialog"""
        if len(self.camera_tabs) <= 1:
            QMessageBox.warning(self, "Cannot Delete", 
                              "Cannot delete the last camera. At least one camera is required.")
            return
        
        # Get camera name for confirmation dialog
        camera_name = "Unknown"
        if camera_index < len(self.camera_tabs):
            camera_name = self.camera_tabs[camera_index]["camera_name"].text()
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Delete Camera",
            f"Are you sure you want to delete camera '{camera_name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Decrease camera count (this will trigger rebuild_camera_tabs)
            current_count = self.cams_count.value()
            if current_count > 1:
                self.cams_count.setValue(current_count - 1)

    # Enhanced Camera Discovery Methods - Reusing code from simple_camera_gui.py
    def discover_camera(self, ip_field, username_field, password_field, url_field):
        """Launch ONVIF camera discovery dialog"""
        if not ONVIF_AVAILABLE:
            QMessageBox.warning(self, "ONVIF Not Available", 
                              "ONVIF discovery is not available. Please ensure simple_camera_gui.py is in the same directory.")
            return
            
        dialog = ONVIFDiscoveryDialog(self)  # Use the correct class name
        
        # Connect the selection signal to handle discovered camera
        dialog.camera_selected.connect(lambda camera_info: self.on_camera_discovered(
            camera_info, ip_field, username_field, password_field, url_field
        ))
        
        dialog.exec()

    def on_camera_discovered(self, camera_info, ip_field, username_field, password_field, url_field):
        """Handle discovered camera from ONVIF - reusing logic from simple_camera_gui.py"""
        try:
            # Always use fallback to avoid compatibility issues with different GUI structures
            self._fallback_on_camera_discovered(camera_info, ip_field, username_field, password_field, url_field)
            
        except Exception as e:
            QMessageBox.warning(self, "Discovery Error", f"Error processing discovered camera:\n{str(e)}")

    def _fallback_on_camera_discovered(self, camera_info, ip_field, username_field, password_field, url_field):
        """Fallback implementation for camera discovery handling"""
        try:
            # Temporarily block signals to prevent crashes during programmatic updates
            ip_field.blockSignals(True)
            username_field.blockSignals(True)
            password_field.blockSignals(True)
            
            # Fill in the discovered camera information
            ip_field.setText(camera_info['ip'])
            
            # Store manufacturer info for later URL generation
            if hasattr(ip_field, 'setProperty'):
                ip_field.setProperty('discovered_manufacturer', camera_info.get('manufacturer', 'Unknown'))
                ip_field.setProperty('rtsp_patterns', camera_info.get('rtsp_patterns', {}))
            
            # Also store on username and password fields for better access
            if hasattr(username_field, 'setProperty'):
                username_field.setProperty('discovered_manufacturer', camera_info.get('manufacturer', 'Unknown'))
                username_field.setProperty('rtsp_patterns', camera_info.get('rtsp_patterns', {}))
            if hasattr(password_field, 'setProperty'):
                password_field.setProperty('discovered_manufacturer', camera_info.get('manufacturer', 'Unknown'))
                password_field.setProperty('rtsp_patterns', camera_info.get('rtsp_patterns', {}))
            
            # Re-enable signals
            ip_field.blockSignals(False)
            username_field.blockSignals(False)
            password_field.blockSignals(False)
            
            # Show manufacturer-specific info in the message
            manufacturer_info = ""
            if camera_info.get('manufacturer', 'Unknown') != 'Unknown':
                manufacturer_info = f"\nManufacturer: {camera_info['manufacturer']}"
                if 'rtsp_patterns' in camera_info and camera_info['rtsp_patterns'].get('manufacturer_detected'):
                    manufacturer_info += "\n✅ Manufacturer-specific RTSP URL will be used"
            
            # If we discovered additional info, show a message
            QMessageBox.information(
                self, "Camera Discovered", 
                f"📹 Camera discovered successfully!\n\n"
                f"IP Address: {camera_info['ip']}\n"
                f"Name: {camera_info['name']}\n"
                f"Model: {camera_info['model']}{manufacturer_info}\n\n"
                "Please enter your camera username and password to complete the setup."
            )
            
            # Focus on username field for user input
            username_field.setFocus()
            
            # Handle manufacturer selection UI based on detection results
            if camera_info.get('manufacturer', 'Unknown') == 'Unknown':
                # Show manufacturer selection UI for unknown manufacturers
                if hasattr(url_field, 'manufacturer_selection_frame'):
                    url_field.manufacturer_selection_frame.show()
                    url_field.manufacturer_combo.setCurrentIndex(0)  # Reset to default
            else:
                # Hide manufacturer selection UI for known manufacturers
                if hasattr(url_field, 'manufacturer_selection_frame'):
                    url_field.manufacturer_selection_frame.hide()
                    
                # Trigger URL update if we have manufacturer info and credentials are filled
                if hasattr(username_field, 'text') and hasattr(password_field, 'text'):
                    # Small delay to ensure properties are set
                    QTimer.singleShot(100, lambda: self.trigger_url_update_if_ready(username_field, password_field, ip_field, url_field))
            
        except Exception as e:
            # Re-enable signals in case of error
            try:
                ip_field.blockSignals(False)
                username_field.blockSignals(False)
                password_field.blockSignals(False)
            except:
                pass
            QMessageBox.warning(self, "Discovery Error", f"Error processing discovered camera:\n{str(e)}")

    def trigger_url_update_if_ready(self, username_field, password_field, ip_field, url_field):
        """Trigger URL update if all fields are ready"""
        try:
            # Check if we have credentials and the URL field is in auto-generate mode
            if (not url_field.isEnabled() and 
                username_field.text().strip() and 
                password_field.text().strip() and 
                ip_field.text().strip()):
                
                # Get manufacturer info
                manufacturer = username_field.property('discovered_manufacturer')
                rtsp_patterns = username_field.property('rtsp_patterns')
                
                if manufacturer and rtsp_patterns and rtsp_patterns.get('manufacturer_detected'):
                    # Generate manufacturer-specific URL
                    rtsp_info = self.generate_manufacturer_rtsp_url(
                        ip_field.text().strip(), 
                        manufacturer, 
                        username_field.text().strip(), 
                        password_field.text().strip()
                    )
                    url_field.setText(rtsp_info['default_url'])
        except Exception as e:
            print(f"Error in trigger_url_update_if_ready: {e}")

    def toggle_manual_url(self, url_field, manual_mode):
        """Toggle between auto-generated and manual URL entry"""
        if manual_mode:
            url_field.setEnabled(True)
            url_field.setPlaceholderText("Enter your custom RTSP URL here...")
            url_field.setStyleSheet("background-color: #fff3cd; border: 1px solid #ffeaa7;")
        else:
            url_field.setEnabled(False)
            url_field.setPlaceholderText("Auto-generated RTSP URL will appear here")
            url_field.setStyleSheet("")

    def on_manufacturer_selected(self, manufacturer_text, ip_field, username_field, password_field, url_field, manufacturer_frame):
        """Handle manual manufacturer selection for unknown cameras"""
        try:
            if manufacturer_text == "-- None of the above --":
                # Show manual URL section for custom input
                if hasattr(url_field, 'manual_url_section'):
                    url_field.manual_url_section.show()
                    url_field.custom_url_field.setFocus()
                    url_field.setEnabled(False)  # Disable auto URL
                    print("Manual URL section shown for custom input")
                    
            elif manufacturer_text and manufacturer_text not in ["Select manufacturer...", "-- Select Camera Brand --"]:
                # Auto-generate URL for selected manufacturer
                if hasattr(url_field, 'manual_url_section'):
                    url_field.manual_url_section.hide()  # Hide manual section
                
                # Store the manually selected manufacturer
                if hasattr(username_field, 'setProperty'):
                    username_field.setProperty('discovered_manufacturer', manufacturer_text)
                    
                    # Generate RTSP patterns for this manufacturer
                    rtsp_info = self.generate_manufacturer_rtsp_url(
                        ip_field.text().strip() if ip_field.text().strip() else "192.168.1.100",
                        manufacturer_text, 
                        username_field.text().strip() if username_field.text().strip() else "admin",
                        password_field.text().strip() if password_field.text().strip() else "password"
                    )
                    username_field.setProperty('rtsp_patterns', rtsp_info)
                
                # Generate URL if we have at least an IP
                if ip_field.text().strip():
                    rtsp_info = self.generate_manufacturer_rtsp_url(
                        ip_field.text().strip(),
                        manufacturer_text,
                        username_field.text().strip() if username_field.text().strip() else "admin",
                        password_field.text().strip() if password_field.text().strip() else "password"
                    )
                    url_field.setText(rtsp_info['default_url'])
                    url_field.setEnabled(False)  # Keep auto-generated
                    
                    # Hide the manufacturer selection frame since we now have a manufacturer
                    manufacturer_frame.hide()
                    
                    # Show success message
                    QMessageBox.information(
                        self, "Manufacturer Selected",
                        f"✅ Manufacturer set to: {manufacturer_text}\n"
                        f"🔗 RTSP URL generated: {rtsp_info['default_url']}\n\n"
                        "The camera URL has been automatically configured for your camera."
                    )
                else:
                    url_field.setText("")
                    QMessageBox.warning(
                        self, "IP Address Required",
                        "Please enter the camera IP address first to generate the RTSP URL."
                    )
            else:
                # Reset state for default selection
                if hasattr(url_field, 'manual_url_section'):
                    url_field.manual_url_section.hide()
                url_field.setText("")
                
        except Exception as e:
            print(f"Error in manufacturer selection: {e}")
            traceback.print_exc()
            QMessageBox.warning(self, "Selection Error", f"Error processing manufacturer selection:\n{str(e)}")

    def update_rtsp_url(self, ip_field, username_field, password_field, url_field):
        """Update RTSP URL when IP/username/password changes"""
        try:
            # Only update if URL field is in auto-generate mode
            if (url_field.isEnabled()):
                return
                
            # Check if all required fields are filled
            ip_text = ip_field.text().strip()
            username_text = username_field.text().strip() 
            password_text = password_field.text().strip()
            
            if (not ip_text or not username_text or not password_text):
                return
                
            # Get manufacturer info from stored properties
            manufacturer = username_field.property('discovered_manufacturer')
            rtsp_patterns = username_field.property('rtsp_patterns')
            
            if manufacturer and manufacturer != 'Unknown':
                # Generate manufacturer-specific URL
                rtsp_info = self.generate_manufacturer_rtsp_url(
                    ip_text, manufacturer, username_text, password_text
                )
                url_field.setText(rtsp_info['default_url'])
                
                # Hide manufacturer selection if it was shown
                if hasattr(url_field, 'manufacturer_selection_frame'):
                    url_field.manufacturer_selection_frame.hide()
            else:
                # Show manufacturer selection for unknown manufacturers
                if hasattr(url_field, 'manufacturer_selection_frame'):
                    frame = url_field.manufacturer_selection_frame
                    combo = url_field.manufacturer_combo
                    
                    # Reset the combo to default selection
                    combo.setCurrentIndex(0)
                    
                    # Show the frame and ensure proper visibility
                    frame.show()
                    frame.setVisible(True)
                    frame.raise_()  # Bring to front
                    
                    # Ensure the combo box is properly sized and visible
                    combo.setVisible(True)
                    combo.raise_()
                    combo.adjustSize()
                    
                    # Force layout updates at multiple levels including form row
                    frame.updateGeometry()
                    parent_widget = frame.parent()
                    if parent_widget:
                        parent_widget.updateGeometry()
                        parent_widget.update()
                        
                        # If it's in a form layout, ensure the row is visible
                        parent_layout = parent_widget.layout()
                        if parent_layout:
                            parent_layout.update()
                    
                    # Force a repaint
                    frame.repaint()
                    
                    print(f"Manufacturer selection shown - frame visible: {frame.isVisible()}, combo visible: {combo.isVisible()}")  # Debug
                    
        except Exception as e:
            print(f"Error updating RTSP URL: {e}")
            import traceback
            traceback.print_exc()

    def generate_manufacturer_rtsp_url(self, ip_address, manufacturer, username="admin", password="password"):
        """Generate manufacturer-specific RTSP URL patterns - reusing from simple_camera_gui.py"""
        try:
            # Try to import and use the method from simple_camera_gui.py
            from simple_camera_gui import SimpleCameraGUI
            temp_gui = SimpleCameraGUI()
            return temp_gui.generate_manufacturer_rtsp_url(ip_address, manufacturer, username, password)
        except ImportError:
            # Fallback to local implementation
            return self._fallback_generate_manufacturer_rtsp_url(ip_address, manufacturer, username, password)

    def _fallback_generate_manufacturer_rtsp_url(self, ip_address, manufacturer, username="admin", password="password"):
        """Generate manufacturer-specific RTSP URL patterns"""
        try:
            manufacturer_lower = manufacturer.lower()
            
            # Manufacturer-specific RTSP URL patterns
            rtsp_patterns = {
                'hikvision': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/Streaming/Channels/101',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/Streaming/Channels/102',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/h264/ch1/main/av_stream'
                },
                'dahua': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=0',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=1',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=0'
                },
                'amcrest': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=0',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=1', 
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/cam/realmonitor?channel=1&subtype=0'
                },
                'reolink': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/h264Preview_01_main',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/h264Preview_01_sub',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/h264Preview_01_main'
                },
                'axis': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/axis-media/media.amp',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/axis-media/media.amp?resolution=320x240',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/axis-media/media.amp'
                },
                'foscam': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/videoMain',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/videoSub',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/videoMain'
                },
                'vivotek': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/live.sdp',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/live2.sdp',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/live.sdp'
                },
                'bosch': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/rtsp_tunnel',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/rtsp_tunnel?inst=2',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/rtsp_tunnel'
                },
                'sony': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/media/video1',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/media/video2', 
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/media/video1'
                },
                'uniview': {
                    'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/media/video1',
                    'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/media/video2',
                    'default': f'rtsp://{username}:{password}@{ip_address}:554/media/video1'
                }
            }
            
            # Check for exact manufacturer match
            for mfr_key, patterns in rtsp_patterns.items():
                if mfr_key in manufacturer_lower:
                    return {
                        'main_stream': patterns['main_stream'],
                        'sub_stream': patterns['sub_stream'], 
                        'default_url': patterns['default'],
                        'manufacturer_detected': True
                    }
            
            # Generic fallback for unknown manufacturers
            generic_patterns = [
                f'rtsp://{username}:{password}@{ip_address}:554/stream1',
                f'rtsp://{username}:{password}@{ip_address}:554/live',
                f'rtsp://{username}:{password}@{ip_address}:554/media/video1'
            ]
            
            return {
                'main_stream': generic_patterns[0],
                'sub_stream': generic_patterns[0],
                'default_url': generic_patterns[0],
                'manufacturer_detected': False,
                'alternatives': generic_patterns
            }
            
        except Exception:
            # Ultimate fallback
            return {
                'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'default_url': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'manufacturer_detected': False
            }

    def save_config(self):
        try:
            # --- MQTT ---
            mqtt_config = {
                "enabled": self.mqtt_enabled.isChecked() if hasattr(self, 'mqtt_enabled') and self.mqtt_enabled else False
            }
            if hasattr(self, 'mqtt_enabled') and self.mqtt_enabled and self.mqtt_enabled.isChecked():
                if hasattr(self, 'mqtt_host') and self.mqtt_host:
                    mqtt_config["host"] = self.mqtt_host.text()
                if hasattr(self, 'mqtt_port') and self.mqtt_port and self.mqtt_port.text():
                    mqtt_config["port"] = int(self.mqtt_port.text())
                if hasattr(self, 'mqtt_topic') and self.mqtt_topic and self.mqtt_topic.text():
                    mqtt_config["topic_prefix"] = self.mqtt_topic.text()
        except Exception as e:
            print(f"Error in MQTT config: {e}")
            mqtt_config = {"enabled": False}

        # --- FFmpeg ---
        try:
            ffmpeg_config = {}
            if hasattr(self, 'ffmpeg_group') and self.ffmpeg_group and self.ffmpeg_group.isChecked():
                if hasattr(self, 'ffmpeg_hwaccel') and self.ffmpeg_hwaccel:
                    ffmpeg_config["hwaccel_args"] = self.ffmpeg_hwaccel.currentText()
        except Exception as e:
            print(f"Error in FFmpeg config: {e}")
            ffmpeg_config = {}

        # --- Detectors ---
        try:
            detectors_config = {}
            if hasattr(self, 'memryx_devices') and self.memryx_devices:
                for i in range(self.memryx_devices.value()):
                    detectors_config[f"memx{i}"] = {
                        "type": "memryx",
                        "device": f"PCIe:{i}"
                    }
        except Exception as e:
            print(f"Error in Detectors config: {e}")
            detectors_config = {"memx0": {"type": "memryx", "device": "PCIe:0"}}

        # --- Model ---
        try:
            if hasattr(self, 'custom_group') and self.custom_group and self.custom_group.isChecked():
                # Use custom width/height + path
                w = self.custom_width.value() if hasattr(self, 'custom_width') and self.custom_width else 320
                h = self.custom_height.value() if hasattr(self, 'custom_height') and self.custom_height else 320
                model_path = self.custom_path.text() if hasattr(self, 'custom_path') and self.custom_path else None
            else:
                # Use preset resolution selection
                if hasattr(self, 'model_resolution') and self.model_resolution:
                    w, h = self._parse_resolution(self.model_resolution.currentText())
                else:
                    w, h = 320, 320
                model_path = None  # no path unless the custom group is checked

            model_config = {
                "model_type": self.model_type.currentText() if hasattr(self, 'model_type') and self.model_type else "yolo-generic",
                "width": w,
                "height": h,
                "input_tensor": self.input_tensor.currentText() if hasattr(self, 'input_tensor') and self.input_tensor else "nchw",
                "input_dtype": self.input_dtype.currentText() if hasattr(self, 'input_dtype') and self.input_dtype else "float",
                "labelmap_path": self.labelmap_path.text() if hasattr(self, 'labelmap_path') and self.labelmap_path else "/labelmap/coco-80.txt"
            }
            if model_path:
                model_config["path"] = model_path
        except Exception as e:
            print(f"Error in Model config: {e}")
            model_config = {
                "model_type": "yolo-generic",
                "width": 320,
                "height": 320,
                "input_tensor": "nchw",
                "input_dtype": "float",
                "labelmap_path": "/labelmap/coco-80.txt"
            }

        # --- Camera ---
        try:
            cameras_config = {}
            if hasattr(self, 'camera_tabs') and self.camera_tabs:
                for cam in self.camera_tabs:
                    try:
                        roles = []
                        if cam.get("role_detect") and cam["role_detect"].isChecked():
                            roles.append("detect")
                        if cam.get("role_record") and cam["role_record"].isChecked():
                            roles.append("record")

                        camera_name = cam["camera_name"].text() if cam.get("camera_name") else f"camera_{len(cameras_config)+1}"
                        camera_url = cam["camera_url"].text() if cam.get("camera_url") else ""

                        cameras_config[camera_name] = {
                            "ffmpeg": {"inputs": [{"path": camera_url, "roles": roles}]},
                            "detect": {
                                "width": cam["detect_width"].value() if cam.get("detect_width") else 2560,
                                "height": cam["detect_height"].value() if cam.get("detect_height") else 1440,
                                "fps": cam["detect_fps"].value() if cam.get("detect_fps") else 5,
                                "enabled": cam["detect_enabled"].isChecked() if cam.get("detect_enabled") else True,
                            },
                            "objects": {
                                "track": [o.strip() for o in cam["objects"].toPlainText().split(",") if o.strip()] if cam.get("objects") else ["person", "car"]
                            },
                            "snapshots": {
                                "enabled": cam["snapshots_enabled"].isChecked() if cam.get("snapshots_enabled") else True,
                                "bounding_box": cam["snapshots_bb"].isChecked() if cam.get("snapshots_bb") else True,
                                "retain": {"default": cam["snapshots_retain"].value() if cam.get("snapshots_retain") else 14},
                            },
                            "record": {
                                "enabled": cam["record_enabled"].isChecked() if cam.get("record_enabled") else False,
                                "alerts": {"retain": {"days": cam["record_alerts"].value() if cam.get("record_alerts") else 7}},
                                "detections": {"retain": {"days": cam["record_detections"].value() if cam.get("record_detections") else 3}},
                            },
                        }
                    except Exception as cam_error:
                        print(f"Error processing camera {len(cameras_config)+1}: {cam_error}")
                        continue
        except Exception as e:
            print(f"Error in Camera config: {e}")
            cameras_config = {}

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

        # Always overwrite the existing config with camera spacing
        yaml_content = yaml.dump(
            config, 
            Dumper=MyDumper, 
            default_flow_style=False, 
            sort_keys=False
        )
        
        # Add spacing between cameras for better readability
        yaml_content = MyDumper.add_camera_spacing(yaml_content)
        
        with open(save_path, "w") as f:
            f.write(yaml_content)

        print(f"[SUCCESS] Config saved to {save_path}")

        self.config_saved = True
        
        # Close the GUI after saving
        # Check if this GUI was launched from frigate_launcher
        if hasattr(self, 'launcher_parent') and self.launcher_parent is not None:
            # If launched from launcher, just close this window (not the entire application)
            self.close()
        else:
            # If running standalone, quit the entire application
            QApplication.instance().quit()

    def smart_close(self, exit_code=0):
        """Smart close that detects launcher context and closes appropriately"""
        if hasattr(self, 'launcher_parent') and self.launcher_parent is not None:
            # If launched from launcher, just close this window
            self.close()
        else:
            # If running standalone, exit the entire application
            if exit_code == 0:
                QApplication.instance().quit()
            else:
                QApplication.instance().exit(exit_code)

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
        width: 2560
        height: 1440
        fps: 5
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
            default: 0   # keep snapshots for 'n' day

        record:
        enabled: false
        alerts:
            retain:
            days: 0
        detections:
            retain:
            days: 0
        continuous:
            days: 0
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
                
        # Smart close with code 1 to indicate window was closed without saving
        self.smart_close(1)
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

            # Note: Camera settings are now loaded separately in load_existing_cameras()
            # to ensure proper sequencing with tab creation

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
            
            self.smart_close(2)  # Smart close with code 2 for advanced settings

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConfigGUI()
    window.show()
    sys.exit(app.exec())