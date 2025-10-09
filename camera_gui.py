#!/usr/bin/env python3
"""
Simple Camera Configuration GUI for Frigate + MemryX
A simplified GUI focused solely on camera configuration - matches config_gui.py design
"""

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QCheckBox, QComboBox, QSpinBox, QFormLayout, 
                               QTextEdit, QGroupBox, QScrollArea, QFrame, QMessageBox, 
                               QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QTabWidget,
                               QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy)
from PySide6.QtGui import QFont, QPixmap, QCloseEvent
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
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import re

# Global list to track all ONVIF worker threads for cleanup
_active_onvif_workers = []

def cleanup_all_threads():
    """Global cleanup function to ensure all threads are stopped"""
    global _active_onvif_workers
    for worker in _active_onvif_workers[:]:  # Copy list to avoid modification during iteration
        try:
            if worker.isRunning():
                worker.running = False
                worker.requestInterruption()
                if not worker.wait(500):
                    worker.terminate()
                    worker.wait(500)
            _active_onvif_workers.remove(worker)
        except:
            pass
    _active_onvif_workers.clear()

# Register cleanup function to run on exit
atexit.register(cleanup_all_threads)

# ONVIF Discovery functionality
class ONVIFDiscoveryWorker(QThread):
    """Background worker for ONVIF camera discovery"""
    camera_found = Signal(dict)  # Emits camera info when found
    discovery_finished = Signal()
    progress_update = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        # Register this worker globally for cleanup
        global _active_onvif_workers
        _active_onvif_workers.append(self)
    
    def __del__(self):
        """Remove from global list when destroyed"""
        global _active_onvif_workers
        try:
            if self in _active_onvif_workers:
                _active_onvif_workers.remove(self)
        except:
            pass
    
    def run(self):
        """Discover ONVIF cameras on the network"""
        self.running = True
        self.progress_update.emit("🔍 Searching for ONVIF cameras...")
        
        try:
            # Check for interruption before starting
            if self.isInterruptionRequested():
                return
                
            cameras = self.discover_onvif_cameras()
            
            # Check for interruption after discovery
            if self.isInterruptionRequested():
                return
                
            if not cameras:
                self.progress_update.emit("❌ No ONVIF cameras found on network")
            else:
                self.progress_update.emit(f"✅ Found {len(cameras)} camera(s)")
                
        except Exception as e:
            if not self.isInterruptionRequested():
                self.progress_update.emit(f"❌ Discovery error: {str(e)}")
        
        if not self.isInterruptionRequested():
            self.discovery_finished.emit()
    
    def discover_onvif_cameras(self):
        """Discover ONVIF cameras using WS-Discovery"""
        cameras = []
        
        # Create multicast socket for WS-Discovery
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(5.0)
        
        # WS-Discovery probe message for ONVIF devices
        probe_uuid = str(uuid.uuid4())
        probe_message = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope 
    xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
    xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
    xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery" 
    xmlns:tns="http://www.onvif.org/ver10/network/wsdl">
    <soap:Header>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
        <wsa:MessageID>urn:uuid:{probe_uuid}</wsa:MessageID>
        <wsa:ReplyTo>
            <wsa:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:Address>
        </wsa:ReplyTo>
        <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    </soap:Header>
    <soap:Body>
        <wsd:Probe>
            <wsd:Types>tns:NetworkVideoTransmitter</wsd:Types>
        </wsd:Probe>
    </soap:Body>
</soap:Envelope>'''
        
        try:
            # Send multicast probe
            multicast_addr = ('239.255.255.250', 3702)
            sock.sendto(probe_message.encode('utf-8'), multicast_addr)
            
            # Listen for responses
            start_time = time.time()
            discovered_ips = set()
            
            while time.time() - start_time < 3.0 and self.running and not self.isInterruptionRequested():  # 3 second timeout
                try:
                    data, addr = sock.recvfrom(4096)
                    ip_address = addr[0]
                    
                    # Check for interruption during processing
                    if self.isInterruptionRequested():
                        break
                    
                    if ip_address not in discovered_ips:
                        discovered_ips.add(ip_address)
                        
                        # Extract camera info from response
                        camera_info = self.parse_onvif_response(data.decode('utf-8', errors='ignore'), ip_address)
                        if camera_info:
                            cameras.append(camera_info)
                            self.camera_found.emit(camera_info)
                            self.progress_update.emit(f"📹 Found camera: {ip_address}")
                        
                except socket.timeout:
                    # Check for interruption on timeout too
                    if self.isInterruptionRequested():
                        break
                    continue
                except Exception as e:
                    continue
                    
        except Exception as e:
            self.progress_update.emit(f"Network error: {str(e)}")
        finally:
            sock.close()
        
        return cameras
    
    def parse_onvif_response(self, response_data, ip_address):
        """Parse ONVIF discovery response and extract camera info"""
        try:
            # Basic camera info with defaults
            camera_info = {
                'ip': ip_address,
                'name': f'Camera_{ip_address.split(".")[-1]}',
                'manufacturer': 'Unknown',
                'model': 'ONVIF Camera',
                'rtsp_url': f'rtsp://{ip_address}:554/live',
                'onvif_url': f'http://{ip_address}/onvif/device_service',
                'status': 'Discovered'
            }
            
            # Method 1: Extract manufacturer from WS-Discovery response
            manufacturer = self.extract_manufacturer_from_discovery(response_data)
            if manufacturer and manufacturer != 'Unknown':
                camera_info['manufacturer'] = manufacturer
                camera_info['status'] = 'Identified'
                
                # Generate manufacturer-specific RTSP URLs
                rtsp_info = self.generate_manufacturer_rtsp_url(ip_address, manufacturer)
                camera_info['rtsp_url'] = rtsp_info['default_url']
                camera_info['rtsp_patterns'] = rtsp_info  # Store all patterns for later use
                
            else:
                # Method 2: Try ONVIF GetDeviceInformation (in background)
                device_info = self.get_onvif_device_info_quick(ip_address)
                if device_info:
                    camera_info.update(device_info)
                    camera_info['status'] = 'Detailed'
                    
                    # Generate manufacturer-specific RTSP URLs if manufacturer was found
                    if 'manufacturer' in device_info and device_info['manufacturer'] != 'Unknown':
                        rtsp_info = self.generate_manufacturer_rtsp_url(ip_address, device_info['manufacturer'])
                        camera_info['rtsp_url'] = rtsp_info['default_url']
                        camera_info['rtsp_patterns'] = rtsp_info
            
            return camera_info
            
        except Exception:
            return None
    
    def extract_manufacturer_from_discovery(self, response_data):
        """Extract manufacturer from WS-Discovery response"""
        try:
            response_lower = response_data.lower()
            
            # Common camera manufacturers and detection patterns
            manufacturer_patterns = {
                'hikvision': ['hikvision', 'hik-vision', 'hikcvision'],
                'dahua': ['dahua', 'dh-', 'dahua technology'],
                'axis': ['axis', 'axis communications'],
                'bosch': ['bosch', 'bosch security'],
                'sony': ['sony'],
                'panasonic': ['panasonic', 'matsushita'],
                'samsung': ['samsung', 'hanwha'],
                'vivotek': ['vivotek'],
                'foscam': ['foscam'],
                'reolink': ['reolink'],
                'amcrest': ['amcrest'],
                'uniview': ['uniview', 'unv'],
                'honeywell': ['honeywell']
            }
            
            # Method 1: Check for manufacturer patterns in text
            for manufacturer, patterns in manufacturer_patterns.items():
                for pattern in patterns:
                    if pattern in response_lower:
                        return manufacturer.title()
            
            # Method 2: Parse XML if present
            if '<' in response_data and '>' in response_data:
                try:
                    start_tag = response_data.find('<')
                    if start_tag >= 0:
                        xml_data = response_data[start_tag:]
                        root = ET.fromstring(xml_data)
                        
                        # Look for manufacturer info in XML elements
                        for elem in root.iter():
                            if elem.text:
                                text = elem.text.lower()
                                for manufacturer, patterns in manufacturer_patterns.items():
                                    for pattern in patterns:
                                        if pattern in text:
                                            return manufacturer.title()
                except ET.ParseError:
                    pass
            
            # Method 3: Look for ONVIF scope patterns
            scope_patterns = [
                r'onvif://www\.onvif\.org/([^/\s]+)',
                r'http://[^/]*([^./]+)\.[^/]*/'
            ]
            
            for pattern in scope_patterns:
                matches = re.findall(pattern, response_data, re.IGNORECASE)
                for match in matches:
                    match_lower = match.lower()
                    for manufacturer, patterns in manufacturer_patterns.items():
                        for p in patterns:
                            if p in match_lower:
                                return manufacturer.title()
            
            return 'Unknown'
            
        except Exception:
            return 'Unknown'
    
    def get_onvif_device_info_quick(self, ip_address):
        """Get device info via ONVIF with short timeout for quick discovery"""
        try:
            soap_request = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <soap:Header/>
    <soap:Body>
        <tds:GetDeviceInformation/>
    </soap:Body>
</soap:Envelope>'''
            
            # Try most common ONVIF endpoint with short timeout
            endpoint = f'http://{ip_address}/onvif/device_service'
            
            req = urllib.request.Request(
                endpoint,
                data=soap_request.encode('utf-8'),
                headers={
                    'Content-Type': 'application/soap+xml; charset=utf-8',
                    'SOAPAction': 'http://www.onvif.org/ver10/device/wsdl/GetDeviceInformation'
                }
            )
            
            # Very short timeout to keep discovery fast
            with urllib.request.urlopen(req, timeout=1) as response:
                response_data = response.read().decode('utf-8')
                return self.parse_device_information_response(response_data)
                
        except Exception:
            return None
    
    def parse_device_information_response(self, response_data):
        """Parse ONVIF GetDeviceInformation response"""
        try:
            root = ET.fromstring(response_data)
            
            namespaces = {
                'soap': 'http://www.w3.org/2003/05/soap-envelope',
                'tds': 'http://www.onvif.org/ver10/device/wsdl'
            }
            
            device_info = {}
            
            # Extract manufacturer
            manufacturer_elem = root.find('.//tds:Manufacturer', namespaces)
            if manufacturer_elem is not None and manufacturer_elem.text:
                device_info['manufacturer'] = manufacturer_elem.text.strip()
            
            # Extract model
            model_elem = root.find('.//tds:Model', namespaces)
            if model_elem is not None and model_elem.text:
                device_info['model'] = model_elem.text.strip()
            
            # Extract firmware for enhanced name
            firmware_elem = root.find('.//tds:FirmwareVersion', namespaces)
            if firmware_elem is not None and firmware_elem.text:
                fw_version = firmware_elem.text.strip()
                if device_info.get('model'):
                    device_info['name'] = f"{device_info['model']} (FW: {fw_version})"
            
            return device_info if device_info else None
            
        except Exception:
            return None
    
    def generate_manufacturer_rtsp_url(self, ip_address, manufacturer, username="admin", password="password"):
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
    
    def stop_discovery(self):
        """Stop the discovery process"""
        self.running = False
        # Request thread interruption
        self.requestInterruption()
        # Remove from global list
        global _active_onvif_workers
        try:
            if self in _active_onvif_workers:
                _active_onvif_workers.remove(self)
        except:
            pass

class ONVIFDiscoveryDialog(QDialog):
    """Dialog for discovering ONVIF cameras"""
    camera_selected = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 ONVIF Camera Discovery")
        self.setModal(True)
        self.resize(700, 500)
        
        self.discovered_cameras = []
        self.worker = None
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("🔍 ONVIF Camera Discovery")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("color: #2c6b7d; padding: 10px;")
        layout.addWidget(header_label)
        
        # Info label
        info_label = QLabel(
            "This tool will scan your network for ONVIF-compatible IP cameras.\n"
            "Make sure your cameras are powered on and connected to the same network."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background: #f0f8ff; border-radius: 5px; margin: 5px;")
        layout.addWidget(info_label)
        
        # Progress area
        self.progress_label = QLabel("Ready to scan...")
        self.progress_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Camera table
        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(5)
        self.camera_table.setHorizontalHeaderLabels(['IP Address', 'Name', 'Manufacturer', 'Model', 'Status'])
        
        # Make table headers stretch
        header = self.camera_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.camera_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.camera_table.setAlternatingRowColors(True)
        self.camera_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        layout.addWidget(self.camera_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.scan_button = QPushButton("🔍 Start Scan")
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.scan_button.clicked.connect(self.start_discovery)
        
        self.select_button = QPushButton("✓ Select Camera")
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.select_button.clicked.connect(self.select_camera)
        self.select_button.setEnabled(False)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Connect table selection
        self.camera_table.selectionModel().selectionChanged.connect(self.on_selection_changed)
    
    def start_discovery(self):
        """Start ONVIF camera discovery"""
        self.scan_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.camera_table.setRowCount(0)
        self.discovered_cameras.clear()
        
        # Start worker thread
        self.worker = ONVIFDiscoveryWorker()
        self.worker.camera_found.connect(self.on_camera_found)
        self.worker.discovery_finished.connect(self.on_discovery_finished)
        self.worker.progress_update.connect(self.on_progress_update)
        self.worker.start()
    
    def on_camera_found(self, camera_info):
        """Handle discovered camera"""
        self.discovered_cameras.append(camera_info)
        
        # Add to table
        row = self.camera_table.rowCount()
        self.camera_table.insertRow(row)
        
        self.camera_table.setItem(row, 0, QTableWidgetItem(camera_info['ip']))
        self.camera_table.setItem(row, 1, QTableWidgetItem(camera_info['name']))
        self.camera_table.setItem(row, 2, QTableWidgetItem(camera_info['manufacturer']))
        self.camera_table.setItem(row, 3, QTableWidgetItem(camera_info['model']))
        self.camera_table.setItem(row, 4, QTableWidgetItem(camera_info['status']))
    
    def on_discovery_finished(self):
        """Handle discovery completion"""
        self.scan_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if self.discovered_cameras:
            self.progress_label.setText(f"✅ Discovery complete! Found {len(self.discovered_cameras)} camera(s)")
        else:
            self.progress_label.setText("❌ No cameras found. Check network connection and camera power.")
        
        # Clean up worker thread
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def on_progress_update(self, message):
        """Handle progress updates"""
        self.progress_label.setText(message)
    
    def on_selection_changed(self):
        """Handle table selection changes"""
        self.select_button.setEnabled(len(self.camera_table.selectedItems()) > 0)
    
    def select_camera(self):
        """Select the currently highlighted camera"""
        current_row = self.camera_table.currentRow()
        if current_row >= 0 and current_row < len(self.discovered_cameras):
            selected_camera = self.discovered_cameras[current_row]
            self.camera_selected.emit(selected_camera)
            self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close"""
        try:
            if self.worker and self.worker.isRunning():
                print("Stopping ONVIF discovery worker...")
                self.worker.stop_discovery()
                # Wait for thread to finish, but not from within the thread itself
                if not self.worker.wait(800):  # Wait up to 0.8 seconds
                    print("Force terminating ONVIF worker...")
                    # Force terminate if it doesn't stop
                    self.worker.terminate()
                    if not self.worker.wait(200):  # Wait another 0.2 seconds for termination
                        print("Warning: ONVIF worker did not terminate cleanly")
                print("ONVIF worker stopped")
            # Ensure worker is deleted
            if self.worker:
                self.worker.deleteLater()
                self.worker = None
        except Exception as e:
            print(f"Error during ONVIF dialog cleanup: {e}")
        event.accept()

class MyDumper(yaml.Dumper):
    """Custom YAML dumper for better formatting"""
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

        # Make window responsive with flexible sizing
        win_width = int(screen_width * 0.5)
        win_height = int(screen_height * 0.65)
        
        # Set minimum size for usability and responsive sizing
        self.setMinimumSize(500, 400)
        self.resize(win_width, win_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Center the window
        self.move(
            (screen_width - win_width) // 2,
            (screen_height - win_height) // 2
        )

        # Global Layout with responsive setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Smaller margins for compact layout
        layout.setSpacing(5)

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
        # Tabs - responsive design
        ################################
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Remove elide mode to prevent tab text truncation

        # --- Camera Tab with Scroll Area ---
        # Create main scroll area for the entire camera tab
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        cams_tab = QWidget()
        cams_layout = QVBoxLayout(cams_tab)
        cams_layout.setContentsMargins(10, 10, 10, 10)
        cams_layout.setSpacing(8)

        # Camera count controls - responsive design
        cams_count_frame = QFrame()
        cams_count_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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

        # Sub-tabs for cameras - responsive
        self.cams_subtabs = QTabWidget()
        self.cams_subtabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cams_layout.addWidget(self.cams_subtabs)
        
        # Set scroll area widget
        main_scroll.setWidget(cams_tab)

        # Add the scroll area (not the widget directly) to tabs
        tabs.addTab(main_scroll, "📹 Cameras")

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

    # ================================
    # INPUT VALIDATION METHODS
    # ================================
    
    def validate_camera_name(self, name):
        """Validate camera name input"""
        name = name.strip()
        errors = []
        
        if not name:
            errors.append("Camera name is required")
        elif len(name) < 2:
            errors.append("Camera name must be at least 2 characters")
        elif len(name) > 50:
            errors.append("Camera name must be less than 50 characters")
        elif not re.match(r'^[a-zA-Z0-9_\-\s]+$', name):
            errors.append("Camera name can only contain letters, numbers, spaces, hyphens, and underscores")
        
        return len(errors) == 0, errors
    
    def validate_ip_address(self, ip):
        """Validate IP address format"""
        ip = ip.strip()
        errors = []
        
        if not ip:
            errors.append("IP address is required")
            return False, errors
        
        # Check basic IP format
        ip_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(ip_pattern, ip)
        
        if not match:
            errors.append("IP address must be in format xxx.xxx.xxx.xxx")
        else:
            # Check each octet is valid (0-255)
            octets = [int(x) for x in match.groups()]
            for i, octet in enumerate(octets):
                if octet > 255:
                    errors.append(f"IP address octet {i+1} must be 0-255")
                elif i == 0 and octet == 0:
                    errors.append("First octet cannot be 0")
        
        return len(errors) == 0, errors
    
    def validate_username(self, username):
        """Validate username input"""
        username = username.strip()
        errors = []
        
        if not username:
            errors.append("Username is required")
        elif len(username) < 2:
            errors.append("Username must be at least 2 characters")
        elif len(username) > 50:
            errors.append("Username must be less than 50 characters")
        elif not re.match(r'^[a-zA-Z0-9_\-\.@]+$', username):
            errors.append("Username can only contain letters, numbers, and common symbols (_ - . @)")
        
        return len(errors) == 0, errors
    
    def validate_password(self, password):
        """Validate password input"""
        errors = []
        
        if not password:
            errors.append("Password is required")
        elif len(password) < 1:  # Allow any non-empty password
            errors.append("Password cannot be empty")
        elif len(password) > 100:
            errors.append("Password must be less than 100 characters")
        
        return len(errors) == 0, errors
    
    def validate_rtsp_url(self, url):
        """Validate RTSP URL format"""
        url = url.strip()
        errors = []
        
        if not url:
            # RTSP URL is optional if other fields are filled
            return True, errors
        
        if not url.startswith('rtsp://'):
            errors.append("RTSP URL must start with 'rtsp://'")
        
        # Basic URL format check
        url_pattern = r'^rtsp://([a-zA-Z0-9_\-\.@]+):(.+)@(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):?(\d+)?/.+'
        if not re.match(url_pattern, url):
            errors.append("RTSP URL format should be: rtsp://username:password@ip:port/path")
        
        return len(errors) == 0, errors
    
    def validate_objects_list(self, objects_text):
        """Validate objects detection list"""
        objects_text = objects_text.strip()
        errors = []
        
        if not objects_text:
            errors.append("At least one object type is required (e.g., person)")
            return False, errors
        
        # Split by commas and validate each object
        objects = [obj.strip() for obj in objects_text.split(',')]
        valid_objects = []
        
        for obj in objects:
            if not obj:
                continue
            if len(obj) < 2:
                errors.append(f"Object '{obj}' is too short")
            elif len(obj) > 30:
                errors.append(f"Object '{obj}' is too long")
            elif not re.match(r'^[a-zA-Z0-9_\-\s]+$', obj):
                errors.append(f"Object '{obj}' contains invalid characters")
            else:
                valid_objects.append(obj)
        
        if not valid_objects:
            errors.append("No valid objects found in the list")
        
        return len(errors) == 0, errors
    
    def apply_validation_style(self, widget, is_valid, errors=None):
        """Apply visual validation styling to input widgets"""
        if is_valid:
            # Valid style - green border
            widget.setStyleSheet("""
                QLineEdit, QTextEdit {
                    border: 2px solid #28a745;
                    background: #f8fff9;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
                QLineEdit:focus, QTextEdit:focus {
                    border: 2px solid #20c997;
                    background: #ffffff;
                }
            """)
            widget.setToolTip("")
        else:
            # Invalid style - red border
            widget.setStyleSheet("""
                QLineEdit, QTextEdit {
                    border: 2px solid #dc3545;
                    background: #fff5f5;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
                QLineEdit:focus, QTextEdit:focus {
                    border: 2px solid #e74c3c;
                    background: #ffffff;
                }
            """)
            # Set error tooltip
            if errors:
                widget.setToolTip("❌ " + " • ".join(errors))
    
    def apply_neutral_style(self, widget):
        """Apply neutral styling for fields that haven't been validated yet"""
        widget.setStyleSheet("""
            QLineEdit, QTextEdit {
                border: 1px solid #cbd5e0;
                background: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #3498db;
                background: #ffffff;
            }
        """)
        widget.setToolTip("")
    
    def validate_camera_form(self, camera_data):
        """Validate all fields in a camera form"""
        all_valid = True
        validation_results = {}
        
        # Validate each field
        fields_to_validate = [
            ('camera_name', self.validate_camera_name),
            ('ip_address', self.validate_ip_address),
            ('username', self.validate_username),
            ('password', self.validate_password),
            ('camera_url', self.validate_rtsp_url),
            ('objects', self.validate_objects_list)
        ]
        
        for field_name, validator in fields_to_validate:
            if field_name in camera_data:
                field_value = camera_data[field_name]
                is_valid, errors = validator(field_value)
                validation_results[field_name] = {
                    'valid': is_valid,
                    'errors': errors
                }
                if not is_valid:
                    all_valid = False
        
        return all_valid, validation_results
    
    def setup_field_validation(self, widget, validator, field_name=None):
        """Setup real-time validation for a field"""
        def on_text_changed():
            if hasattr(widget, 'text'):
                text = widget.text()
            elif hasattr(widget, 'toPlainText'):
                text = widget.toPlainText()
            else:
                return
            
            is_valid, errors = validator(text)
            self.apply_validation_style(widget, is_valid, errors)
            
            # Update widget's validation state
            widget.setProperty('validation_valid', is_valid)
            widget.setProperty('validation_errors', errors)
        
        # Connect to appropriate signal
        if hasattr(widget, 'textChanged'):
            widget.textChanged.connect(on_text_changed)
        elif hasattr(widget, 'textChanged'):  # QTextEdit
            widget.textChanged.connect(on_text_changed)
        
        # Apply neutral style initially
        self.apply_neutral_style(widget)
        
        return on_text_changed

    def generate_manufacturer_rtsp_url(self, ip_address, manufacturer, username="admin", password="password"):
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
                        'manufacturer_detected': True,
                        'alternative_urls': [patterns['main_stream'], patterns['sub_stream']]
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
                'alternative_urls': generic_patterns
            }
            
        except Exception:
            # Ultimate fallback
            return {
                'main_stream': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'sub_stream': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'default_url': f'rtsp://{username}:{password}@{ip_address}:554/live',
                'manufacturer_detected': False,
                'alternative_urls': []
            }

    def load_existing_cameras(self):
        """Load existing camera configurations from config.yaml if available"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "frigate", "config", "config.yaml")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_content = f.read()
                    
                # Check if file is empty
                if not config_content.strip():
                    print("Config file is empty, using default configuration")
                    self.rebuild_camera_tabs(self.cams_count.value())
                    return
                
                # Try parsing with yaml.safe_load
                try:
                    config = yaml.safe_load(config_content)
                    if config is None:
                        config = {}
                except yaml.YAMLError as yaml_error:
                    print(f"YAML parsing error: {yaml_error}")
                    # Use intelligent reconstruction for malformed YAML
                    config = self.intelligent_config_reconstruction(config_content)
                    if config is None:
                        config = {}
                
                # Extract and validate cameras from config
                valid_cameras = self.extract_valid_cameras(config)
                
                if valid_cameras:
                    # Set camera count to match valid cameras
                    self.cams_count.setValue(len(valid_cameras))
                    
                    # Store original config for change detection
                    self.original_config = valid_cameras.copy()
                    
                    # Rebuild tabs with valid camera data
                    self.rebuild_camera_tabs_with_existing_data(valid_cameras)
                    print(f"Loaded {len(valid_cameras)} valid camera(s) from config")
                    return
                else:
                    print("No valid cameras found in config file")
                        
            except FileNotFoundError:
                print(f"Config file not found: {config_path}")
            except PermissionError:
                print(f"Permission denied reading config file: {config_path}")
            except Exception as e:
                print(f"Error loading existing cameras: {e}")
                import traceback
                traceback.print_exc()
        
        # Fallback: build default single camera tab
        print("Using default camera configuration")
        self.rebuild_camera_tabs(self.cams_count.value())

    def extract_valid_cameras(self, config):
        """Extract and validate camera configurations from the config"""
        if not config or not isinstance(config, dict):
            return {}
        
        cameras_config = config.get("cameras", {})
        if not isinstance(cameras_config, dict):
            return {}
        
        valid_cameras = {}
        
        for camera_name, camera_config in cameras_config.items():
            if self.validate_camera_config(camera_name, camera_config):
                valid_cameras[camera_name] = camera_config
            else:
                print(f"Skipping invalid camera: {camera_name}")
        
        return valid_cameras

    def validate_camera_config(self, camera_name, camera_config):
        """Validate that a camera configuration has the required structure"""
        try:
            # Must be a dictionary
            if not isinstance(camera_config, dict):
                return False
            
            # Must have ffmpeg section with inputs
            ffmpeg = camera_config.get("ffmpeg", {})
            if not isinstance(ffmpeg, dict):
                return False
            
            inputs = ffmpeg.get("inputs", [])
            if not isinstance(inputs, list) or not inputs:
                return False
            
            # First input must have a valid path
            first_input = inputs[0]
            if not isinstance(first_input, dict):
                return False
            
            path = first_input.get("path", "")
            if not path or not isinstance(path, str):
                return False
            
            # Path should be a valid RTSP URL (basic validation)
            if not (path.startswith("rtsp://") or path.startswith("http://") or path.startswith("/dev/")):
                return False
            
            # Check for placeholder URLs - reject template configurations
            placeholder_indicators = ["username:password", "camera_ip", "your_camera_ip", "your_ip_here", "example.com"]
            for placeholder in placeholder_indicators:
                if placeholder in path.lower():
                    print(f"Skipping camera {camera_name}: contains placeholder URL ({placeholder})")
                    return False
            
            # Camera name should be valid
            if not camera_name or not isinstance(camera_name, str) or camera_name.strip() == "":
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating camera {camera_name}: {e}")
            return False

    def extract_valid_cameras(self, config):
        """Extract and validate camera configurations from the config"""
        if not config or not isinstance(config, dict):
            return {}
        
        cameras_config = config.get("cameras", {})
        if not isinstance(cameras_config, dict):
            return {}
        
        valid_cameras = {}
        
        for camera_name, camera_config in cameras_config.items():
            if self.validate_camera_config(camera_name, camera_config):
                valid_cameras[camera_name] = camera_config
            else:
                print(f"Skipping invalid camera: {camera_name}")
        
        return valid_cameras

    def validate_camera_config(self, camera_name, camera_config):
        """Validate that a camera configuration has the required structure"""
        try:
            # Must be a dictionary
            if not isinstance(camera_config, dict):
                return False
            
            # Must have ffmpeg section with inputs
            ffmpeg = camera_config.get("ffmpeg", {})
            if not isinstance(ffmpeg, dict):
                return False
            
            inputs = ffmpeg.get("inputs", [])
            if not isinstance(inputs, list) or not inputs:
                return False
            
            # First input must have a valid path
            first_input = inputs[0]
            if not isinstance(first_input, dict):
                return False
            
            path = first_input.get("path", "")
            if not path or not isinstance(path, str):
                return False
            
            # Path should be a valid RTSP URL (basic validation)
            if not (path.startswith("rtsp://") or path.startswith("http://") or path.startswith("/dev/")):
                return False
            
            # Check for placeholder URLs - reject template configurations
            placeholder_indicators = ["username:password", "camera_ip", "your_camera_ip", "your_ip_here", "example.com"]
            for placeholder in placeholder_indicators:
                if placeholder in path.lower():
                    print(f"Skipping camera {camera_name}: contains placeholder URL ({placeholder})")
                    return False
            
            # Camera name should be valid
            if not camera_name or not isinstance(camera_name, str) or camera_name.strip() == "":
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating camera {camera_name}: {e}")
            return False

    def detect_manual_url(self, camera_url, username, password, ip_address):
        """Detect if a camera URL was manually entered vs auto-generated
        
        Strategy: If the URL field was manually enabled and contains user credentials,
        treat it as manual. This is more reliable than pattern matching since users
        often modify auto-generated URLs (e.g., changing substream from 0 to 1).
        """
        if not camera_url or not camera_url.strip():
            return False
            
        # If the URL contains the user's credentials, it's likely been customized
        # This handles cases where users modify auto-generated URLs
        if username and password and ip_address:
            # Check if URL contains the user's actual credentials and IP
            credentials_in_url = f"{username}:{password}@{ip_address}" in camera_url
            if credentials_in_url:
                # If it contains their credentials, assume it was manually set/modified
                # This covers both completely manual URLs and modified auto-generated ones
                return True
        
        # If URL exists but doesn't contain user credentials, check if it looks like
        # a standard auto-generated pattern that hasn't been customized
        if camera_url.startswith("rtsp://"):
            # Very basic auto-generated patterns that are clearly not customized
            basic_patterns = [
                "rtsp://admin:password@",
                "rtsp://user:pass@", 
                "rtsp://username:password@"
            ]
            for pattern in basic_patterns:
                if pattern in camera_url:
                    return False  # Clearly auto-generated placeholder
        
        # Default to manual if URL exists and we can't determine it's auto-generated
        return bool(camera_url.strip())

    def rebuild_camera_tabs_with_existing_data(self, existing_cameras):
        """Rebuild camera tabs with existing camera data"""
        camera_list = list(existing_cameras.items())
        
        # Clear existing tabs
        self.cams_subtabs.clear()
        self.camera_tabs.clear()
        
        # Clear delete buttons list for rebuild
        if hasattr(self, 'delete_buttons'):
            self.delete_buttons.clear()
        else:
            self.delete_buttons = []
        
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
            record_alerts_days = record_config.get("alerts", {}).get("retain", {}).get("days", 1)
            record_detections_days = record_config.get("detections", {}).get("retain", {}).get("days", 1)
            
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
            
            # Determine if URL field should be enabled (manual) or disabled (auto-generated)
            # Check if the URL looks like it was manually entered vs auto-generated
            is_manual_url = self.detect_manual_url(camera_url, username, password, ip_address)
            camera_url_field.setEnabled(is_manual_url)
            
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
                    try:
                        if not url_field.isEnabled():  # Only auto-generate if URL field is disabled
                            user = u_field.text().strip()
                            pwd = p_field.text().strip()
                            ip = i_field.text().strip()
                            if user and pwd and ip:
                                # Check if we have manufacturer-specific RTSP patterns
                                manufacturer = None
                                rtsp_patterns = None
                                
                                # Try multiple fields for manufacturer info
                                for field in [i_field, u_field, p_field]:
                                    if hasattr(field, 'property'):
                                        manufacturer = field.property('discovered_manufacturer')
                                        rtsp_patterns = field.property('rtsp_patterns')
                                        if manufacturer and rtsp_patterns:
                                            break
                                
                                if manufacturer and rtsp_patterns and rtsp_patterns.get('manufacturer_detected'):
                                    # Use manufacturer-specific URL pattern
                                    rtsp_info = self.generate_manufacturer_rtsp_url(ip, manufacturer, user, pwd)
                                    rtsp_url = rtsp_info['default_url']
                                    # Hide manufacturer selection since we know the manufacturer
                                    if hasattr(url_field, 'manufacturer_selection_frame'):
                                        url_field.manufacturer_selection_frame.hide()
                                else:
                                    # Show manufacturer selection UI for unknown manufacturers
                                    if hasattr(url_field, 'manufacturer_selection_frame'):
                                        url_field.manufacturer_selection_frame.show()
                                        # Reset dropdown to default
                                        url_field.manufacturer_combo.setCurrentIndex(0)
                                        url_field.manual_url_section.hide()
                                        return  # Don't set URL yet, wait for user selection
                                    else:
                                        # Fallback if UI elements don't exist
                                        generic_fallback = self.generate_manufacturer_rtsp_url(ip, "Unknown", user, pwd)
                                        rtsp_url = generic_fallback['default_url']
                                
                                url_field.setText(rtsp_url)
                            else:
                                url_field.setText("")
                        self.mark_as_changed()
                    except Exception as e:
                        print(f"Error updating RTSP URL (manual setup): {e}")
                        import traceback
                        traceback.print_exc()
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
            
            # IP Address with ONVIF Discovery button (moved to be first)
            ip_layout = QHBoxLayout()
            ip_layout.addWidget(ip_address_field)
            
            onvif_btn = QPushButton("🔍 Discover Cameras")
            onvif_btn.setMaximumWidth(160)
            onvif_btn.setMinimumHeight(36)
            onvif_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    margin-left: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d4ed8, stop:1 #1e40af);
                }
            """)
            
            def open_onvif_discovery():
                """Open ONVIF discovery dialog"""
                dialog = ONVIFDiscoveryDialog(self)
                dialog.camera_selected.connect(lambda camera_info: self.on_camera_discovered(
                    camera_info, ip_address_field, username_field, password_field, camera_url_field
                ))
                dialog.exec()
            
            onvif_btn.clicked.connect(open_onvif_discovery)
            ip_layout.addWidget(onvif_btn)
            
            form.addRow("IP Address", ip_layout)
            form.addRow("Username", username_field)
            form.addRow("Password", password_field)
            
            # Hidden manufacturer selection (only shown when manufacturer is unknown)
            manufacturer_selection_frame = QFrame()
            manufacturer_selection_frame.setStyleSheet("""
                QFrame {
                    background-color: #fef3c7;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 12px;
                    margin: 8px 0;
                }
            """)
            manufacturer_selection_layout = QVBoxLayout(manufacturer_selection_frame)
            manufacturer_selection_layout.setSpacing(10)
            manufacturer_selection_layout.setContentsMargins(12, 12, 12, 12)
            
            # Header with icon
            unknown_header = QLabel("🔍 Unknown Camera Manufacturer Detected")
            unknown_header.setStyleSheet("font-weight: bold; color: #856404; font-size: 13px;")
            manufacturer_selection_layout.addWidget(unknown_header)
            
            # Manufacturer dropdown
            manufacturer_combo_layout = QHBoxLayout()
            manufacturer_combo_label = QLabel("Select Manufacturer:")
            manufacturer_combo = QComboBox()
            manufacturer_combo.addItems([
                "-- Select Camera Brand --",
                "Hikvision", "Dahua", "Amcrest", "Reolink", 
                "Axis", "Foscam", "Vivotek", "Bosch", 
                "Sony", "Uniview", "-- None of the above --"
            ])
            manufacturer_combo.setStyleSheet("""
                QComboBox {
                    padding: 5px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                    min-width: 200px;
                }
                QComboBox:hover {
                    border-color: #3498db;
                }
            """)
            manufacturer_combo_layout.addWidget(manufacturer_combo_label)
            manufacturer_combo_layout.addWidget(manufacturer_combo)
            manufacturer_combo_layout.addStretch()
            manufacturer_selection_layout.addLayout(manufacturer_combo_layout)
            
            # Manual URL section (hidden by default)
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
            manual_url_header.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px;")
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
            manufacturer_selection_layout.addWidget(manual_url_section)
            
            # Hide the entire selection frame by default
            manufacturer_selection_frame.hide()
            
            # Store references for later use
            camera_url_field.manufacturer_selection_frame = manufacturer_selection_frame
            camera_url_field.manufacturer_combo = manufacturer_combo
            camera_url_field.manual_url_section = manual_url_section
            camera_url_field.custom_url_field = custom_url_field
            
            # Add manufacturer selection frame to form
            form.addRow("", manufacturer_selection_frame)
            
            # Manufacturer selection change handler
            def on_manufacturer_selected():
                selected = manufacturer_combo.currentText()
                if selected == "-- None of the above --":
                    manual_url_section.show()
                    camera_url_field.setEnabled(False)  # Disable auto URL
                    custom_url_field.setFocus()
                elif selected != "-- Select Camera Brand --":
                    manual_url_section.hide()
                    # Auto-generate URL for selected manufacturer immediately
                    user = username_field.text().strip()
                    pwd = password_field.text().strip()
                    ip = ip_address_field.text().strip()
                    
                    # Generate URL even if credentials are empty (will update when filled)
                    if ip:  # Only need IP to generate URL structure
                        rtsp_info = self.generate_manufacturer_rtsp_url(
                            ip, selected, 
                            user if user else "admin",  # Use placeholder if empty
                            pwd if pwd else "password"   # Use placeholder if empty
                        )
                        camera_url_field.setText(rtsp_info['default_url'])
                        camera_url_field.setEnabled(False)  # Keep auto-generated
                        
                        # Update stored manufacturer info for future updates
                        ip_address_field.setProperty('discovered_manufacturer', selected)
                        username_field.setProperty('discovered_manufacturer', selected)
                        password_field.setProperty('discovered_manufacturer', selected)
                        
                        manufacturer_patterns = {
                            'manufacturer_detected': True,
                            'patterns': {selected.lower(): rtsp_info['default_url']}
                        }
                        ip_address_field.setProperty('rtsp_patterns', manufacturer_patterns)
                        username_field.setProperty('rtsp_patterns', manufacturer_patterns)
                        password_field.setProperty('rtsp_patterns', manufacturer_patterns)
                        
                        # Hide the selection UI since we now have a manufacturer
                        manufacturer_selection_frame.hide()
                    else:
                        camera_url_field.setText("")
                else:
                    manual_url_section.hide()
                    camera_url_field.setText("")
                self.mark_as_changed()
            
            manufacturer_combo.currentTextChanged.connect(on_manufacturer_selected)
            
            # Custom URL field change handler
            def on_custom_url_changed():
                if custom_url_field.text().strip():
                    camera_url_field.setText(custom_url_field.text())
                self.mark_as_changed()
            
            custom_url_field.textChanged.connect(on_custom_url_changed)
            
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
            
            # Add delete camera button
            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: #f8d7da;
                    color: #721c24;
                    padding: 6px 12px;
                    border: 1px solid #f5c6cb;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                    margin-top: 5px;
                    min-width: 80px;
                    max-width: 100px;
                }
                QPushButton:hover {
                    background: #f1b0b7;
                    border-color: #f1b0b7;
                }
                QPushButton:pressed {
                    background: #ea868f;
                    border-color: #ea868f;
                }
            """)
            
            # Create a closure that captures the current widget correctly
            def create_delete_function(widget, name_field):
                def delete_camera():
                    """Delete this specific camera"""
                    # Get current camera index using the captured widget
                    current_index = self.cams_subtabs.indexOf(widget)
                    if current_index >= 0:
                        # Show confirmation dialog
                        camera_name_text = name_field.text() or f"Camera {current_index + 1}"
                        reply = QMessageBox.question(
                            self, "Delete Camera",
                            f"Are you sure you want to delete '{camera_name_text}'?\n\n"
                            "This action cannot be undone.",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            # Remove the tab and camera data
                            self.cams_subtabs.removeTab(current_index)
                            self.camera_tabs.pop(current_index)
                            
                            # Remove the corresponding delete button from the list
                            if hasattr(self, 'delete_buttons') and current_index < len(self.delete_buttons):
                                self.delete_buttons.pop(current_index)
                            
                            # Update camera count spinner
                            self.cams_count.setValue(len(self.camera_tabs))
                            
                            # Update delete button visibility
                            self.update_delete_buttons_visibility()
                            
                            # Mark as changed
                            self.mark_as_changed()
                            
                            # If there are still cameras, switch to a nearby tab
                            if self.camera_tabs:
                                # Switch to previous tab if available, otherwise first tab
                                new_index = min(current_index, len(self.camera_tabs) - 1)
                                self.cams_subtabs.setCurrentIndex(new_index)
                return delete_camera
            
            delete_btn.clicked.connect(create_delete_function(cam_widget, camera_name_field))
            
            # Always add delete button to form, but control visibility dynamically
            form.addRow("", delete_btn)
            
            # Store reference to delete button for visibility control
            if not hasattr(self, 'delete_buttons'):
                self.delete_buttons = []
            self.delete_buttons.append(delete_btn)

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
        
        # Update delete button visibility after rebuilding all cameras
        self.update_delete_buttons_visibility()

    def mark_as_changed(self):
        """Mark that the configuration has unsaved changes"""
        self.has_unsaved_changes = True

    def on_camera_discovered(self, camera_info, ip_field, username_field, password_field, url_field):
        """Handle discovered camera from ONVIF"""
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
                    url_field.manual_url_section.hide()
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

    def update_delete_buttons_visibility(self):
        """Update visibility of all delete buttons based on camera count"""
        if hasattr(self, 'delete_buttons'):
            camera_count = len(self.camera_tabs)
            show_buttons = camera_count > 1
            
            for delete_btn in self.delete_buttons:
                delete_btn.setVisible(show_buttons)

    def on_camera_count_changed(self, count):
        """Handle camera count change"""
        # Store the current tab count before rebuilding
        old_count = self.cams_subtabs.count() if hasattr(self, 'cams_subtabs') else 0
        
        self.rebuild_camera_tabs(count)
        self.mark_as_changed()
        
        # Update delete button visibility after rebuilding
        self.update_delete_buttons_visibility()
        
        # If we added new tabs (count increased), switch to the last (newest) tab
        if count > old_count and count > 0:
            # Switch to the last tab (newly created camera)
            self.cams_subtabs.setCurrentIndex(count - 1)

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
                "camera_url_enabled": cam["camera_url"].isEnabled(),  # Save enabled state
                "objects": cam["objects"].toPlainText(),
                "record_enabled": cam["record_enabled"].isChecked(),
                "record_alerts": cam["record_alerts"].value(),
                "record_detections": cam["record_detections"].value(),
            })

        # Step 2: Clear tabs and rebuild
        self._restoring_data = True  # Flag to prevent auto-generation during restoration
        self.cams_subtabs.clear()
        self.camera_tabs.clear()
        
        # Clear delete buttons list for rebuild
        if hasattr(self, 'delete_buttons'):
            self.delete_buttons.clear()
        else:
            self.delete_buttons = []

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
            # Create scroll area for each camera form
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

            # Camera Name - automatically generated with responsive sizing + validation
            camera_name = QLineEdit(data.get("camera_name", f"camera_{idx+1}"))
            camera_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setup_field_validation(camera_name, self.validate_camera_name, 'camera_name')
            
            # Username - responsive + validation
            username = QLineEdit(data.get("username", ""))
            username.setPlaceholderText("Enter camera username (required)")
            username.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setup_field_validation(username, self.validate_username, 'username')
            
            # Password - open text as requested - responsive + validation
            password = QLineEdit(data.get("password", ""))
            password.setPlaceholderText("Enter camera password (required)")
            password.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setup_field_validation(password, self.validate_password, 'password')
            
            # IP Address - responsive + validation
            ip_address = QLineEdit(data.get("ip_address", ""))
            ip_address.setPlaceholderText("192.168.1.100 (required)")
            ip_address.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setup_field_validation(ip_address, self.validate_ip_address, 'ip_address')
            
            # Camera URL - optional, disabled by default - responsive + validation
            camera_url = QLineEdit(data.get("camera_url", ""))
            camera_url.setPlaceholderText("rtsp://username:password@ip:port/cam/realmonitor?channel=1&subtype=0 (auto-generated)")
            # Restore the enabled state (default to disabled if not saved)
            camera_url.setEnabled(data.get("camera_url_enabled", False))
            camera_url.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setup_field_validation(camera_url, self.validate_rtsp_url, 'camera_url')
            
            # Objects to track - responsive + validation
            objects = QTextEdit(data.get("objects", "person,car,dog"))
            objects.setMinimumHeight(100)
            objects.setMaximumHeight(200)
            objects.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            objects.setStyleSheet("font-size: 14px; font-family: 'Segoe UI', 'Inter', sans-serif;")
            objects.setPlaceholderText("Enter objects to detect (comma-separated): person,car,dog,cat,bicycle")
            self.setup_field_validation(objects, self.validate_objects_list, 'objects')
            
            # Record option - disabled by default
            record_enabled = QCheckBox("Enable Recording")
            record_enabled.setChecked(data.get("record_enabled", False))
            
            # Recording retention settings (hidden by default) - responsive
            record_alerts = QSpinBox()
            record_alerts.setRange(0, 365)
            record_alerts.setValue(data.get("record_alerts", 7))
            record_alerts.setSuffix(" days")
            record_alerts.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            record_detections = QSpinBox()
            record_detections.setRange(0, 365)
            record_detections.setValue(data.get("record_detections", 3))
            record_detections.setSuffix(" days")
            record_detections.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # Create container for recording settings - responsive
            record_settings_widget = QWidget()
            record_settings_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            record_settings_layout = QFormLayout(record_settings_widget)
            record_settings_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            record_settings_layout.setContentsMargins(20, 0, 0, 0)
            record_settings_layout.addRow("Days to keep alert recordings:", record_alerts)
            record_settings_layout.addRow("Days to keep detection recordings:", record_detections)
            record_settings_widget.setVisible(False)  # Hidden by default
            
            # Connect record checkbox to show/hide retention settings
            record_enabled.toggled.connect(record_settings_widget.setVisible)
            
            # Auto-generate RTSP URL when username, password, or IP changes
            def update_rtsp_url():
                try:
                    # Skip auto-generation if we're currently restoring data
                    if hasattr(self, '_restoring_data') and self._restoring_data:
                        return
                        
                    if not camera_url.isEnabled():  # Only auto-generate if URL field is disabled
                        user = username.text().strip()
                        pwd = password.text().strip()
                        ip = ip_address.text().strip()
                        if user and pwd and ip:
                            # Check if we have manufacturer-specific RTSP patterns
                            manufacturer = None
                            rtsp_patterns = None
                            
                            # Try multiple fields for manufacturer info
                            for field in [ip_address, username, password]:
                                if hasattr(field, 'property'):
                                    manufacturer = field.property('discovered_manufacturer')
                                    rtsp_patterns = field.property('rtsp_patterns')
                                    if manufacturer and rtsp_patterns:
                                        break
                            
                            if manufacturer and rtsp_patterns and rtsp_patterns.get('manufacturer_detected'):
                                # Use manufacturer-specific URL pattern
                                rtsp_info = self.generate_manufacturer_rtsp_url(ip, manufacturer, user, pwd)
                                rtsp_url = rtsp_info['default_url']
                                # Hide manufacturer selection since we know the manufacturer
                                if hasattr(camera_url, 'manufacturer_selection_frame'):
                                    camera_url.manufacturer_selection_frame.hide()
                            else:
                                # Show manufacturer selection UI for unknown manufacturers
                                if hasattr(camera_url, 'manufacturer_selection_frame'):
                                    camera_url.manufacturer_selection_frame.show()
                                    # Reset dropdown to default
                                    camera_url.manufacturer_combo.setCurrentIndex(0)
                                    camera_url.manual_url_section.hide()
                                    return  # Don't set URL yet, wait for user selection
                                else:
                                    # Fallback if UI elements don't exist
                                    generic_fallback = self.generate_manufacturer_rtsp_url(ip, "Unknown", user, pwd)
                                    rtsp_url = generic_fallback['default_url']
                            
                            camera_url.setText(rtsp_url)
                        else:
                            camera_url.setText("")
                    self.mark_as_changed()
                except Exception as e:
                    print(f"Error updating RTSP URL (advanced setup): {e}")
                    import traceback
                    traceback.print_exc()
            
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
            
            # IP Address with ONVIF Discovery button (moved to be first)
            ip_layout_adv = QHBoxLayout()
            ip_layout_adv.addWidget(ip_address)
            
            onvif_btn_adv = QPushButton("🔍 Discover Cameras")
            onvif_btn_adv.setMaximumWidth(150)
            onvif_btn_adv.setStyleSheet("""
                QPushButton {
                    background: #3498db;
                    color: white;
                    padding: 8px 14px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                    border: none;
                }
                QPushButton:hover {
                    background: #2980b9;
                }
                QPushButton:pressed {
                    background: #21618c;
                }
            """)
            
            def open_onvif_discovery_adv():
                """Open ONVIF discovery dialog for advanced setup"""
                dialog = ONVIFDiscoveryDialog(self)
                dialog.camera_selected.connect(lambda camera_info: self.on_camera_discovered(
                    camera_info, ip_address, username, password, camera_url
                ))
                dialog.exec()
            
            onvif_btn_adv.clicked.connect(open_onvif_discovery_adv)
            ip_layout_adv.addWidget(onvif_btn_adv)
            
            form.addRow("IP Address", ip_layout_adv)
            form.addRow("Username", username)
            form.addRow("Password", password)
            
            # Hidden manufacturer selection (only shown when manufacturer is unknown)
            manufacturer_selection_frame_adv = QFrame()
            manufacturer_selection_frame_adv.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 6px;
                    padding: 10px;
                    margin: 5px 0;
                }
            """)
            manufacturer_selection_layout_adv = QVBoxLayout(manufacturer_selection_frame_adv)
            
            # Header with icon
            unknown_header_adv = QLabel("🔍 Unknown Camera Manufacturer Detected")
            unknown_header_adv.setStyleSheet("font-weight: bold; color: #856404; font-size: 13px;")
            manufacturer_selection_layout_adv.addWidget(unknown_header_adv)
            
            # Manufacturer dropdown
            manufacturer_combo_layout_adv = QHBoxLayout()
            manufacturer_combo_label_adv = QLabel("Select Manufacturer:")
            manufacturer_combo_adv = QComboBox()
            manufacturer_combo_adv.addItems([
                "-- Select Camera Brand --",
                "Hikvision", "Dahua", "Amcrest", "Reolink", 
                "Axis", "Foscam", "Vivotek", "Bosch", 
                "Sony", "Uniview", "-- None of the above --"
            ])
            manufacturer_combo_adv.setStyleSheet("""
                QComboBox {
                    padding: 5px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                    min-width: 200px;
                }
                QComboBox:hover {
                    border-color: #3498db;
                }
            """)
            manufacturer_combo_layout_adv.addWidget(manufacturer_combo_label_adv)
            manufacturer_combo_layout_adv.addWidget(manufacturer_combo_adv)
            manufacturer_combo_layout_adv.addStretch()
            manufacturer_selection_layout_adv.addLayout(manufacturer_combo_layout_adv)
            
            # Manual URL section (hidden by default)
            manual_url_section_adv = QFrame()
            manual_url_section_adv.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 5px;
                }
            """)
            manual_url_layout_adv = QVBoxLayout(manual_url_section_adv)
            manual_url_header_adv = QLabel("✏️ Enter Custom Camera URL:")
            manual_url_header_adv.setStyleSheet("font-weight: bold; color: #495057; font-size: 12px;")
            manual_url_layout_adv.addWidget(manual_url_header_adv)
            
            custom_url_field_adv = QLineEdit()
            custom_url_field_adv.setPlaceholderText("rtsp://username:password@ip:554/your/camera/path")
            custom_url_field_adv.setStyleSheet("""
                QLineEdit {
                    padding: 6px 10px;
                    border: 1px solid #ced4da;
                    border-radius: 4px;
                    font-family: monospace;
                }
            """)
            manual_url_layout_adv.addWidget(custom_url_field_adv)
            manual_url_section_adv.hide()  # Hidden by default
            manufacturer_selection_layout_adv.addWidget(manual_url_section_adv)
            
            # Hide the entire selection frame by default
            manufacturer_selection_frame_adv.hide()
            
            # Store references for later use
            camera_url.manufacturer_selection_frame = manufacturer_selection_frame_adv
            camera_url.manufacturer_combo = manufacturer_combo_adv
            camera_url.manual_url_section = manual_url_section_adv
            camera_url.custom_url_field = custom_url_field_adv
            
            # Add manufacturer selection frame to form
            form.addRow("", manufacturer_selection_frame_adv)
            
            # Manufacturer selection change handler
            def on_manufacturer_selected_adv():
                selected = manufacturer_combo_adv.currentText()
                if selected == "-- None of the above --":
                    manual_url_section_adv.show()
                    camera_url.setEnabled(False)  # Disable auto URL
                    custom_url_field_adv.setFocus()
                elif selected != "-- Select Camera Brand --":
                    manual_url_section_adv.hide()
                    # Auto-generate URL for selected manufacturer immediately
                    user = username.text().strip()
                    pwd = password.text().strip()
                    ip = ip_address.text().strip()
                    
                    # Generate URL even if credentials are empty (will update when filled)
                    if ip:  # Only need IP to generate URL structure
                        rtsp_info = self.generate_manufacturer_rtsp_url(
                            ip, selected, 
                            user if user else "admin",  # Use placeholder if empty
                            pwd if pwd else "password"   # Use placeholder if empty
                        )
                        camera_url.setText(rtsp_info['default_url'])
                        camera_url.setEnabled(False)  # Keep auto-generated
                        
                        # Update stored manufacturer info for future updates
                        ip_address.setProperty('discovered_manufacturer', selected)
                        username.setProperty('discovered_manufacturer', selected)
                        password.setProperty('discovered_manufacturer', selected)
                        
                        manufacturer_patterns = {
                            'manufacturer_detected': True,
                            'patterns': {selected.lower(): rtsp_info['default_url']}
                        }
                        ip_address.setProperty('rtsp_patterns', manufacturer_patterns)
                        username.setProperty('rtsp_patterns', manufacturer_patterns)
                        password.setProperty('rtsp_patterns', manufacturer_patterns)
                        
                        # Hide the selection UI since we now have a manufacturer
                        manufacturer_selection_frame_adv.hide()
                    else:
                        camera_url.setText("")
                else:
                    manual_url_section_adv.hide()
                    camera_url.setText("")
                self.mark_as_changed()
            
            manufacturer_combo_adv.currentTextChanged.connect(on_manufacturer_selected_adv)
            
            # Custom URL field change handler
            def on_custom_url_changed_adv():
                if custom_url_field_adv.text().strip():
                    camera_url.setText(custom_url_field_adv.text())
                self.mark_as_changed()
            
            custom_url_field_adv.textChanged.connect(on_custom_url_changed_adv)
            
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
                    enable_url_btn.setText("🔗 Enable Manual URL")
                    # Auto-generate URL when switching back to auto mode
                    user = username.text().strip()
                    pwd = password.text().strip()
                    ip = ip_address.text().strip()
                    if user and pwd and ip:
                        # Check for manufacturer-specific patterns
                        manufacturer = ip_address.property('discovered_manufacturer')
                        rtsp_patterns = ip_address.property('rtsp_patterns')
                        
                        if manufacturer and rtsp_patterns and rtsp_patterns.get('manufacturer_detected'):
                            rtsp_info = self.generate_manufacturer_rtsp_url(ip, manufacturer, user, pwd)
                            camera_url.setText(rtsp_info['default_url'])
                        else:
                            # Use consistent generic fallback
                            generic_fallback = self.generate_manufacturer_rtsp_url(ip, "Unknown", user, pwd)
                            camera_url.setText(generic_fallback['default_url'])
                else:
                    camera_url.setEnabled(True)
                    enable_url_btn.setText("✨ Auto Generate URL")
                    camera_url.setFocus()
                self.mark_as_changed()
            enable_url_btn.clicked.connect(toggle_url_field)
            
            # Set button text based on restored enabled state
            if camera_url.isEnabled():
                enable_url_btn.setText("✨ Auto Generate URL")
            else:
                enable_url_btn.setText("🔗 Enable Manual URL")
            
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
            
            # Add delete camera button
            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: #f8d7da;
                    color: #721c24;
                    padding: 6px 12px;
                    border: 1px solid #f5c6cb;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                    margin-top: 5px;
                    min-width: 80px;
                    max-width: 100px;
                }
                QPushButton:hover {
                    background: #f1b0b7;
                    border-color: #f1b0b7;
                }
                QPushButton:pressed {
                    background: #ea868f;
                    border-color: #ea868f;
                }
            """)
            
            # Create a closure that captures the current widget correctly
            def create_delete_function(widget, name_field):
                def delete_camera():
                    """Delete this specific camera"""
                    # Get current camera index using the captured widget
                    current_index = self.cams_subtabs.indexOf(widget)
                    if current_index >= 0:
                        # Show confirmation dialog
                        camera_name_text = name_field.text() or f"Camera {current_index + 1}"
                        reply = QMessageBox.question(
                            self, "Delete Camera",
                            f"Are you sure you want to delete '{camera_name_text}'?\n\n"
                            "This action cannot be undone.",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            # Remove the tab and camera data
                            self.cams_subtabs.removeTab(current_index)
                            self.camera_tabs.pop(current_index)
                            
                            # Remove the corresponding delete button from the list
                            if hasattr(self, 'delete_buttons') and current_index < len(self.delete_buttons):
                                self.delete_buttons.pop(current_index)
                            
                            # Update camera count spinner
                            self.cams_count.setValue(len(self.camera_tabs))
                            
                            # Update delete button visibility
                            self.update_delete_buttons_visibility()
                            
                            # Mark as changed
                            self.mark_as_changed()
                            
                            # If there are still cameras, switch to a nearby tab
                            if self.camera_tabs:
                                # Switch to previous tab if available, otherwise first tab
                                new_index = min(current_index, len(self.camera_tabs) - 1)
                                self.cams_subtabs.setCurrentIndex(new_index)
                return delete_camera
            
            delete_btn.clicked.connect(create_delete_function(cam_widget, camera_name))
            
            # Always add delete button to form, but control visibility dynamically
            form.addRow("", delete_btn)
            
            # Store reference to delete button for visibility control
            if not hasattr(self, 'delete_buttons'):
                self.delete_buttons = []
            self.delete_buttons.append(delete_btn)

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
        
        # Clear the restoration flag to re-enable auto-generation
        self._restoring_data = False

    def intelligent_config_reconstruction(self, config_content):
        """Reconstruct config from malformed YAML using intelligent parsing - preserve all sections"""
        try:
            # Start with a proper base config structure preserving essential sections
            config = {
                'mqtt': {'enabled': False},
                'detectors': {
                    'memx0': {
                        'type': 'memryx',
                        'device': 'PCIe:0'
                    }
                },
                'model': {
                    'model_type': 'yolo-generic',
                    'width': 320,
                    'height': 320,
                    'input_tensor': 'nchw',
                    'input_dtype': 'float',
                    'labelmap_path': '/labelmap/coco-80.txt'
                },
                'version': '0.17-0',
                'cameras': {}
            }
            
            # Parse the content line by line to extract existing sections and preserve them
            lines = config_content.split('\n')
            current_section = None
            current_camera = None
            current_subsection = None
            
            # First pass: extract non-camera sections to preserve them
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                
                if not stripped or stripped.startswith('#'):
                    i += 1
                    continue
                
                # Detect top-level sections
                if not line.startswith(' ') and line.endswith(':') and stripped != 'cameras:':
                    section_name = line.rstrip(':').strip()
                    
                    # Try to preserve existing section values
                    if section_name in ['mqtt', 'detectors', 'model', 'version']:
                        # Extract the section content 
                        section_content = {}
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            if not next_line.startswith(' ') and not next_line.startswith('\t') and next_line.strip().endswith(':'):
                                break  # Found next section
                            if next_line.strip() and not next_line.strip().startswith('#'):
                                # Simple key-value extraction
                                if ':' in next_line and next_line.startswith(' '):
                                    try:
                                        key_part = next_line.split(':')[0].strip()
                                        value_part = ':'.join(next_line.split(':')[1:]).strip()
                                        if value_part:
                                            # Convert basic types
                                            if value_part.lower() == 'true':
                                                section_content[key_part] = True
                                            elif value_part.lower() == 'false':
                                                section_content[key_part] = False
                                            elif value_part.isdigit():
                                                section_content[key_part] = int(value_part)
                                            else:
                                                section_content[key_part] = value_part
                                    except:
                                        pass
                            j += 1
                        
                        # Only update if we extracted something meaningful
                        if section_content:
                            config[section_name] = section_content
                
                i += 1
            
            # Second pass: parse cameras section  
            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                
                if not stripped or stripped.startswith('#'):
                    i += 1
                    continue
                
                # Detect cameras section
                if stripped == 'cameras:':
                    current_section = 'cameras'
                    current_camera = None
                    current_subsection = None
                    i += 1
                    continue
                
                # Parse cameras section
                if current_section == 'cameras':
                    # Camera name (no indentation and ends with :, but not comments or version)
                    if (not line.startswith(' ') and line.rstrip().endswith(':') and 
                        not stripped.startswith('#') and 'version:' not in stripped.lower()):
                        current_camera = line.strip().rstrip(':')
                        config['cameras'][current_camera] = {
                            'ffmpeg': {'inputs': []},
                            'detect': {},
                            'objects': {'track': []},
                            'snapshots': {},
                            'record': {},
                            'alerts': {'retain': {}},
                            'detections': {'retain': {}}
                        }
                        current_subsection = None
                        i += 1
                        continue
                    
                    # Handle malformed ffmpeg section
                    elif current_camera and stripped == 'ffmpeg:':
                        current_subsection = 'ffmpeg'
                        i += 1
                        continue
                    
                    # Handle malformed inputs section
                    elif current_camera and current_subsection == 'ffmpeg' and stripped == 'inputs:':
                        # Look for the malformed input structure
                        j = i + 1
                        input_entry = {}
                        
                        # Skip to "- path:" line
                        while j < len(lines) and lines[j].strip() != '- path:':
                            j += 1
                        
                        if j < len(lines):
                            j += 1  # Skip "- path:" line
                            # Get the actual path from next line
                            if j < len(lines):
                                path_line = lines[j].strip()
                                if path_line and not path_line.startswith('-'):
                                    input_entry['path'] = path_line
                                    j += 1
                        
                        # Look for roles section
                        while j < len(lines) and lines[j].strip() != 'roles:':
                            j += 1
                        
                        if j < len(lines):
                            j += 1  # Skip "roles:" line
                            # Collect roles
                            roles = []
                            while j < len(lines) and lines[j].strip().startswith('- '):
                                role = lines[j].strip()[2:]  # Remove '- '
                                roles.append(role)
                                j += 1
                            input_entry['roles'] = roles
                        
                        if input_entry:
                            config['cameras'][current_camera]['ffmpeg']['inputs'].append(input_entry)
                        
                        i = j
                        current_subsection = None
                        continue
                    
                    # Handle other subsections
                    elif current_camera and stripped.endswith(':') and not stripped.startswith('-'):
                        subsection_name = stripped.rstrip(':')
                        current_subsection = subsection_name
                        i += 1
                        continue
                    
                    # Handle properties within subsections
                    elif current_camera and current_subsection and ':' in stripped and not stripped.startswith('-'):
                        key, value = stripped.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle different value types
                        if value.lower() in ['true', 'false']:
                            value = value.lower() == 'true'
                        elif value.isdigit():
                            value = int(value)
                        elif value.replace('.', '').replace('-', '').isdigit() and '.' in value and '-' not in value:
                            # Only convert to float if it's a proper decimal number (not version strings like "0.17-0")
                            value = float(value)
                        elif not value:  # Empty value
                            value = ""
                        
                        # Place in appropriate subsection
                        if current_subsection in config['cameras'][current_camera]:
                            if isinstance(config['cameras'][current_camera][current_subsection], dict):
                                config['cameras'][current_camera][current_subsection][key] = value
                        
                        i += 1
                        continue
                    
                    # Handle list items (like track objects)
                    elif current_camera and current_subsection and stripped.startswith('- '):
                        item = stripped[2:]  # Remove '- '
                        
                        # Add to track list if in objects section
                        if current_subsection == 'track' and 'objects' in config['cameras'][current_camera]:
                            if 'track' not in config['cameras'][current_camera]['objects']:
                                config['cameras'][current_camera]['objects']['track'] = []
                            config['cameras'][current_camera]['objects']['track'].append(item)
                        
                        i += 1
                        continue
                
                i += 1
            
            # Now validate cameras - remove any that don't have proper RTSP paths
            valid_cameras = {}
            for camera_name, camera_config in config['cameras'].items():
                if self._is_valid_camera(camera_config):
                    valid_cameras[camera_name] = camera_config
            
            config['cameras'] = valid_cameras
            return config  # Always return the config structure, even if cameras is empty
            
        except Exception as e:
            return None

    def _is_valid_camera(self, camera_config):
        """Check if a camera configuration is valid (has proper RTSP path)"""
        try:
            # Check if ffmpeg inputs exist and have a valid path
            if 'ffmpeg' not in camera_config or 'inputs' not in camera_config['ffmpeg']:
                return False
                
            inputs = camera_config['ffmpeg']['inputs']
            if not inputs or not isinstance(inputs, list):
                return False
                
            # Check if any input has a valid RTSP path
            for inp in inputs:
                if isinstance(inp, dict) and 'path' in inp:
                    path = inp['path'].strip()
                    # Valid path should be an actual RTSP URL, not placeholder
                    if path and path.startswith('rtsp://'):
                        # Check for placeholder URLs - reject template configurations
                        placeholder_indicators = ["username:password", "camera_ip", "your_camera_ip", "your_ip_here", "example.com"]
                        is_placeholder = any(placeholder in path.lower() for placeholder in placeholder_indicators)
                        if not is_placeholder:
                            return True
            
            return False
        except Exception:
            return False

    def save_config(self):
        """Save configuration - preserve existing config and update only cameras section"""
        
        # ================================
        # VALIDATION STEP - Check all inputs before saving
        # ================================
        validation_errors = []
        invalid_cameras = []
        
        for idx, camera_tab in enumerate(self.camera_tabs):
            camera_name = camera_tab["camera_name"].text().strip()
            
            # Collect camera data for validation
            camera_data = {
                'camera_name': camera_tab["camera_name"].text(),
                'ip_address': camera_tab["ip_address"].text(),
                'username': camera_tab["username"].text(),
                'password': camera_tab["password"].text(),
                'camera_url': camera_tab["camera_url"].text(),
                'objects': camera_tab["objects"].toPlainText()
            }
            
            # Validate this camera's data
            is_valid, validation_results = self.validate_camera_form(camera_data)
            
            if not is_valid:
                invalid_cameras.append(camera_name or f"Camera {idx + 1}")
                for field_name, result in validation_results.items():
                    if not result['valid']:
                        for error in result['errors']:
                            validation_errors.append(f"📹 {camera_name or f'Camera {idx + 1}'} - {field_name}: {error}")
        
        # If there are validation errors, show them and abort save
        if validation_errors:
            error_message = "❌ Cannot save configuration due to validation errors:\n\n"
            error_message += "\n".join(validation_errors)
            error_message += f"\n\n🔧 Please fix the errors in: {', '.join(invalid_cameras)}"
            
            QMessageBox.warning(
                self, "Validation Errors", error_message
            )
            
            # Switch to the first invalid camera tab for easy fixing
            if invalid_cameras and self.camera_tabs:
                for idx, camera_tab in enumerate(self.camera_tabs):
                    if (camera_tab["camera_name"].text().strip() or f"Camera {idx + 1}") == invalid_cameras[0]:
                        self.cams_subtabs.setCurrentIndex(idx)
                        break
            
            return  # Don't save if validation fails
        
        # ================================
        # PROCEED WITH SAVE (validation passed)
        # ================================
        
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

        # Load and preserve existing configuration
        existing_config = self.load_existing_config_safely(config_path)
        if existing_config is None:
            return  # Error message already shown

        # Ensure essential sections exist even if config was empty or incomplete
        if not existing_config:
            existing_config = {}
            
        # Guarantee essential sections are present
        if 'mqtt' not in existing_config:
            existing_config['mqtt'] = {'enabled': False}
        
        # Check and fix detectors section structure
        if ('detectors' not in existing_config or 
            not isinstance(existing_config['detectors'], dict) or
            'memx0' not in existing_config['detectors']):
            # Fix malformed or missing detectors section
            existing_config['detectors'] = {
                'memx0': {
                    'type': 'memryx',
                    'device': 'PCIe:0'
                }
            }
        if 'model' not in existing_config:
            existing_config['model'] = {
                'model_type': 'yolo-generic',
                'width': 320,
                'height': 320,
                'input_tensor': 'nchw',
                'input_dtype': 'float',
                'labelmap_path': '/labelmap/coco-80.txt'
            }
        if 'version' not in existing_config:
            existing_config['version'] = '0.17-0'

        # Build cameras configuration from GUI
        cameras_config = self.build_cameras_config_from_gui()
        
        if not cameras_config:
            QMessageBox.warning(
                self, "No Camera Configuration", 
                "No valid camera configurations found in the GUI.\n\n"
                "Please configure at least one camera before saving."
            )
            return

        # Update only the cameras section in the existing config
        existing_config["cameras"] = cameras_config
        
        # Reorder config to ensure version appears at the end
        ordered_config = {}
        # Add sections in desired order
        for section in ['mqtt', 'detectors', 'model', 'cameras']:
            if section in existing_config:
                ordered_config[section] = existing_config[section]
        
        # Add any other sections we might have missed
        for key, value in existing_config.items():
            if key not in ['mqtt', 'detectors', 'model', 'cameras', 'version']:
                ordered_config[key] = value
        
        # Always add version at the end
        if 'version' in existing_config:
            ordered_config['version'] = existing_config['version']

        # Save the updated configuration
        try:
            # Suppress config change popup in parent launcher if available
            if hasattr(self, 'launcher_parent') and self.launcher_parent:
                self.launcher_parent.suppress_config_change_popup = True
            
            # Generate YAML string with spacing between cameras
            yaml_content = yaml.dump(ordered_config, Dumper=MyDumper, default_flow_style=False, sort_keys=False)
            yaml_content = MyDumper.add_camera_spacing(yaml_content)
            
            with open(config_path, 'w') as f:
                f.write(yaml_content)
            
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
            if hasattr(self, 'launcher_parent') and self.launcher_parent:
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
            if hasattr(self, 'launcher_parent') and self.launcher_parent:
                self.launcher_parent.suppress_config_change_popup = False

    def load_existing_config_safely(self, config_path):
        """Safely load existing config while preserving structure"""
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()
            
            # Check if file is empty
            if not config_content.strip():
                return {}
            
            try:
                config = yaml.safe_load(config_content)
                if config is None:
                    config = {}
                return config
            except yaml.YAMLError as yaml_error:
                # Try intelligent reconstruction
                config = self.intelligent_config_reconstruction(config_content)
                if config is None:
                    QMessageBox.critical(
                        self, "Configuration Load Error", 
                        f"Error parsing YAML configuration:\n{str(yaml_error)}\n\n"
                        "Please check if the config.yaml file is valid YAML format."
                    )
                    return None
                return config
                
        except FileNotFoundError:
            QMessageBox.critical(
                self, "File Not Found", 
                f"Configuration file not found:\n{config_path}"
            )
            return None
        except PermissionError:
            QMessageBox.critical(
                self, "Permission Error", 
                f"Permission denied reading config file:\n{config_path}\n\n"
                "Please check file permissions."
            )
            return None
        except Exception as e:
            QMessageBox.critical(
                self, "Configuration Load Error", 
                f"Error loading existing configuration:\n{str(e)}\n\n"
                "Please check if the config.yaml file is accessible."
            )
            return None

    def build_cameras_config_from_gui(self):
        """Build cameras configuration from current GUI state"""
        cameras_config = {}
        
        for cam in self.camera_tabs:
            try:
                camera_name = cam["camera_name"].text().strip()
                if not camera_name:
                    continue  # Skip cameras without names
                
                # Generate RTSP URL if not manually provided
                camera_url = cam["camera_url"].text().strip()
                if not camera_url or not cam["camera_url"].isEnabled():
                    # Auto-generate RTSP URL from username, password, IP
                    username = cam["username"].text().strip()
                    password = cam["password"].text().strip()
                    ip = cam["ip_address"].text().strip()
                    if username and password and ip:
                        camera_url = f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel=1&subtype=0"
                    else:
                        continue  # Skip cameras without valid connection info

                # Determine roles based on recording setting
                roles = ["detect"]
                if cam["record_enabled"].isChecked():
                    roles.append("record")

                # Build camera configuration
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
                        "width": 2560,
                        "height": 1440,
                        "fps": 5,
                        "enabled": True
                    },
                    "objects": {
                        "track": [obj.strip() for obj in cam["objects"].toPlainText().split(',') if obj.strip()]
                    },
                    "snapshots": {
                        "enabled": False,
                        "bounding_box": True,
                        "retain": {
                            "default": 0
                        }
                    }
                }

                # Add recording configuration if enabled
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

                cameras_config[camera_name] = cam_config
                
            except Exception as e:
                print(f"Error building config for camera: {e}")
                continue  # Skip this camera if there's an error

        return cameras_config

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - check for unsaved changes and cleanup threads"""
        
        # First, cleanup any running ONVIF discovery threads
        try:
            # Find any open ONVIF discovery dialogs and close them properly
            for child in self.findChildren(ONVIFDiscoveryDialog):
                try:
                    if child.worker and child.worker.isRunning():
                        child.worker.stop_discovery()
                        # Wait for thread to finish from dialog context, not thread context
                        if not child.worker.wait(1000):
                            child.worker.terminate()
                            child.worker.wait(500)
                    child.close()
                except Exception as e:
                    print(f"Error cleaning up ONVIF dialog: {e}")
                    
            # Force cleanup of any remaining threads
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().waitForDone(1000)
            
        except Exception as e:
            print(f"Error cleaning up ONVIF threads: {e}")
        
        # Check for unsaved changes
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
                # Clean up all threads before accepting close
                cleanup_all_threads()
                event.accept()  # Close without saving
            else:
                event.ignore()  # Don't close, let user save first
        else:
            # Clean up all threads before accepting close
            cleanup_all_threads()
            event.accept()  # No changes, safe to close

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Simple Camera GUI")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("MemryX")
    
    try:
        window = SimpleCameraGUI()
        window.show()
        
        result = app.exec()
        
        # Ensure all threads are cleaned up before exit
        cleanup_all_threads()
        
        sys.exit(result)
        
    except Exception as e:
        print(f"Application error: {e}")
        cleanup_all_threads()
        sys.exit(1)

if __name__ == "__main__":
    main()