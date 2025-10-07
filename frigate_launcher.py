#!/usr/bin/env python3
"""
MemryX + Frigate Launcher
A comprehensive GUI application for managing Frigate installation and configuration
"""

import sys
import os
import subprocess
import threading
import time
import glob
import getpass
import shutil
import tempfile
import webbrowser
import platform
from pathlib import Path

# Try to import psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Import required Qt modules
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QTabWidget, QTextEdit, QPushButton, QLabel, QProgressBar,
        QGroupBox, QFormLayout, QCheckBox, QMessageBox, QSplitter,
        QFrame, QScrollArea, QGridLayout, QSpacerItem, QSizePolicy,
        QDialog, QLineEdit, QDialogButtonBox, QFileDialog
    )
    from PySide6.QtCore import QThread, Signal, QTimer, Qt, QEvent
    from PySide6.QtGui import QFont, QPixmap, QPalette, QColor, QIcon
except ImportError as e:
    print("❌ Required GUI libraries are not available.")
    print("   Please run './launch.sh' to set up the environment properly.")
    print(f"   Error: {e}")
    sys.exit(1)

# Import Simple Camera GUI
try:
    from camera_gui import SimpleCameraGUI
except ImportError as e:
    print(f"Warning: Could not import SimpleCameraGUI: {e}")
    SimpleCameraGUI = None

# Import Advanced Config GUI
try:
    from advanced_config_gui import ConfigGUI
except ImportError as e:
    print(f"Warning: Could not import ConfigGUI: {e}")
    ConfigGUI = None

class PasswordDialog(QDialog):
    """Secure password input dialog for sudo operations"""
    
    def __init__(self, parent=None, operation_name="system operation"):
        super().__init__(parent)
        self.operation_name = operation_name
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Administrator Password Required")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(f"Administrator privileges are required for {self.operation_name}.\n"
                           "Please enter your password to continue:")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #2d3748;
                font-size: 12px;
                margin-bottom: 10px;
                padding: 10px;
                background: #f7fafc;
                border-radius: 6px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout.addWidget(info_label)
        
        # Password input
        password_layout = QHBoxLayout()
        password_label = QLabel("Password:")
        password_label.setMinimumWidth(80)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #cbd5e0;
                border-radius: 6px;
                font-size: 12px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #4299e1;
                outline: none;
            }
        """)
        self.password_input.returnPressed.connect(self.accept)
        
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)
        
        # Show password checkbox
        self.show_password_cb = QCheckBox("Show password")
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        self.show_password_cb.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                color: #4a5568;
                margin: 5px 0;
            }
        """)
        layout.addWidget(self.show_password_cb)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton[text="OK"] {
                background: #3182ce;
                color: white;
                border: none;
            }
            QPushButton[text="OK"]:hover {
                background: #2c5aa0;
            }
            QPushButton[text="Cancel"] {
                background: #e2e8f0;
                color: #4a5568;
                border: 1px solid #cbd5e0;
            }
            QPushButton[text="Cancel"]:hover {
                background: #cbd5e0;
            }
        """)
        layout.addWidget(button_box)
        
        # Focus on password input
        self.password_input.setFocus()
        
    def toggle_password_visibility(self, checked):
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
    
    def get_password(self):
        """Get the entered password"""
        return self.password_input.text()
    
    @staticmethod
    def get_sudo_password(parent=None, operation_name="system operation"):
        """Static method to get sudo password from user"""
        dialog = PasswordDialog(parent, operation_name)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_password()
        return None

class SystemPrereqInstallWorker(QThread):
    """Background worker for system prerequisite installations"""
    progress = Signal(str)
    finished = Signal(bool)
    
    def __init__(self, script_dir, install_type, sudo_password=None):
        super().__init__()
        self.script_dir = script_dir
        self.install_type = install_type  # 'git', 'build-tools'
        self.sudo_password = sudo_password
    
    def run(self):
        try:
            # Helper function to run sudo commands with password
            def run_sudo_command(cmd, input_text=None):
                if self.sudo_password:
                    # Use sudo -S to read password from stdin
                    sudo_cmd = ['sudo', '-S'] + cmd[1:]  # Remove 'sudo' from original cmd
                    password_input = f"{self.sudo_password}\n"
                    if input_text:
                        password_input += input_text
                    return subprocess.run(sudo_cmd, input=password_input, text=True, check=True, capture_output=True)
                else:
                    # Fallback to normal sudo (will work if terminal=true)
                    return subprocess.run(cmd, input=input_text, text=True, check=True, capture_output=True)
            
            if self.install_type == 'git':
                self._install_git(run_sudo_command)
            elif self.install_type == 'build-tools':
                self._install_build_tools(run_sudo_command)
            
            self.finished.emit(True)
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Command failed: {e.cmd}"
            if e.stderr:
                error_msg += f"\n   Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            self.progress.emit(error_msg)
            self.finished.emit(False)
            
        except Exception as e:
            self.progress.emit(f"❌ Installation error: {str(e)}")
            self.finished.emit(False)
    
    def _install_git(self, run_sudo_command):
        self.progress.emit("📦 Starting Git installation...")
        
        # Update package repositories
        self.progress.emit("🔄 Updating package repositories...")
        run_sudo_command(['sudo', 'apt', 'update'])
        
        # Install git
        self.progress.emit("📥 Installing Git...")
        run_sudo_command(['sudo', 'apt', 'install', '-y', 'git'])
        
        # Verify installation
        result = subprocess.run(['git', '--version'], capture_output=True, text=True, check=True)
        version = result.stdout.strip()
        self.progress.emit(f"✅ Git installed successfully: {version}")
    
    def _install_build_tools(self, run_sudo_command):
        self.progress.emit("🔧 Starting build tools installation...")
        
        # Update package repositories
        self.progress.emit("🔄 Updating package repositories...")
        run_sudo_command(['sudo', 'apt', 'update'])
        
        # Install essential build tools
        self.progress.emit("📥 Installing build essential packages...")
        run_sudo_command(['sudo', 'apt', 'install', '-y', 
                       'build-essential', 'cmake', 'pkg-config', 'curl', 'wget'])
        
        # Verify installation
        gcc_result = subprocess.run(['gcc', '--version'], capture_output=True, text=True, check=True)
        gcc_version = gcc_result.stdout.split('\n')[0]
        self.progress.emit(f"✅ GCC installed: {gcc_version}")
        
        make_result = subprocess.run(['make', '--version'], capture_output=True, text=True, check=True)
        make_version = make_result.stdout.split('\n')[0]
        self.progress.emit(f"✅ Make installed: {make_version}")
        
        cmake_result = subprocess.run(['cmake', '--version'], capture_output=True, text=True, check=True)
        cmake_version = cmake_result.stdout.split('\n')[0]
        self.progress.emit(f"✅ CMake installed: {cmake_version}")

class InstallWorker(QThread):
    """Background worker for installation tasks"""
    progress = Signal(str)  # Progress message
    finished = Signal(bool)  # Success/failure
    
    def __init__(self, script_dir, action_type='skip_frigate'):
        super().__init__()
        self.script_dir = script_dir
        self.action_type = action_type  # 'clone_only', 'update_only', 'skip_frigate'
        
    def run(self):
        try:
            # Check dependencies
            self.progress.emit("🔍 Checking system dependencies...")
            self._check_dependencies()
            
            # Setup Python environment
            self.progress.emit("🐍 Setting up Python virtual environment...")
            self._setup_python_env()
            
            # Handle Frigate repository based on action type
            if self.action_type == 'clone_only':
                self.progress.emit("📥 Cloning fresh Frigate repository...")
                self._clone_frigate()
            elif self.action_type == 'update_only':
                self.progress.emit("🔄 Updating existing Frigate repository...")
                self._update_frigate()
            elif self.action_type == 'skip_frigate':
                self.progress.emit("⏭️ Skipping Frigate repository setup...")
            
            self.progress.emit("✅ Setup completed successfully!")
            self.finished.emit(True)
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            self.progress.emit(error_msg)
            self.progress.emit("💡 Tip: Check the troubleshooting section in README.md")
            self.finished.emit(False)
    
    def _check_dependencies(self):
        # Check for required tools
        required = ['git', 'python3']
        for tool in required:
            result = subprocess.run(['which', tool], capture_output=True)
            if result.returncode != 0:
                raise Exception(f"{tool} is not installed. Please install it first.")
        
        # Special check for Docker with better verification
        docker_check = subprocess.run(['which', 'docker'], capture_output=True)
        if docker_check.returncode != 0:
            raise Exception("docker is not installed. Please install it first.")
        
        # Verify Docker is actually working
        try:
            version_check = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            if version_check.returncode != 0:
                raise Exception("Docker binary found but not working properly.")
        except subprocess.TimeoutExpired:
            raise Exception("Docker command timed out - Docker may not be properly installed.")
        except FileNotFoundError:
            raise Exception("Docker binary not found in PATH.")
        
        # Check if Docker service is running
        try:
            service_check = subprocess.run(['systemctl', 'is-active', 'docker'], 
                                         capture_output=True, text=True, timeout=5)
            if service_check.stdout.strip() != 'active':
                raise Exception("Docker service is not running. Please start it with: sudo systemctl start docker")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # If we can't check systemctl, try a simple docker command
            try:
                subprocess.run(['docker', 'info'], capture_output=True, timeout=5, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                raise Exception("Docker is installed but not accessible. You may need to add your user to the docker group or start the Docker service.")
        
        time.sleep(1)  # Simulate work
    
    def _setup_python_env(self):
        """Set up Python environment - skip if already properly configured"""
        venv_path = os.path.join(self.script_dir, '.venv')
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        
        # Check if environment already exists and is functional
        if os.path.exists(venv_path) and os.path.exists(pip_path):
            try:
                # Test if pip works
                result = subprocess.run([pip_path, '--version'], capture_output=True, timeout=10)
                if result.returncode == 0:
                    # Check if required packages are already installed
                    try:
                        result = subprocess.run([pip_path, 'show', 'PySide6', 'pyyaml'], 
                                              capture_output=True, timeout=10)
                        if result.returncode == 0:
                            self.progress.emit("✅ Python environment already configured and ready!")
                            return
                    except:
                        pass
            except:
                pass
        
        # Environment needs setup
        self.progress.emit("🏗️ Creating/updating Python virtual environment...")
        
        # Remove corrupted venv if exists
        if os.path.exists(venv_path):
            self.progress.emit("🗑️ Removing existing virtual environment...")
            import shutil
            shutil.rmtree(venv_path)
        
        # Create new venv
        self.progress.emit("🐍 Creating virtual environment...")
        subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True)
        
        # Install/upgrade requirements
        self.progress.emit("📦 Installing Python packages...")
        subprocess.run([pip_path, 'install', '--upgrade', 'pip'], check=True)
        subprocess.run([pip_path, 'install', 'PySide6', 'pyyaml'], check=True)
        
        self.progress.emit("✅ Python environment setup completed!")
    
    def _setup_frigate(self):
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if os.path.exists(frigate_path):
            # Check if it's a valid git repository
            try:
                # Check if .git directory exists
                git_dir = os.path.join(frigate_path, '.git')
                if not os.path.exists(git_dir):
                    self.progress.emit("⚠️ Frigate directory exists but is not a git repo, removing...")
                    import shutil
                    shutil.rmtree(frigate_path)
                    raise FileNotFoundError("Not a git repository")
                
                # Try to update existing repo
                self.progress.emit("🔄 Updating existing Frigate repository...")
                result = subprocess.run(['git', 'status'], cwd=frigate_path, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Repository is valid, try to fetch and pull
                    try:
                        # First fetch all remote changes
                        subprocess.run(['git', 'fetch', 'origin'], cwd=frigate_path, check=True)
                        
                        # Check current branch
                        branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                                     cwd=frigate_path, capture_output=True, text=True, check=True)
                        current_branch = branch_result.stdout.strip()
                        
                        if current_branch:
                            # Try to pull from the current branch
                            try:
                                subprocess.run(['git', 'pull', 'origin', current_branch], cwd=frigate_path, check=True)
                                self.progress.emit(f"✅ Frigate repository updated successfully! (branch: {current_branch})")
                            except subprocess.CalledProcessError:
                                # If pull fails, just use what we have
                                self.progress.emit(f"⚠️ Could not update branch {current_branch}, using existing version")
                        else:
                            self.progress.emit("⚠️ Repository in detached HEAD state, using existing version")
                    except subprocess.CalledProcessError as e:
                        self.progress.emit(f"⚠️ Could not update repository: {str(e)}, using existing version")
                else:
                    # Repository is corrupted, remove and re-clone
                    raise Exception("Repository is corrupted")
                    
            except (subprocess.CalledProcessError, Exception) as e:
                self.progress.emit(f"⚠️ Repository update failed: {str(e)}")
                self.progress.emit("🗑️ Removing corrupted repository...")
                import shutil
                shutil.rmtree(frigate_path)
                # Fall through to clone new repo
        
        # Clone new repo if directory doesn't exist or was removed
        if not os.path.exists(frigate_path):
            self.progress.emit("📥 Cloning Frigate repository...")
            try:
                subprocess.run([
                    'git', 'clone', 
                    'https://github.com/blakeblackshear/frigate.git',
                    frigate_path
                ], cwd=self.script_dir, check=True)
                self.progress.emit("✅ Frigate repository cloned successfully!")
            except subprocess.CalledProcessError as e:
                raise Exception(f"Failed to clone Frigate repository: {str(e)}")
        
    def _clone_frigate(self):
        """Clone a fresh Frigate repository, removing existing if present"""
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        # Remove existing directory if present
        if os.path.exists(frigate_path):
            self.progress.emit("🗑️ Removing existing Frigate directory...")
            import shutil
            shutil.rmtree(frigate_path)
        
        # Clone fresh repository
        self.progress.emit("📥 Cloning Frigate repository...")
        try:
            subprocess.run([
                'git', 'clone', 
                'https://github.com/blakeblackshear/frigate.git',
                frigate_path
            ], cwd=self.script_dir, check=True)
            self.progress.emit("✅ Frigate repository cloned successfully!")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to clone Frigate repository: {str(e)}")
        
        self._setup_config_directory(frigate_path)
        self._create_default_config(frigate_path)
    
    def _update_frigate(self):
        """Update existing Frigate repository"""
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if not os.path.exists(frigate_path):
            raise Exception("Frigate repository not found. Please use 'Clone Fresh' option instead.")
        
        # Check if it's a valid git repository
        git_dir = os.path.join(frigate_path, '.git')
        if not os.path.exists(git_dir):
            raise Exception("Frigate directory exists but is not a git repository. Please use 'Clone Fresh' option.")
        
        try:
            # Check repository status
            result = subprocess.run(['git', 'status'], cwd=frigate_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("Git repository is corrupted. Please use 'Clone Fresh' option.")
            
            # Check for local changes
            status_output = result.stdout
            if "Changes not staged" in status_output or "Changes to be committed" in status_output:
                self.progress.emit("⚠️ Local changes detected in repository")
                # Stash changes
                self.progress.emit("💾 Stashing local changes...")
                subprocess.run(['git', 'stash'], cwd=frigate_path, check=True)
            
            # Fetch latest changes
            self.progress.emit("📡 Fetching latest changes...")
            subprocess.run(['git', 'fetch', 'origin'], cwd=frigate_path, check=True)
            
            # Get current branch
            branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                         cwd=frigate_path, capture_output=True, text=True, check=True)
            current_branch = branch_result.stdout.strip()
            
            if current_branch:
                # Pull latest changes
                self.progress.emit(f"⬇️ Pulling latest changes for branch: {current_branch}")
                subprocess.run(['git', 'pull', 'origin', current_branch], cwd=frigate_path, check=True)
                self.progress.emit(f"✅ Repository updated successfully! (branch: {current_branch})")
            else:
                self.progress.emit("⚠️ Repository in detached HEAD state, fetched latest changes")
                
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update repository: {str(e)}")
        
        self._setup_config_directory(frigate_path)
    
    def _setup_config_directory(self, frigate_path):
        """Ensure config directory exists and create version.py"""
        config_dir = os.path.join(frigate_path, 'config')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            self.progress.emit("📁 Created config directory")
        
        # Create version.py file in frigate/frigate/version.py
        version_dir = os.path.join(frigate_path, 'frigate')
        version_file_path = os.path.join(version_dir, 'version.py')
        
        # Ensure frigate subdirectory exists
        if not os.path.exists(version_dir):
            os.makedirs(version_dir, exist_ok=True)
            self.progress.emit("📁 Created frigate subdirectory")
        
        try:
            # Create version.py with the specific version
            version_content = 'VERSION = "0.16.0-2458f667"\n'
            
            with open(version_file_path, 'w') as f:
                f.write(version_content)
            
            self.progress.emit("📝 Created version.py with version: 0.16.0-2458f667")
            
        except Exception as e:
            self.progress.emit(f"⚠️ Could not create version.py: {str(e)}")

    def _create_default_config(self, frigate_path):
        """Create default config.yaml file with template content"""
        config_dir = os.path.join(frigate_path, 'config')
        config_file_path = os.path.join(config_dir, 'config.yaml')
        
        # Check if config.yaml already exists
        if os.path.exists(config_file_path):
            self.progress.emit("ℹ️ Config file already exists, skipping creation")
            return
        
        # Default configuration content (same as in load_config_preview)
        default_config = """# Frigate Configuration
# This is a basic template. Customize it for your cameras and setup.

mqtt:
enabled: False

detectors:
  memx0:
    type: memryx
    device: PCIe:0

model:
model_type: yolo-generic
width: 320
height: 320
input_tensor: nchw
input_dtype: float
labelmap_path: /labelmap/coco-80.txt

# cameras:
# Add your cameras here
# example_camera:
#   ffmpeg:
#     inputs:
#       - path: rtsp://username:password@camera_ip:554/stream
#         roles:
#           - detect
#   detect:
#     width: 1280
#     height: 720

cameras:
cam1:
    ffmpeg:
    inputs:
        - path: 
            rtsp://username:password@camera_ip:554/stream
        roles:
            - detect
    detect:
    width: 1920
    height: 1080
    fps: 20
    enabled: true

    objects:
    track:
        - person
        - car
        - bottle
        - cup

    snapshots:
    enabled: false
    bounding_box: true
    retain:
        default: 0  # Keep snapshots for 'n' days
    record:
    enabled: false
    alerts:
        retain:
        days: 0
    detections:
        retain:
        days: 0

version: 0.17-0

# For more configuration options, visit:
# https://docs.frigate.video/configuration/
"""
        
        try:
            # Create the config file
            with open(config_file_path, 'w', encoding='utf-8') as f:
                f.write(default_config)
            
            self.progress.emit("📝 Created default config.yaml file")
            self.progress.emit(f"   📁 Location: {config_file_path}")
            
            # Signal to main thread to update config_file_mtime to prevent popup
            self.progress.emit("UPDATE_CONFIG_MTIME")
            
        except Exception as e:
            self.progress.emit(f"⚠️ Could not create default config.yaml: {str(e)}")

class DockerWorker(QThread):
    """Background worker for Docker operations"""
    progress = Signal(str)
    finished = Signal(bool)
    
    def __init__(self, script_dir, action='start'):
        super().__init__()
        self.script_dir = script_dir
        self.action = action
        self._terminated = False  # Track termination state
    
    def terminate(self):
        """Override terminate to set our flag"""
        self._terminated = True
        super().terminate()
    
    def run(self):
        try:
            if self._terminated:
                return
                
            if self.action == 'start':
                self._start_frigate()
            elif self.action == 'stop':
                self._stop_frigate()
            elif self.action == 'restart':
                self._restart_frigate()
            elif self.action == 'rebuild':
                self._rebuild_frigate()
            elif self.action == 'remove':
                self._remove_frigate()
                
            if not self._terminated:
                self.finished.emit(True)
        except Exception as e:
            if not self._terminated:
                self.progress.emit(f"❌ Error: {str(e)}")
                self.finished.emit(False)
    
    def _run_docker_command(self, cmd, description, cwd=None, capture_output=True):
        """Run a docker command and emit its output line by line"""
        self.progress.emit(f"{description}")
        
        try:
            if capture_output:
                # For commands that produce lots of output (like build)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=cwd,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Read output line by line and emit it
                for line in process.stdout:
                    line = line.strip()
                    if line:  # Only emit non-empty lines
                        self.progress.emit(line)
                
                # Wait for process to complete
                process.wait()
                
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
                    
            else:
                # For simple commands that don't produce much output
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=True)
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            self.progress.emit(line.strip())
                if result.stderr.strip():
                    for line in result.stderr.strip().split('\n'):
                        if line.strip():
                            self.progress.emit(f"⚠️ {line.strip()}")
                            
        except subprocess.CalledProcessError as e:
            self.progress.emit(f"❌ Command failed: {' '.join(cmd)}")
            if e.stdout:
                self.progress.emit(f"Output: {e.stdout}")
            if e.stderr:
                self.progress.emit(f"Error: {e.stderr}")
            raise
    
    def _check_container_exists(self):
        """Check if Frigate container exists"""
        try:
            result = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=frigate', '--format', '{{.Names}}'], 
                                  capture_output=True, text=True)
            return 'frigate' in result.stdout
        except:
            return False
    
    def _check_container_running(self):
        """Check if Frigate container is running"""
        try:
            result = subprocess.run(['docker', 'ps', '--filter', 'name=frigate', '--format', '{{.Names}}'], 
                                  capture_output=True, text=True)
            return 'frigate' in result.stdout
        except:
            return False
    
    def _start_frigate(self):
        """Start Frigate container (create if doesn't exist, just start if stopped)"""
        if self._check_container_exists():
            if self._check_container_running():
                self.progress.emit("ℹ️ Frigate container is already running")
                return
            else:
                self.progress.emit("▶️ Starting existing Frigate container...")
                self._run_docker_command(['docker', 'start', 'frigate'], "Starting container:", capture_output=False)
                self.progress.emit("✅ Frigate started successfully!")
                return
        
        # Container doesn't exist, create it automatically
        self.progress.emit("🏗️ Frigate container doesn't exist, creating new one...")
        self.progress.emit("💡 This will build and start a fresh Frigate container")
        self._rebuild_frigate()
    
    def _stop_frigate(self):
        """Stop Frigate container (but keep it for later restart)"""
        if not self._check_container_exists():
            self.progress.emit("ℹ️ Frigate container doesn't exist - nothing to stop")
            return
            
        if not self._check_container_running():
            self.progress.emit("ℹ️ Frigate container is already stopped")
            return
            
        self.progress.emit("⏹️ Stopping Frigate container...")
        self._run_docker_command(['docker', 'stop', 'frigate'], "Stopping container:", capture_output=False)
        self.progress.emit("✅ Frigate stopped successfully!")
    
    def _restart_frigate(self):
        """Quick restart of existing container"""
        if not self._check_container_exists():
            self.progress.emit("❌ Cannot restart: Frigate container doesn't exist")
            self.progress.emit("💡 Use 'Start' to create and start a new container")
            self.progress.emit("💡 Or use 'Rebuild' for a complete fresh build")
            # Raise an exception so the operation is marked as failed
            raise Exception("Container doesn't exist - cannot restart")
            
        self.progress.emit("🔄 Restarting Frigate container...")
        
        if self._check_container_running():
            self._run_docker_command(['docker', 'restart', 'frigate'], "Restarting container:", capture_output=False)
        else:
            self._run_docker_command(['docker', 'start', 'frigate'], "Starting container:", capture_output=False)
            
        self.progress.emit("✅ Frigate restarted successfully!")
    
    def _remove_frigate(self):
        """Stop and remove Frigate container completely"""
        if not self._check_container_exists():
            self.progress.emit("ℹ️ Frigate container doesn't exist")
            return
            
        self.progress.emit("🗑️ Stopping and removing Frigate container...")
        
        # Stop if running
        if self._check_container_running():
            self._run_docker_command(['docker', 'stop', 'frigate'], "Stopping container:", capture_output=False)
        
        # Remove container
        self._run_docker_command(['docker', 'rm', 'frigate'], "Removing container:", capture_output=False)
        self.progress.emit("✅ Frigate container removed successfully!")
    
    def _rebuild_frigate(self):
        """Complete rebuild: stop, remove, build fresh image, and start"""
        self.progress.emit("🔨 Starting complete rebuild of Frigate...")
        
        # Stop and remove existing container if it exists
        if self._check_container_exists():
            self.progress.emit("🛑 Stopping and removing existing container...")
            
            if self._check_container_running():
                try:
                    self._run_docker_command(['docker', 'stop', 'frigate'], "Stopping container:", capture_output=False)
                except subprocess.CalledProcessError:
                    self.progress.emit("(Container was already stopped)")
            
            try:
                self._run_docker_command(['docker', 'rm', 'frigate'], "Removing container:", capture_output=False)
            except subprocess.CalledProcessError:
                self.progress.emit("(Container was already removed)")
        
        # Build fresh image
        self.progress.emit("🔨 Building fresh Frigate Docker image...")
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if not os.path.exists(frigate_path):
            raise Exception("Frigate repository not found. Please use the Setup tab to clone it first.")
        
        self._run_docker_command([
            'docker', 'build', '-t', 'frigate', 
            '-f', 'docker/main/Dockerfile', '.'
        ], "Building Docker image:", cwd=frigate_path, capture_output=True)
        
        self.progress.emit("")  # Empty line for separation
        self.progress.emit("🚀 Creating and starting new Frigate container...")
        
        # Create and start new container
        self._run_docker_command([
            'docker', 'run', '-d',
            '--name', 'frigate',
            '--restart=unless-stopped',
            '--mount', 'type=tmpfs,target=/tmp/cache,tmpfs-size=1000000000',
            '--shm-size=256m',
            '-v', f"{frigate_path}/config:/config",
            '-v', '/run/mxa_manager:/run/mxa_manager',
            '-e', 'FRIGATE_RTSP_PASSWORD=password',
            '--privileged=true',
            '-p', '8971:8971',
            '-p', '8554:8554', 
            '-p', '5000:5000',
            '-p', '8555:8555/tcp',
            '-p', '8555:8555/udp',
            '--device', '/dev/memx0',
            'frigate'
        ], "Creating container:", capture_output=False)
        
        self.progress.emit("")  # Empty line for separation
        self.progress.emit("✅ Frigate rebuild completed successfully!")

class DockerInstallWorker(QThread):
    """Background worker for Docker installation"""
    progress = Signal(str)
    finished = Signal(bool)
    
    def __init__(self, script_dir, sudo_password=None):
        super().__init__()
        self.script_dir = script_dir
        self.sudo_password = sudo_password
    
    def run(self):
        try:
            self.progress.emit("🐳 Starting Docker installation process...")
            
            # Helper function to run sudo commands with password
            def run_sudo_command(cmd, input_text=None):
                if self.sudo_password:
                    # Use sudo -S to read password from stdin
                    sudo_cmd = ['sudo', '-S'] + cmd[1:]  # Remove 'sudo' from original cmd
                    if input_text:
                        # For commands that need input, we can't mix password and content
                        # This should only be used for commands that don't need input
                        raise ValueError("Use write_sudo_file for commands that need file input")
                    return subprocess.run(sudo_cmd, input=f"{self.sudo_password}\n", text=True, check=True, capture_output=True)
                else:
                    # Fallback to normal sudo (will work if terminal=true)
                    return subprocess.run(cmd, input=input_text, text=True, check=True, capture_output=True)
            
            # Helper function to write files with sudo
            def write_sudo_file(file_path, content):
                if self.sudo_password:
                    # Write to temp file first, then move with sudo
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                        temp_file.write(content)
                        temp_file_path = temp_file.name
                    
                    try:
                        # Move temp file to target location with sudo
                        sudo_cmd = ['sudo', '-S', 'mv', temp_file_path, file_path]
                        subprocess.run(sudo_cmd, input=f"{self.sudo_password}\n", text=True, check=True, capture_output=True)
                    finally:
                        # Clean up temp file if it still exists
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                else:
                    # Fallback to normal write (won't work for protected paths)
                    with open(file_path, 'w') as f:
                        f.write(content)
            
            # Step 0: Clean up any existing Docker repository files (in case of previous failed attempts)
            self.progress.emit("🧹 Cleaning up any existing Docker repository files...")
            try:
                run_sudo_command(['sudo', 'rm', '-f', '/etc/apt/sources.list.d/docker.list'])
                run_sudo_command(['sudo', 'rm', '-f', '/etc/apt/keyrings/docker.asc'])
            except subprocess.CalledProcessError:
                pass  # Files may not exist, continue
            
            # Step 1: Update package repositories
            self.progress.emit("📦 Updating package repositories...")
            run_sudo_command(['sudo', 'apt-get', 'update'])
            
            # Step 2: Install prerequisites
            self.progress.emit("🔧 Installing prerequisites...")
            run_sudo_command([
                'sudo', 'apt-get', 'install', '-y',
                'ca-certificates', 'curl'
            ])
            
            # Step 3: Create keyrings directory
            self.progress.emit("🔑 Setting up Docker GPG keyring...")
            run_sudo_command([
                'sudo', 'install', '-m', '0755', '-d', '/etc/apt/keyrings'
            ])
            
            # Step 4: Download Docker GPG key
            run_sudo_command([
                'sudo', 'curl', '-fsSL', 
                'https://download.docker.com/linux/ubuntu/gpg',
                '-o', '/etc/apt/keyrings/docker.asc'
            ])
            
            # Step 5: Set permissions on GPG key
            run_sudo_command([
                'sudo', 'chmod', 'a+r', '/etc/apt/keyrings/docker.asc'
            ])
            
            # Step 6: Add Docker repository
            self.progress.emit("📋 Adding Docker repository...")
            
            # Get architecture and version codename
            arch_result = subprocess.run(['dpkg', '--print-architecture'], 
                                       capture_output=True, text=True, check=True)
            architecture = arch_result.stdout.strip()
            
            # Get Ubuntu version codename
            with open('/etc/os-release', 'r') as f:
                os_release = f.read()
            
            version_codename = None
            for line in os_release.split('\n'):
                if line.startswith('VERSION_CODENAME='):
                    version_codename = line.split('=')[1].strip('"')
                    break
            
            if not version_codename:
                raise Exception("Could not determine Ubuntu version codename")
            
            # Create repository entry
            repo_entry = (
                f"deb [arch={architecture} signed-by=/etc/apt/keyrings/docker.asc] "
                f"https://download.docker.com/linux/ubuntu {version_codename} stable\n"
            )
            
            # Add repository to sources list
            self.progress.emit("📋 Adding Docker repository...")
            write_sudo_file('/etc/apt/sources.list.d/docker.list', repo_entry)
            
            # Verify the repository was written correctly
            try:
                verify_result = subprocess.run(['cat', '/etc/apt/sources.list.d/docker.list'], 
                                             capture_output=True, text=True, check=True)
                self.progress.emit(f"✅ Repository added: {verify_result.stdout.strip()}")
            except subprocess.CalledProcessError:
                self.progress.emit("⚠️  Could not verify repository file, continuing...")
            
            # Step 7: Update package repositories again
            self.progress.emit("🔄 Updating package repositories with Docker repo...")
            run_sudo_command(['sudo', 'apt-get', 'update'])
            
            # Step 8: Install Docker
            self.progress.emit("🐳 Installing Docker CE and components...")
            run_sudo_command([
                'sudo', 'apt-get', 'install', '-y',
                'docker-ce', 'docker-ce-cli', 'containerd.io',
                'docker-buildx-plugin', 'docker-compose-plugin'
            ])
            
            # Step 9: Start and enable Docker service
            self.progress.emit("🚀 Starting Docker service...")
            run_sudo_command(['sudo', 'systemctl', 'start', 'docker'])
            run_sudo_command(['sudo', 'systemctl', 'enable', 'docker'])
            
            # Step 10: Create docker group and add user
            self.progress.emit("👥 Configuring user permissions...")
            
            # Create docker group (may already exist)
            try:
                run_sudo_command(['sudo', 'groupadd', 'docker'])
            except subprocess.CalledProcessError:
                # Group may already exist, continue
                pass
            
            # Add current user to docker group
            import getpass
            current_user = getpass.getuser()
            run_sudo_command(['sudo', 'usermod', '-aG', 'docker', current_user])
            
            # Step 11: Verify Docker installation
            self.progress.emit("🔍 Verifying Docker installation...")
            
            # Check if docker binary exists and is executable
            try:
                docker_version_result = subprocess.run(['docker', '--version'], 
                                                     capture_output=True, text=True, check=True)
                self.progress.emit(f"✅ Docker binary working: {docker_version_result.stdout.strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                self.progress.emit("❌ Docker binary not found or not working!")
                self.progress.emit("🔄 Attempting to reinstall Docker CLI...")
                try:
                    run_sudo_command(['sudo', 'apt-get', 'reinstall', '-y', 'docker-ce-cli'])
                    # Try again
                    docker_version_result = subprocess.run(['docker', '--version'], 
                                                         capture_output=True, text=True, check=True)
                    self.progress.emit(f"✅ Docker binary working after reinstall: {docker_version_result.stdout.strip()}")
                except Exception as reinstall_error:
                    self.progress.emit(f"❌ Failed to fix Docker CLI: {str(reinstall_error)}")
                    self.finished.emit(False)
                    return
            
            # Check if Docker service is running
            try:
                service_result = subprocess.run(['systemctl', 'is-active', 'docker'], 
                                              capture_output=True, text=True, check=True)
                if service_result.stdout.strip() == 'active':
                    self.progress.emit("✅ Docker service is running")
                else:
                    self.progress.emit("⚠️  Docker service not active, starting it...")
                    run_sudo_command(['sudo', 'systemctl', 'start', 'docker'])
            except subprocess.CalledProcessError:
                self.progress.emit("⚠️  Could not check Docker service status")
            
            # Test Docker with a simple command (as root since user may not be in group yet)
            try:
                test_result = run_sudo_command(['sudo', 'docker', 'run', '--rm', 'hello-world'])
                self.progress.emit("✅ Docker test successful - container can run!")
            except subprocess.CalledProcessError as e:
                self.progress.emit("⚠️  Docker test failed - may need logout/login for group permissions")
                self.progress.emit(f"   Error: {e.stderr if e.stderr else str(e)}")
            
            self.progress.emit("✅ Docker installation completed successfully!")
            self.progress.emit("ℹ️  Please log out and log back in for group permissions to take effect.")
            
            self.finished.emit(True)
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Command failed: {e.cmd}"
            if e.stderr:
                error_msg += f"\n   Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            self.progress.emit(error_msg)
            self.finished.emit(False)
            
        except Exception as e:
            self.progress.emit(f"❌ Installation error: {str(e)}")
            self.finished.emit(False)

class MemryXInstallWorker(QThread):
    """Background worker for MemryX driver installation"""
    progress = Signal(str)
    finished = Signal(bool)
    
    def __init__(self, script_dir, sudo_password=None):
        super().__init__()
        self.script_dir = script_dir
        self.sudo_password = sudo_password
    
    def run(self):
        try:
            # Helper function to run sudo commands with password
            def run_sudo_command(cmd, input_text=None, **kwargs):
                if self.sudo_password:
                    # Use sudo -S to read password from stdin
                    sudo_cmd = ['sudo', '-S'] + cmd[1:]  # Remove 'sudo' from original cmd
                    if input_text:
                        # For commands that need input, we can't mix password and content
                        raise ValueError("Use write_sudo_file for commands that need file input")
                    return subprocess.run(sudo_cmd, input=f"{self.sudo_password}\n", text=True, check=True, capture_output=True, **kwargs)
                else:
                    # Fallback to normal sudo (will work if terminal=true)
                    return subprocess.run(cmd, input=input_text, text=True, check=True, capture_output=True, **kwargs)
            
            # Helper function to write files with sudo
            def write_sudo_file(file_path, content):
                if self.sudo_password:
                    # Write to temp file first, then move with sudo
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                        temp_file.write(content)
                        temp_file_path = temp_file.name
                    
                    try:
                        # Move temp file to target location with sudo
                        sudo_cmd = ['sudo', '-S', 'mv', temp_file_path, file_path]
                        subprocess.run(sudo_cmd, input=f"{self.sudo_password}\n", text=True, check=True, capture_output=True)
                    finally:
                        # Clean up temp file if it still exists
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                else:
                    # Fallback to normal write (won't work for protected paths)
                    with open(file_path, 'w') as f:
                        f.write(content)
            
            self.progress.emit("🚀 Starting MemryX driver and runtime installation...")
            
            # Detect architecture
            arch_result = subprocess.run(['uname', '-m'], capture_output=True, text=True, check=True)
            architecture = arch_result.stdout.strip()
            self.progress.emit(f"🏗️ Detected architecture: {architecture}")
            
            # Step 1: Purge existing packages and repo
            self.progress.emit("🗑️ Removing old MemryX installations...")
            
            # Remove any holds on MemryX packages (if they exist)
            try:
                run_sudo_command(['sudo', 'apt-mark', 'unhold', 'memx-*', 'mxa-manager'])
            except subprocess.CalledProcessError:
                pass  # May not exist
            
            try:
                run_sudo_command(['sudo', 'apt', 'purge', '-y', 'memx-*', 'mxa-manager'])
            except subprocess.CalledProcessError:
                pass  # May not exist
                
            # Remove existing MemryX repository and keys (both old and new formats)
            try:
                run_sudo_command(['sudo', 'rm', '-f', 
                                '/etc/apt/sources.list.d/memryx.list',
                                '/etc/apt/trusted.gpg.d/memryx.asc',
                                '/etc/apt/trusted.gpg.d/memryx.gpg'])
            except subprocess.CalledProcessError:
                pass  # May not exist
            
            # Also try to remove from apt-key (legacy method)
            try:
                # List keys and remove any MemryX keys
                list_result = subprocess.run(['apt-key', 'list'], capture_output=True, text=True)
                if 'memryx' in list_result.stdout.lower() or 'D3F12469DCF7E731' in list_result.stdout:
                    run_sudo_command(['sudo', 'apt-key', 'del', 'D3F12469DCF7E731'])
            except subprocess.CalledProcessError:
                pass  # Key may not exist
            
            # Step 2: Install kernel headers
            kernel_version_result = subprocess.run(['uname', '-r'], capture_output=True, text=True, check=True)
            kernel_version = kernel_version_result.stdout.strip()
            self.progress.emit(f"🔧 Installing kernel headers for: {kernel_version}")
            
            run_sudo_command(['sudo', 'apt', 'update'])
            run_sudo_command(['sudo', 'apt', 'install', '-y', 'dkms', f'linux-headers-{kernel_version}'])
            
            # Step 3: Add MemryX key and repo
            self.progress.emit("🔑 Adding MemryX GPG key and repository...")
            
            # Method 1: Try using wget and gpg --dearmor (modern approach)
            try:
                # Download GPG key and convert to proper format
                self.progress.emit("📥 Downloading MemryX GPG key...")
                subprocess.run([
                    'wget', '-qO-', 'https://developer.memryx.com/deb/memryx.asc'
                ], stdout=open('/tmp/memryx_key.asc', 'w'), check=True)
                
                # Convert ASCII armored key to binary format that apt can use
                subprocess.run([
                    'gpg', '--dearmor', '--output', '/tmp/memryx.gpg', '/tmp/memryx_key.asc'
                ], check=True)
                
                # Copy the binary GPG key to the correct location with proper permissions
                run_sudo_command(['sudo', 'cp', '/tmp/memryx.gpg', '/etc/apt/trusted.gpg.d/memryx.gpg'])
                run_sudo_command(['sudo', 'chmod', '644', '/etc/apt/trusted.gpg.d/memryx.gpg'])
                run_sudo_command(['sudo', 'chown', 'root:root', '/etc/apt/trusted.gpg.d/memryx.gpg'])
                
                # Clean up temporary files
                subprocess.run(['rm', '-f', '/tmp/memryx_key.asc', '/tmp/memryx.gpg'], check=False)
                
            except subprocess.CalledProcessError as e:
                self.progress.emit(f"⚠️ GPG method 1 failed: {e}")
                self.progress.emit("🔄 Trying alternative GPG key installation method...")
                
                # Method 2: Direct curl and apt-key approach (fallback)
                try:
                    # Use curl to download and pipe directly to apt-key
                    curl_cmd = ['curl', '-fsSL', 'https://developer.memryx.com/deb/memryx.asc']
                    apt_key_cmd = ['sudo', '-S', 'apt-key', 'add', '-']
                    
                    # Run curl and pipe to apt-key
                    curl_proc = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE)
                    apt_key_proc = subprocess.Popen(apt_key_cmd, stdin=curl_proc.stdout, 
                                                   input=f"{self.sudo_password}\n" if self.sudo_password else None,
                                                   text=True, capture_output=True)
                    curl_proc.stdout.close()
                    curl_proc.wait()
                    apt_key_proc.wait()
                    
                    if apt_key_proc.returncode != 0:
                        raise subprocess.CalledProcessError(apt_key_proc.returncode, 'apt-key')
                        
                except subprocess.CalledProcessError as e2:
                    self.progress.emit(f"❌ Both GPG methods failed. Last error: {e2}")
                    raise Exception("Failed to install MemryX GPG key")
            
            # Add repository
            self.progress.emit("📝 Adding MemryX repository...")
            write_sudo_file('/etc/apt/sources.list.d/memryx.list', 
                          'deb https://developer.memryx.com/deb stable main\n')
            
            # Step 4: Update and install memx-drivers
            self.progress.emit("📦 Installing memx-drivers...")
            
            # Update package lists with detailed error handling
            try:
                result = run_sudo_command(['sudo', 'apt', 'update'])
                self.progress.emit("✅ Package lists updated successfully")
            except subprocess.CalledProcessError as e:
                self.progress.emit(f"⚠️ Package update had warnings (this is often normal): {e}")
                # Continue anyway - warnings are often non-fatal
                
            # Try to install memx-drivers
            try:
                run_sudo_command(['sudo', 'apt', 'install', '-y', 'memx-drivers'])
                self.progress.emit("✅ memx-drivers installed successfully")
            except subprocess.CalledProcessError as e:
                self.progress.emit(f"❌ Failed to install memx-drivers: {e}")
                # Try to get more specific error information
                try:
                    search_result = subprocess.run(['apt', 'search', 'memx-drivers'], 
                                                 capture_output=True, text=True)
                    if 'memx-drivers' in search_result.stdout:
                        self.progress.emit("📦 Package memx-drivers is available in repository")
                    else:
                        self.progress.emit("❌ Package memx-drivers not found in repository")
                        self.progress.emit("🔍 Checking repository configuration...")
                        
                        # Check if repository was added correctly
                        try:
                            with open('/etc/apt/sources.list.d/memryx.list', 'r') as f:
                                repo_content = f.read().strip()
                            self.progress.emit(f"📝 Repository content: {repo_content}")
                        except:
                            self.progress.emit("❌ Repository file not found or not readable")
                            
                except Exception as search_error:
                    self.progress.emit(f"❌ Could not search for package: {search_error}")
                    
                raise e  # Re-raise the original error
            
            # Step 5: ARM-specific board setup
            if architecture in ['aarch64', 'arm64']:
                self.progress.emit("🔧 Running ARM board setup...")
                run_sudo_command(['sudo', 'mx_arm_setup'])
            
            self.progress.emit("⚠️ SYSTEM RESTART REQUIRED AFTER DRIVER INSTALLATION")
            
            # Step 6: Install other runtime packages
            packages = ['memx-accl', 'mxa-manager']
            for pkg in packages:
                self.progress.emit(f"📦 Installing {pkg}...")
                run_sudo_command(['sudo', 'apt', 'install', '-y', pkg])
            
            self.progress.emit("✅ MemryX installation completed successfully!")
            self.progress.emit("🔄 Please restart your computer to complete the installation.")
            
            self.finished.emit(True)
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Command failed: {e.cmd}"
            if e.stderr:
                error_msg += f"\n   Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            self.progress.emit(error_msg)
            self.finished.emit(False)
            
        except Exception as e:
            self.progress.emit(f"❌ Installation error: {str(e)}")
            self.finished.emit(False)

class StatusCheckWorker(QThread):
    """Background worker for status checking to prevent UI blocking"""
    status_updated = Signal(dict)  # Emit status results
    finished = Signal()
    
    def __init__(self, script_dir):
        super().__init__()
        self.script_dir = script_dir
        
    def run(self):
        """Run status checks in background thread"""
        try:
            status_data = {}
            
            # Check Frigate container status
            status_data['frigate'] = self._check_frigate_status()
            
            # Check Docker service status  
            status_data['docker'] = self._check_docker_status()
            
            # Check configuration status
            status_data['config'] = self._check_config_status()
            
            # Check MemryX devices
            status_data['memryx'] = self._check_memryx_status()
            
            # Emit results
            self.status_updated.emit(status_data)
            
        except Exception as e:
            # Emit error status
            error_status = {
                'frigate': {'text': '❓ Check Failed', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'},
                'docker': {'text': '❓ Check Failed', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'},
                'config': {'text': '❓ Check Failed', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'},
                'memryx': {'text': '❓ Check Failed', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'}
            }
            self.status_updated.emit(error_status)
        finally:
            self.finished.emit()
    
    def _check_frigate_status(self):
        """Check Frigate container status"""
        try:
            # Check if container exists (running or stopped)
            all_containers = subprocess.run(['docker', 'ps', '-a', '-q', '-f', 'name=frigate'], 
                                          capture_output=True, text=True, timeout=10)
            
            if all_containers.stdout.strip():
                # Container exists, check if it's running
                running_containers = subprocess.run(['docker', 'ps', '-q', '-f', 'name=frigate'], 
                                                  capture_output=True, text=True, timeout=10)
                
                if running_containers.stdout.strip():
                    return {'text': '✅ Running', 'style': 'background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;'}
                else:
                    return {'text': '⏸️ Stopped', 'style': 'background: #fff3cd; color: #856404; padding: 6px; border-radius: 4px;'}
            else:
                return {'text': '❌ Not Created', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
                
        except subprocess.TimeoutExpired:
            return {'text': '⏱️ Docker Timeout', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'}
        except FileNotFoundError:
            return {'text': '❌ Docker Not Installed', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
        except Exception:
            return {'text': '❓ Unknown Error', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'}
    
    def _check_docker_status(self):
        """Check Docker service status"""
        try:
            result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {'text': '✅ Running', 'style': 'background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;'}
            else:
                return {'text': '❌ Not Available', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
        except subprocess.TimeoutExpired:
            return {'text': '⏱️ Docker Timeout', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'}
        except FileNotFoundError:
            return {'text': '❌ Not Installed', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
        except Exception:
            return {'text': '❌ Not Installed', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
    
    def _check_config_status(self):
        """Check configuration file status"""
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        if os.path.exists(config_path):
            return {'text': '✅ Found', 'style': 'background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;'}
        else:
            return {'text': '❌ Missing', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
    
    def _check_memryx_status(self):
        """Check MemryX devices status"""
        try:
            import glob
            devices = [d for d in glob.glob("/dev/memx*") if "_feature" not in d]
            if devices:
                device_count = len(devices)
                return {'text': f'✅ {device_count} devices found', 'style': 'background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;'}
            else:
                return {'text': '❌ No Devices', 'style': 'background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;'}
        except Exception:
            return {'text': '❓ Check Failed', 'style': 'background: #fdf6e3; color: #8b7355; padding: 6px; border-radius: 4px;'}

class CameraSetupWizard(QDialog):
    """User-friendly camera setup wizard for PreConfigured Box"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cameras = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("🎥 Camera Setup Wizard")
        self.setModal(True)
        self.resize(800, 600)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4299e1, stop:1 #3182ce);
                border-radius: 12px;
                margin-bottom: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(25, 20, 25, 20)
        
        title = QLabel("🎥 Set Up Your Cameras")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; margin-bottom: 8px;")
        
        subtitle = QLabel("Add your cameras to start monitoring with Frigate")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: white; opacity: 0.9;")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_frame)
        
        # Camera list area
        cameras_frame = QFrame()
        cameras_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        cameras_layout = QVBoxLayout(cameras_frame)
        cameras_layout.setContentsMargins(20, 20, 20, 20)
        
        # Cameras list title
        cameras_title = QLabel("📹 Your Cameras")
        cameras_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        cameras_title.setStyleSheet("color: #2d3748; margin-bottom: 15px;")
        cameras_layout.addWidget(cameras_title)
        
        # Scroll area for cameras with enhanced styling
        self.cameras_scroll = QScrollArea()
        self.cameras_scroll.setWidgetResizable(True)
        self.cameras_scroll.setMinimumHeight(200)
        self.cameras_scroll.setMaximumHeight(400)  # Prevent excessive growth
        self.cameras_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                background: #f8f9fa;
            }}
            {self.scroll_bar_style}
        """)
        
        self.cameras_widget = QWidget()
        self.cameras_layout = QVBoxLayout(self.cameras_widget)
        self.cameras_layout.setSpacing(10)
        self.cameras_scroll.setWidget(self.cameras_widget)
        
        cameras_layout.addWidget(self.cameras_scroll)
        
        # Add camera button
        add_camera_btn = QPushButton("➕ Add Camera")
        add_camera_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        add_camera_btn.setMinimumHeight(50)
        add_camera_btn.clicked.connect(self.add_camera)
        add_camera_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #48bb78, stop:1 #38a169);
                color: white;
                border: none;
                border-radius: 8px;
                margin: 10px 0;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #68d391, stop:1 #48bb78);
            }
        """)
        cameras_layout.addWidget(add_camera_btn)
        
        layout.addWidget(cameras_frame)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(45)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #4a5568;
                border: 1px solid #cbd5e0;
                border-radius: 8px;
                padding: 12px 30px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #cbd5e0;
            }
        """)
        
        self.apply_btn = QPushButton("Apply Configuration")
        self.apply_btn.setMinimumHeight(45)
        self.apply_btn.clicked.connect(self.accept)
        self.apply_btn.setEnabled(False)  # Disabled until cameras are added
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4299e1, stop:1 #3182ce);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #63b3ed, stop:1 #4299e1);
            }
            QPushButton:disabled {
                background: #a0aec0;
                color: #718096;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
        
        # Add first camera by default
        self.add_camera()
    
    def add_camera(self):
        """Add a new camera configuration widget"""
        camera_widget = CameraConfigWidget(len(self.cameras) + 1, self)
        camera_widget.removed.connect(self.remove_camera)
        camera_widget.changed.connect(self.update_apply_button)
        
        self.cameras.append(camera_widget)
        self.cameras_layout.addWidget(camera_widget)
        
        self.update_apply_button()
    
    def remove_camera(self, camera_widget):
        """Remove a camera configuration widget"""
        if camera_widget in self.cameras:
            self.cameras.remove(camera_widget)
            camera_widget.setParent(None)
            camera_widget.deleteLater()
            
        # Update camera numbers
        for i, camera in enumerate(self.cameras):
            camera.update_camera_number(i + 1)
        
        self.update_apply_button()
    
    def update_apply_button(self):
        """Enable/disable apply button based on camera configurations"""
        valid_cameras = [camera for camera in self.cameras if camera.is_valid()]
        self.apply_btn.setEnabled(len(valid_cameras) > 0)
        
        if len(valid_cameras) > 0:
            self.apply_btn.setText(f"Apply Configuration ({len(valid_cameras)} camera{'s' if len(valid_cameras) != 1 else ''})")
        else:
            self.apply_btn.setText("Apply Configuration")
    
    def get_camera_configs(self):
        """Get all valid camera configurations"""
        configs = []
        for camera_widget in self.cameras:
            if camera_widget.is_valid():
                configs.append(camera_widget.get_config())
        return configs

class CameraSetupWelcomeDialog(QDialog):
    """First-run welcome dialog for camera setup"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_setup_requested = False
        self.setup_complete_requested = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("🎥 Welcome to MemryX + Frigate")
        self.setModal(True)
        self.resize(750, 550)  # Smaller size as requested
        
        # Strengthen window flags to ensure close button is removed - user must make a choice
        self.setWindowFlags(
            Qt.Dialog | 
            Qt.CustomizeWindowHint | 
            Qt.WindowTitleHint |
            Qt.WindowSystemMenuHint
        )
        # Explicitly disable close button and context menu
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with gradient background
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4299e1, stop:0.5 #3182ce, stop:1 #2c6b7d);
                border: none;
                border-bottom: 3px solid rgba(0,0,0,0.1);
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(50, 40, 50, 40)
        header_layout.setSpacing(15)
        
        # Welcome title with smaller size
        title = QLabel("🎥 Welcome to Your MemryX + Frigate Box!")
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: white; 
            margin-bottom: 15px;
            font-weight: 800;
        """)
        
        header_layout.addWidget(title)
        layout.addWidget(header_frame)
        
        # Content area
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: none;
            }
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(60, 50, 60, 50)
        content_layout.setSpacing(30)
        
        # Main message with smaller text
        message = QLabel()
        message.setWordWrap(True)
        message.setFont(QFont("Segoe UI", 14))
        message.setText(
            "🎯 To get started, first you need to setup your cameras.\n\n"
            "📋 Use this guide to setup first."
        )
        message.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8faff, stop:1 #eef4ff);
                color: #1a365d;
                padding: 30px;
                border-radius: 12px;
                border: 2px solid #bee3f8;
                line-height: 1.6;
            }
        """)
        message.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(message)
        
        # Button area
        button_frame = QFrame()
        button_layout = QVBoxLayout(button_frame)
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(40, 20, 40, 20)  # Add horizontal margins
        
        # Start Setup button - simplified to ensure text shows
        self.start_setup_btn = QPushButton("🚀 Start Camera Setup")
        self.start_setup_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.start_setup_btn.setMinimumHeight(70)
        self.start_setup_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_setup_btn.clicked.connect(self.start_camera_setup)
        self.start_setup_btn.setStyleSheet("""
            QPushButton {
                background-color: #22c55e;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 15px 25px;
                margin: 10px 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #16a34a;
            }
            QPushButton:pressed {
                background-color: #15803d;
            }
        """)
        
        # Already Setup button - simplified to ensure text shows
        self.already_setup_btn = QPushButton("✅ Skip - Already Configured")
        self.already_setup_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.already_setup_btn.setMinimumHeight(50)
        self.already_setup_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.already_setup_btn.clicked.connect(self.mark_setup_complete)
        self.already_setup_btn.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 20px;
                margin: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:pressed {
                background-color: #334155;
            }
        """)
        
        button_layout.addWidget(self.start_setup_btn)
        button_layout.addWidget(self.already_setup_btn)
        content_layout.addWidget(button_frame)
        
        # Footer note with smaller text
        footer_note = QLabel(
            "💡 Don't worry - you can always access the camera setup guide later from the main screen."
        )
        footer_note.setFont(QFont("Segoe UI", 11))
        footer_note.setAlignment(Qt.AlignCenter)
        footer_note.setStyleSheet("""
            QLabel {
                color: #64748b;
                padding: 15px 20px;
                background: rgba(148, 163, 184, 0.1);
                border-radius: 8px;
                margin: 8px 15px;
                font-style: italic;
            }
        """)
        content_layout.addWidget(footer_note)
        
        layout.addWidget(content_frame)
    
    def start_camera_setup(self):
        """Handle start camera setup button click"""
        self.start_setup_requested = True
        self.accept()
    
    def mark_setup_complete(self):
        """Handle already setup complete button click"""
        self.setup_complete_requested = True
        self.accept()
    
    def keyPressEvent(self, event):
        """Override to prevent Escape key from closing the dialog"""
        # Ignore Escape key - user must choose an option
        if event.key() != Qt.Key_Escape:
            super().keyPressEvent(event)

class CameraConfigWidget(QFrame):
    """Widget for configuring a single camera"""
    
    removed = Signal(object)  # Signal emitted when camera is removed
    changed = Signal()        # Signal emitted when configuration changes
    
    def __init__(self, camera_number, parent=None):
        super().__init__(parent)
        self.camera_number = camera_number
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                margin: 5px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)
        
        # Header with camera number and remove button
        header_layout = QHBoxLayout()
        
        self.camera_title = QLabel(f"📷 Camera {self.camera_number}")
        self.camera_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.camera_title.setStyleSheet("color: #2d3748;")
        
        remove_btn = QPushButton("🗑️ Remove")
        remove_btn.setMaximumWidth(100)
        remove_btn.setMinimumHeight(30)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        remove_btn.setStyleSheet("""
            QPushButton {
                background: #fed7d7;
                color: #c53030;
                border: 1px solid #feb2b2;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #feb2b2;
            }
        """)
        
        header_layout.addWidget(self.camera_title)
        header_layout.addStretch()
        header_layout.addWidget(remove_btn)
        
        layout.addLayout(header_layout)
        
        # Form layout for camera details
        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        
        # Camera name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Front Door, Driveway")
        self.name_input.textChanged.connect(self.changed.emit)
        self.name_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("Camera Name:", self.name_input)
        
        # IP Address
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        self.ip_input.textChanged.connect(self.changed.emit)
        self.ip_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("IP Address:", self.ip_input)
        
        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin")
        self.username_input.textChanged.connect(self.changed.emit)
        self.username_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("Username:", self.username_input)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("password")
        self.password_input.textChanged.connect(self.changed.emit)
        self.password_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("Password:", self.password_input)
        
        # Port (optional)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("554 (default)")
        self.port_input.setText("554")
        self.port_input.textChanged.connect(self.changed.emit)
        self.port_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("RTSP Port:", self.port_input)
        
        # Stream path (optional)
        self.stream_input = QLineEdit()
        self.stream_input.setPlaceholderText("/stream1 (default)")
        self.stream_input.setText("/stream1")
        self.stream_input.textChanged.connect(self.changed.emit)
        self.stream_input.setStyleSheet(self.get_input_style())
        form_layout.addRow("Stream Path:", self.stream_input)
        
        layout.addLayout(form_layout)
        
        # Objects to track
        objects_layout = QVBoxLayout()
        objects_label = QLabel("Objects to Track:")
        objects_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        objects_label.setStyleSheet("color: #4a5568; margin-top: 8px;")
        objects_layout.addWidget(objects_label)
        
        # Common objects checkboxes
        objects_grid = QGridLayout()
        self.object_checkboxes = {}
        
        common_objects = [
            'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
            'cat', 'dog', 'bird', 'bottle', 'backpack', 'suitcase'
        ]
        
        for i, obj in enumerate(common_objects):
            checkbox = QCheckBox(obj.title())
            if obj == 'person':  # Default to person
                checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.changed.emit)
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    color: #4a5568;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
            """)
            self.object_checkboxes[obj] = checkbox
            objects_grid.addWidget(checkbox, i // 3, i % 3)
        
        objects_layout.addLayout(objects_grid)
        layout.addLayout(objects_layout)
    
    def get_input_style(self):
        """Get consistent input field styling"""
        return """
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-size: 12px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #4299e1;
                outline: none;
            }
            QLineEdit:placeholder {
                color: #a0aec0;
            }
        """
    
    def update_camera_number(self, number):
        """Update the camera number display"""
        self.camera_number = number
        self.camera_title.setText(f"📷 Camera {self.camera_number}")
    
    def is_valid(self):
        """Check if the camera configuration is valid"""
        return (
            self.name_input.text().strip() != "" and
            self.ip_input.text().strip() != "" and
            self.username_input.text().strip() != "" and
            self.password_input.text().strip() != ""
        )
    
    def get_config(self):
        """Get the camera configuration as a dictionary"""
        selected_objects = [
            obj for obj, checkbox in self.object_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        return {
            'name': self.name_input.text().strip(),
            'ip_address': self.ip_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text().strip(),
            'port': self.port_input.text().strip() or '554',
            'stream_path': self.stream_input.text().strip() or '/stream1',
            'objects': selected_objects if selected_objects else ['person']
        }

class FrigateLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_mtime = 0  # Track config file modification time
        self.suppress_config_change_popup = False  # Flag to suppress config change popup
        
        # Setup completion tracking
        self.setup_complete_file = os.path.join(self.script_dir, '.camera_setup_complete')
        self.is_first_run = not os.path.exists(self.setup_complete_file)

        # Initialize worker thread reference
        self.docker_worker = None
        
        # Initialize loading state
        self.is_initializing = True
        
        # Button state enhancement variables
        self.button_animation_timer = QTimer()
        self.button_animation_timer.timeout.connect(self.update_button_animation)
        self.button_animation_dots = 0
        self.button_base_text = ""
        self.button_operation_state = "idle"  # idle, building, starting, running, stopping
        
        # Store references to container layouts for responsive resizing
        self.responsive_containers = []
        
        # Common scroll bar styling for consistency across all text areas
        self.scroll_bar_style = """
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4a90a4;
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38758a;
            }
            QScrollBar::handle:vertical:pressed {
                background: #2c6b7d;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #4a90a4;
                border-radius: 6px;
                min-width: 20px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38758a;
            }
            QScrollBar::handle:horizontal:pressed {
                background: #2c6b7d;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                border: none;
                background: none;
            }
        """
        
        # Create timers before setup_ui() so they're available during tab creation
        # Status check timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_status)
        
        # Config file watcher timer
        self.config_watcher_timer = QTimer()
        self.config_watcher_timer.timeout.connect(self.check_config_file_changes)
        
        # Logs auto-refresh timer
        self.logs_timer = QTimer()
        self.logs_timer.timeout.connect(self.refresh_logs)
        
        # Setup UI (this will create tabs and potentially start timers)
        self.setup_ui()
        
        # Defer heavy operations until after UI is shown to improve startup time
        QTimer.singleShot(100, self._initialize_async_components)
    
    def mark_setup_complete(self):
        """Mark the initial setup as complete to prevent the welcome dialog from showing again"""
        try:
            with open(self.setup_complete_file, 'w') as f:
                f.write(f"Camera setup completed on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.is_first_run = False
        except Exception as e:
            print(f"Warning: Could not save setup completion status: {e}")
    
    def reset_setup_status(self):
        """Reset setup status to force the welcome dialog to appear again (for testing/reset)"""
        try:
            if os.path.exists(self.setup_complete_file):
                os.remove(self.setup_complete_file)
            self.is_first_run = True
        except Exception as e:
            print(f"Warning: Could not reset setup status: {e}")
    
    def show_first_run_welcome(self):
        """Show the first-run welcome dialog if this is a first run"""
        if self.is_first_run:
            # Use QTimer to show dialog after main window is fully loaded
            QTimer.singleShot(200, self._show_welcome_dialog)
    
    def _show_welcome_dialog(self):
        """Internal method to show the welcome dialog"""
        dialog = CameraSetupWelcomeDialog(self)
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            # User clicked "Start Camera Setup"
            if dialog.start_setup_requested:
                self.show_camera_setup_guide()
            elif dialog.setup_complete_requested:
                self.mark_setup_complete()
                QMessageBox.information(
                    self, 'Setup Complete',
                    'Great! Your system is ready to go.\n\n'
                    'You can always access the camera setup guide from the PreConfigured Box tab.'
                )
    
    def setup_ui(self):
        self.setWindowTitle("MemryX + Frigate Launcher - Full Control Center")
        
        # Set window icon if available
        icon_path = os.path.join(self.script_dir, "assets", "frigate.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Get screen size and set window to maximize/fullscreen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # Set window to use available geometry (maximized but respects taskbar)
        self.setGeometry(screen_geometry)
        
        # Alternative: For true fullscreen, uncomment the next line and comment the above
        # self.showFullScreen()
        
        # Set minimum size for when user resizes - optimized for scroll functionality
        # Below this size, content becomes scrollable instead of squeezed
        self.setMinimumSize(800, 600)  # Reduced to allow more flexible sizing with scroll support
        
        # Enable window controls (minimize, maximize, close)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | 
                           Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Apply modern styling with professional colors (Qt-compatible)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fafbfc, stop:1 #f1f3f5);
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', 'system-ui', '-apple-system', sans-serif;
            }
            QMenuBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border-bottom: 1px solid #dee2e6;
                spacing: 3px;
                padding: 6px 10px;
                font-weight: 500;
                font-size: 13px;
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QMenuBar::item {
                padding: 8px 14px;
                border-radius: 6px;
                margin: 1px;
            }
            QMenuBar::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90a4, stop:1 #38758a);
                color: white;
            }
            QMenuBar::item:pressed {
                background: #2d6374;
                color: white;
            }
            QMenu {
                background: white;
                border: 1px solid #cbd5e0;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QMenu::item {
                padding: 10px 26px 10px 34px;
                border-radius: 6px;
                margin: 2px;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90a4, stop:1 #38758a);
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #e2e8f0;
                margin: 4px 16px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                margin-left: 4px;
            }
            QMenu::indicator:checked {
                background: #4a90a4;
                border: 1px solid #38758a;
                border-radius: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e0;
                border-radius: 10px;
                background: white;
                margin-top: 6px;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
                color: #495057;
                padding: 14px 22px;
                margin: 2px 1px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                border: 1px solid #dee2e6;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90a4, stop:1 #38758a);
                color: #ffffff;
                border: 1px solid #38758a;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e3f2fd, stop:1 #bbdefb);
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
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #4a5568;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4a90a4, stop:1 #38758a);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 14px 26px;
                font-weight: 600;
                font-size: 14px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #5b9bb0, stop:1 #428299);
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
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #2d3748;
                selection-background-color: #bee3f8;
                selection-color: #2a4365;
            }
            QTextEdit:focus {
                border: 2px solid #4a90a4;
            }
            QLabel[status="true"] {
                font-size: 16px;
                font-weight: 600;
                padding: 10px;
                border-radius: 8px;
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel[status="repo"] {
                font-size: 14px;
                font-weight: 500;
                padding: 14px;
                border-radius: 10px;
                margin: 6px;
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel {
                color: #2d3748;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QCheckBox {
                color: #2d3748;
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
            
            /* Scrollbar Styling */
            QScrollBar:vertical {
                border: none;
                background: #f8f9fa;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0aec0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header
        self.create_header(layout)
        
        # Main tabs - new structure with 3 primary tabs using lazy loading
        self.main_tab_widget = QTabWidget()
        
        # Initialize tab content tracking
        self._tab_contents = {}
        
        # 1. PreConfigured Box tab (load immediately as it's the default)
        self.main_tab_widget.addTab(self.create_preconfigured_tab(), "📦 PreConfigured Box")
        self._tab_contents[0] = True  # Mark as loaded
        
        # 2. Manual Setup tab (lazy load)
        placeholder_manual = QLabel("Loading Manual Setup...")
        placeholder_manual.setAlignment(Qt.AlignCenter)
        placeholder_manual.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
        self.main_tab_widget.addTab(placeholder_manual, "🔧 Manual Setup")
        self._tab_contents[1] = False  # Mark as not loaded
        
        # 3. Advanced Settings tab (lazy load)
        placeholder_advanced = QLabel("Loading Advanced Settings...")
        placeholder_advanced.setAlignment(Qt.AlignCenter)
        placeholder_advanced.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
        self.main_tab_widget.addTab(placeholder_advanced, "⚙️ Advanced Settings")
        self._tab_contents[2] = False  # Mark as not loaded
        
        # Set PreConfigured Box as default tab (index 0)
        self.main_tab_widget.setCurrentIndex(0)
        
        # Connect tab change handler to manage refresh timer and lazy loading
        self.main_tab_widget.currentChanged.connect(self.on_main_tab_changed)
        self.main_tab_widget.currentChanged.connect(self._load_tab_on_demand)
        
        layout.addWidget(self.main_tab_widget)
        
        # Create status bar
        self.status_label = QLabel("🔄 Initializing...")
        self.status_label.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 8px 12px; border-radius: 4px; font-weight: 600; font-size: 14px;")
        self.statusBar().addPermanentWidget(self.status_label)
        
        self.statusBar().showMessage('Frigate+MemryX Control Center - Initializing...')
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border-top: 1px solid #dee2e6;
                color: #2d3748;
                font-size: 13px;
                padding: 8px 12px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-weight: 500;
            }
        """)
        # Show status bar during initialization
        self.statusBar().show()
    
    def create_menu_bar(self):
        """Create professional menu bar with comprehensive functionality"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        # Open Configuration GUI action
        config_gui_action = file_menu.addAction('&Open Configuration')
        config_gui_action.setShortcut('Ctrl+O')
        config_gui_action.setStatusTip('Open the Frigate configuration')
        config_gui_action.triggered.connect(self.open_config)
        
        # Save Configuration action (for the built-in editor)
        self.save_config_action = file_menu.addAction('&Save Configuration')
        self.save_config_action.setShortcut('Ctrl+S')
        self.save_config_action.setStatusTip('Save the current configuration')
        self.save_config_action.triggered.connect(self.save_configuration)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = file_menu.addAction('E&xit')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close_application)
        
        # Tools menu
        tools_menu = menubar.addMenu('&Tools')
        
        # Docker actions
        start_docker_action = tools_menu.addAction('&Start Frigate')
        start_docker_action.setShortcut('Ctrl+Shift+S')
        start_docker_action.setStatusTip('Start Frigate Docker container')
        start_docker_action.triggered.connect(lambda: self.docker_action('start'))
        
        stop_docker_action = tools_menu.addAction('S&top Frigate')
        stop_docker_action.setShortcut('Ctrl+Shift+T')
        stop_docker_action.setStatusTip('Stop Frigate Docker container')
        stop_docker_action.triggered.connect(lambda: self.docker_action('stop'))
        
        restart_docker_action = tools_menu.addAction('&Restart Frigate')
        restart_docker_action.setShortcut('Ctrl+Shift+R')
        restart_docker_action.setStatusTip('Restart Frigate Docker container')
        restart_docker_action.triggered.connect(lambda: self.docker_action('restart'))
        
        tools_menu.addSeparator()
        
        # System actions
        check_status_action = tools_menu.addAction('Check &System Status')
        check_status_action.setShortcut('F5')
        check_status_action.setStatusTip('Refresh system and Docker status')
        check_status_action.triggered.connect(self.check_system_status)
        
        # Setup reset action (for testing/debugging)
        reset_setup_action = tools_menu.addAction('&Reset First-Run Setup')
        reset_setup_action.setStatusTip('Reset first-run setup to show welcome dialog again')
        reset_setup_action.triggered.connect(self.reset_setup_status_with_confirmation)
        
        # Manual trigger for welcome dialog (for testing)
        show_welcome_action = tools_menu.addAction('&Show Welcome Dialog')
        show_welcome_action.setStatusTip('Manually show the camera setup welcome dialog')
        show_welcome_action.triggered.connect(self._show_welcome_dialog)
        
        clear_logs_action = tools_menu.addAction('&Clear Progress Logs')
        clear_logs_action.setShortcut('Ctrl+L')
        clear_logs_action.setStatusTip('Clear the progress logs in Docker Manager tab')
        clear_logs_action.triggered.connect(self.clear_progress_logs)
        
        tools_menu.addSeparator()
        
        # Advanced tools
        terminal_action = tools_menu.addAction('Open &Terminal Here')
        terminal_action.setShortcut('Ctrl+Alt+T')
        terminal_action.setStatusTip('Open terminal in project directory')
        terminal_action.triggered.connect(self.open_terminal)
        
        # View menu
        view_menu = menubar.addMenu('&View')
        
        # Main tab navigation
        preconfigured_tab_action = view_menu.addAction('&PreConfigured Box Tab')
        preconfigured_tab_action.setShortcut('Ctrl+1')
        preconfigured_tab_action.setStatusTip('Switch to PreConfigured Box tab')
        preconfigured_tab_action.triggered.connect(lambda: self.main_tab_widget.setCurrentIndex(0))
        
        manual_setup_tab_action = view_menu.addAction('&Manual Setup Tab')
        manual_setup_tab_action.setShortcut('Ctrl+2')
        manual_setup_tab_action.setStatusTip('Switch to Manual Setup tab')
        manual_setup_tab_action.triggered.connect(lambda: self.main_tab_widget.setCurrentIndex(1))
        
        advanced_tab_action = view_menu.addAction('&Advanced Settings Tab')
        advanced_tab_action.setShortcut('Ctrl+3')
        advanced_tab_action.setStatusTip('Switch to Advanced Settings tab')
        advanced_tab_action.triggered.connect(lambda: self.main_tab_widget.setCurrentIndex(2))
        
        view_menu.addSeparator()
        
        # Advanced sub-tab navigation (only works when in Advanced Settings tab)
        config_tab_action = view_menu.addAction('Advanced: &Configuration')
        config_tab_action.setShortcut('Ctrl+Shift+1')
        config_tab_action.setStatusTip('Switch to Advanced Settings → Configuration')
        config_tab_action.triggered.connect(self.go_to_advanced_config)
        
        docker_manager_tab_action = view_menu.addAction('Advanced: &Docker Manager')
        docker_manager_tab_action.setShortcut('Ctrl+Shift+2')
        docker_manager_tab_action.setStatusTip('Switch to Advanced Settings → Docker Manager')
        docker_manager_tab_action.triggered.connect(self.go_to_advanced_docker)
        
        docker_logs_tab_action = view_menu.addAction('Advanced: Docker &Logs')
        docker_logs_tab_action.setShortcut('Ctrl+Shift+3')
        docker_logs_tab_action.setStatusTip('Switch to Advanced Settings → Docker Logs')
        docker_logs_tab_action.triggered.connect(self.go_to_advanced_logs)
        
        view_menu.addSeparator()
        
        # Window modes
        self.fullscreen_action = view_menu.addAction('Toggle &Fullscreen')
        self.fullscreen_action.setShortcut('F11')
        self.fullscreen_action.setStatusTip('Toggle fullscreen mode')
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        
        windowed_action = view_menu.addAction('&Windowed Mode')
        windowed_action.setShortcut('Ctrl+W')
        windowed_action.setStatusTip('Switch to windowed mode (3/4 screen)')
        windowed_action.triggered.connect(self.set_windowed_mode)
        
        maximize_action = view_menu.addAction('&Maximize')
        maximize_action.setShortcut('Ctrl+M')
        maximize_action.setStatusTip('Maximize window to available screen space')
        maximize_action.triggered.connect(self.maximize_window)
        
        view_menu.addSeparator()
        
        # Status bar toggle
        self.statusbar_action = view_menu.addAction('Show &Status Bar')
        self.statusbar_action.setCheckable(True)
        self.statusbar_action.setChecked(False)
        self.statusbar_action.setStatusTip('Toggle status bar visibility')
        self.statusbar_action.triggered.connect(self.toggle_statusbar)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        # Documentation actions
        frigate_docs_action = help_menu.addAction('&Frigate Documentation')
        frigate_docs_action.setShortcut('F1')
        frigate_docs_action.setStatusTip('Open Frigate documentation')
        frigate_docs_action.triggered.connect(self.open_frigate_documentation)
        
        memryx_docs_action = help_menu.addAction('&MemryX Documentation')
        memryx_docs_action.setShortcut('F2')
        memryx_docs_action.setStatusTip('Open MemryX developer documentation')
        memryx_docs_action.triggered.connect(self.open_memryx_documentation)
        
        # Keyboard shortcuts action
        shortcuts_action = help_menu.addAction('&Keyboard Shortcuts')
        shortcuts_action.setShortcut('Ctrl+?')
        shortcuts_action.setStatusTip('Show keyboard shortcuts reference')
        shortcuts_action.triggered.connect(self.show_shortcuts)
        
        help_menu.addSeparator()
        
        # System info action
        sysinfo_action = help_menu.addAction('System &Information')
        sysinfo_action.setStatusTip('Show system and application information')
        sysinfo_action.triggered.connect(self.show_system_info)
        
        # About action
        about_action = help_menu.addAction('&About')
        about_action.setStatusTip('About this application')
        about_action.triggered.connect(self.show_about)
    
    def reset_setup_status_with_confirmation(self):
        """Reset setup status with user confirmation"""
        reply = QMessageBox.question(
            self, 'Reset First-Run Setup',
            'This will reset the first-run setup status and show the welcome dialog on next startup.\n\n'
            'Are you sure you want to reset the setup status?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.reset_setup_status()
            QMessageBox.information(
                self, 'Setup Reset',
                'First-run setup status has been reset.\n\n'
                'The welcome dialog will appear the next time you start the application.'
            )
    
    def close_application(self):
        """Close the application with confirmation"""
        reply = QMessageBox.question(
            self, 'Exit Confirmation',
            'Are you sure you want to exit Frigate Launcher?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.close()
    
    def _initialize_async_components(self):
        """Initialize components that require heavy operations after UI is shown"""
        # Initialize status check worker reference
        self.status_worker = None
        
        # Start the initial status check in background thread
        self.start_background_status_check()
        
        # Start the timers after UI is set up and first status check is done
        self.status_timer.start(5000)  # Check every 5 seconds
        self.config_watcher_timer.start(1000)  # Check every 1 second for file changes
        # Timer will be started/stopped based on auto-refresh checkbox state
        
        # Mark initialization as complete
        self.is_initializing = False
        
        # Re-enable buttons now that initialization is complete
        if hasattr(self, 'preconfigured_start_btn'):
            self.preconfigured_start_btn.setEnabled(True)
        if hasattr(self, 'preconfigured_stop_btn'):
            self.preconfigured_stop_btn.setEnabled(True)
        if hasattr(self, 'preconfigured_open_ui_btn'):
            self.preconfigured_open_ui_btn.setEnabled(True)
        if hasattr(self, 'setup_cameras_btn'):
            self.setup_cameras_btn.setEnabled(True)
        if hasattr(self, 'camera_guide_btn'):
            self.camera_guide_btn.setEnabled(True)
        
        # Update status bar to ready state
        if hasattr(self, 'status_label'):
            self.status_label.setText("✅ Ready")
            self.status_label.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 8px 12px; border-radius: 4px; font-weight: 600; font-size: 14px;")
        
        self.statusBar().showMessage('Frigate+MemryX Control Center - Ready | F11: Fullscreen | F5: Refresh | F1: Help | Ctrl+Q: Exit')
        
        # Hide status bar after a delay
        QTimer.singleShot(3000, lambda: self.statusBar().hide())
        
        # Show first-run welcome dialog if this is the first time
        self.show_first_run_welcome()

    def start_background_status_check(self):
        """Start status checking in background thread"""
        # Don't start new worker if one is already running
        if self.status_worker and self.status_worker.isRunning():
            return
            
        self.status_worker = StatusCheckWorker(self.script_dir)
        self.status_worker.status_updated.connect(self.update_status_from_worker)
        self.status_worker.finished.connect(self.on_status_check_finished)
        self.status_worker.start()
    
    def update_status_from_worker(self, status_data):
        """Update UI with status data from background worker"""
        # Update Frigate status labels
        if 'frigate' in status_data:
            frigate_data = status_data['frigate']
            if hasattr(self, 'frigate_status'):
                self.frigate_status.setText(frigate_data['text'])
                self.frigate_status.setStyleSheet(frigate_data['style'])
            if hasattr(self, 'docker_manager_frigate_status'):
                self.docker_manager_frigate_status.setText(frigate_data['text'])
                self.docker_manager_frigate_status.setStyleSheet(frigate_data['style'])
        
        # Update Docker status
        if 'docker' in status_data and hasattr(self, 'docker_status'):
            docker_data = status_data['docker']
            self.docker_status.setText(docker_data['text'])
            self.docker_status.setStyleSheet(docker_data['style'])
        
        # Update config status
        if 'config' in status_data and hasattr(self, 'config_status'):
            config_data = status_data['config']
            self.config_status.setText(config_data['text'])
            self.config_status.setStyleSheet(config_data['style'])
        
        # Update MemryX status  
        if 'memryx' in status_data and hasattr(self, 'memryx_overview_status'):
            memryx_data = status_data['memryx']
            self.memryx_overview_status.setText(memryx_data['text'])
            self.memryx_overview_status.setStyleSheet(memryx_data['style'])
        
        # Update system monitoring (non-blocking)
        self.update_system_monitoring()
        
        # Update button states
        self.update_button_states_from_status(status_data)
    
    def update_button_states_from_status(self, status_data):
        """Update button states based on status data"""
        if 'frigate' in status_data:
            frigate_text = status_data['frigate']['text']
            container_running = '✅ Running' in frigate_text
            container_exists = container_running or '⏸️ Stopped' in frigate_text
            
            # Update button states
            if hasattr(self, 'docker_restart_btn') and hasattr(self, 'docker_remove_btn'):
                self.docker_restart_btn.setEnabled(container_exists)
                self.docker_remove_btn.setEnabled(container_exists)
    
    def on_status_check_finished(self):
        """Called when background status check completes"""
        # Worker finished, clean up reference
        if self.status_worker:
            self.status_worker.deleteLater()
            self.status_worker = None

    def _load_tab_on_demand(self, index):
        """Load tab content on-demand when user switches to it"""
        # Prevent loading if we're already in the process of creating this tab
        if hasattr(self, '_creating_tab_index') and self._creating_tab_index == index:
            return
            
        if index in self._tab_contents and not self._tab_contents[index]:
            # Mark that we're creating this tab to prevent recursive calls
            self._creating_tab_index = index
            
            # Tab hasn't been loaded yet, load it now using QTimer to avoid blocking
            if index == 1:  # Manual Setup tab
                QTimer.singleShot(10, lambda: self._create_tab_content(index, "manual"))
            elif index == 2:  # Advanced Settings tab
                QTimer.singleShot(10, lambda: self._create_tab_content(index, "advanced"))
    
    def _create_tab_content(self, index, tab_type):
        """Create tab content and replace placeholder without triggering tab changes"""
        try:
            if tab_type == "manual":
                content = self.create_manual_setup_tab()
                tab_title = "🔧 Manual Setup"
            elif tab_type == "advanced":
                content = self.create_advanced_settings_tab()
                tab_title = "⚙️ Advanced Settings"
            else:
                return
            
            # Store current tab index to restore it after replacement
            current_index = self.main_tab_widget.currentIndex()
            
            # Replace the placeholder with actual content (no signal needed)
            old_widget = self.main_tab_widget.widget(index)
            self.main_tab_widget.removeTab(index)
            self.main_tab_widget.insertTab(index, content, tab_title)
            
            # Only change to this tab if user is actually on it, otherwise stay on current tab
            if current_index == index:
                self.main_tab_widget.setCurrentIndex(index)
            else:
                # Restore the original current tab
                self.main_tab_widget.setCurrentIndex(current_index)
            
            # Clean up old placeholder widget
            if old_widget:
                old_widget.deleteLater()
            
            # Mark as loaded
            self._tab_contents[index] = True
            
            # Clear creation flag
            if hasattr(self, '_creating_tab_index'):
                delattr(self, '_creating_tab_index')
            
        except Exception as e:
            # On error, show error message in tab
            error_widget = QLabel(f"Error loading tab: {str(e)}")
            error_widget.setAlignment(Qt.AlignCenter)
            error_widget.setStyleSheet("color: red; font-size: 14px; padding: 50px;")
            
            current_index = self.main_tab_widget.currentIndex()
            old_widget = self.main_tab_widget.widget(index)
            self.main_tab_widget.removeTab(index)
            self.main_tab_widget.insertTab(index, error_widget, f"❌ Error")
            
            # Restore current tab or set to error tab if user was on it
            if current_index == index:
                self.main_tab_widget.setCurrentIndex(index)
            else:
                self.main_tab_widget.setCurrentIndex(current_index)
            
            if old_widget:
                old_widget.deleteLater()
            
            # Clear creation flag
            if hasattr(self, '_creating_tab_index'):
                delattr(self, '_creating_tab_index')
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.isFullScreen():
            self.showNormal()
            # Maximize to use available screen space but show taskbar
            screen = QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self.statusBar().showMessage('Maximized mode - F11: Fullscreen | F5: Refresh | ESC: Restore | Ctrl+?: Shortcuts')
        else:
            self.showFullScreen()
            self.statusBar().showMessage('Fullscreen mode - F11/ESC: Exit fullscreen | F5: Refresh | Ctrl+?: Shortcuts')
    
    def set_windowed_mode(self):
        """Set windowed mode (3/4 screen size, centered)"""
        if self.isFullScreen():
            self.showNormal()
        
        # Get screen size and set window to 3/4 of screen size
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # Calculate 3/4 of screen size
        window_width = int(screen_width * 0.75)
        window_height = int(screen_height * 0.75)
        
        # Set window size
        self.resize(window_width, window_height)
        
        # Center the window on screen
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.move(x, y)
        
        # Update status bar
        self.statusBar().showMessage('Windowed mode (3/4 screen) - F11: Fullscreen | F5: Refresh | Ctrl+M: Maximize | Ctrl+?: Shortcuts')
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 'About MemryX + Frigate Launcher',
            '<h3>MemryX + Frigate Launcher</h3>'
            '<p>Version 1.0.0</p>'
            '<p>A comprehensive GUI application for managing Frigate installation and configuration with MemryX hardware acceleration.</p>'
            '<p><b>Features:</b></p>'
            '<ul>'
            '<li>Complete system prerequisites management</li>'
            '<li>Frigate repository setup and updates</li>'
            '<li>Docker container management with detailed logging</li>'
            '<li>Configuration editing and management</li>'
            '<li>Real-time status monitoring</li>'
            '<li>MemryX hardware acceleration support</li>'
            '</ul>'
            '<p><b>Keyboard Shortcuts:</b></p>'
            '<ul>'
            '<li>Ctrl+Q: Exit application</li>'
            '<li>F11: Toggle fullscreen</li>'
            '<li>Ctrl+W: Windowed mode</li>'
            '</ul>'
            '<p>© 2025 - Built for MemryX + Frigate integration</p>'
        )
    
    # Navigation helper methods for advanced settings sub-tabs
    def go_to_advanced_overview(self):
        """Navigate to Advanced Settings → Overview"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(0)  # Overview sub-tab
    
    def go_to_advanced_prerequisites(self):
        """Navigate to Advanced Settings → Prerequisites"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(1)  # Prerequisites sub-tab
    
    def go_to_advanced_setup(self):
        """Navigate to Advanced Settings → Frigate Setup"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(2)  # Frigate Setup sub-tab
    
    def go_to_advanced_config(self):
        """Navigate to Advanced Settings → Configuration"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(0)  # Configuration sub-tab
    
    def go_to_advanced_docker(self):
        """Navigate to Advanced Settings → Docker Manager"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(1)  # Docker Manager sub-tab
    
    def go_to_advanced_logs(self):
        """Navigate to Advanced Settings → Docker Logs"""
        self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings tab
        if hasattr(self, 'advanced_tab_widget'):
            self.advanced_tab_widget.setCurrentIndex(2)  # Docker Logs sub-tab
    
    def go_to_docker_logs(self):
        """Navigate directly to Advanced Settings → Docker Logs tab"""
        try:
            # Switch to Advanced Settings tab (index 2)
            self.main_tab_widget.setCurrentIndex(2)
            
            # Add a small delay to ensure the advanced tab is fully loaded
            def navigate_to_docker_logs():
                if hasattr(self, 'advanced_tab_widget'):
                    # Switch to Docker Logs sub-tab (index 2: Configuration, Docker Manager, Docker Logs)
                    self.advanced_tab_widget.setCurrentIndex(2)  # Docker Logs is the 3rd tab (index 2)
                    print("DEBUG: Navigated to Docker Logs tab (index 2)")
                else:
                    print("DEBUG: advanced_tab_widget not found, retrying...")
                    # If advanced tab isn't loaded yet, wait and try again
                    QTimer.singleShot(500, navigate_to_docker_logs)
            
            # Use a timer to ensure the tab switch happens after the main tab is loaded
            QTimer.singleShot(100, navigate_to_docker_logs)
            
            # Show status message
            self.statusBar().showMessage('Navigated to Docker Logs - Check here for Frigate troubleshooting information')
            
        except Exception as e:
            QMessageBox.warning(
                self, 'Navigation Error',
                f'Could not navigate to Docker Logs:\n{str(e)}'
            )

    # === New Menu Functions ===
    
    def new_configuration(self):
        """Create a new Frigate configuration"""
        reply = QMessageBox.question(
            self, 'New Configuration',
            'This will create a new configuration file. Any unsaved changes will be lost.\n\nContinue?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Switch to Configuration tab
            self.tab_widget.setCurrentIndex(2)
            # Clear the config editor (if it exists)
            if hasattr(self, 'config_preview'):
                self.config_preview.clear()
                self.config_preview.setPlainText("""# New Frigate Configuration
# Add your configuration here

# Example basic configuration:
# cameras:
#   camera_name:
#     ffmpeg:
#       inputs:
#         - path: rtsp://your_camera_ip:554/stream
#           roles:
#             - detect
#             - record
#     detect:
#       width: 1920
#       height: 1080
#       fps: 5

# objects:
#   track:
#     - person
#     - car
#     - cat
#     - dog

# record:
#   enabled: True
#   retain:
#     days: 3
#     mode: all

# snapshots:
#   enabled: True
#   clean_copy: True
#   retain:
#     default: 10
""")
                self.statusBar().showMessage('New configuration created - Use Ctrl+S to save')
    
    def open_configuration(self):
        """Open an existing configuration file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Open Configuration File',
            os.path.expanduser('~'),
            'YAML files (*.yaml *.yml);;All files (*)'
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                
                # Switch to Configuration tab
                self.tab_widget.setCurrentIndex(2)
                
                # Load content into config editor (if it exists)
                if hasattr(self, 'config_preview'):
                    self.config_preview.setPlainText(content)
                    self.statusBar().showMessage(f'Opened configuration: {os.path.basename(filename)}')
                
            except Exception as e:
                QMessageBox.critical(
                    self, 'Error Opening File',
                    f'Could not open configuration file:\n{str(e)}'
                )
    
    def save_configuration(self):
        """Save the current configuration"""
        # Switch to Configuration tab
        self.tab_widget.setCurrentIndex(2)
        
        if hasattr(self, 'config_preview'):
            content = self.config_preview.toPlainText()
            
            if not content.strip():
                QMessageBox.warning(
                    self, 'Empty Configuration',
                    'Cannot save empty configuration file.'
                )
                return
            
            filename, _ = QFileDialog.getSaveFileName(
                self, 'Save Configuration File',
                os.path.expanduser('~/config.yaml'),
                'YAML files (*.yaml *.yml);;All files (*)'
            )
            
            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(content)
                    
                    self.statusBar().showMessage(f'Configuration saved: {os.path.basename(filename)}')
                    
                    QMessageBox.information(
                        self, 'Configuration Saved',
                        f'Configuration successfully saved to:\n{filename}'
                    )
                    
                except Exception as e:
                    QMessageBox.critical(
                        self, 'Error Saving File',
                        f'Could not save configuration file:\n{str(e)}'
                    )
        else:
            QMessageBox.warning(
                self, 'No Configuration Editor',
                'Configuration editor not available. Please use the Configuration tab.'
            )
    
    def check_system_status(self):
        """Refresh system and Docker status"""
        # Switch to Overview tab
        self.tab_widget.setCurrentIndex(0)
        self.statusBar().showMessage('Refreshing system status...')
        
        # Trigger status update (if the method exists)
        if hasattr(self, 'update_overview_status'):
            self.update_overview_status()
        
        self.statusBar().showMessage('System status refreshed - Press F5 to refresh again')
    
    def clear_progress_logs(self):
        """Clear the progress logs in Docker Manager tab"""
        reply = QMessageBox.question(
            self, 'Clear Logs',
            'Clear all progress logs in the Docker Manager tab?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Switch to Docker Manager tab
            self.tab_widget.setCurrentIndex(3)
            
            # Clear progress logs (if they exist)
            if hasattr(self, 'progress_display'):
                self.progress_display.clear()
                self.statusBar().showMessage('Progress logs cleared')
    
    def open_terminal(self):
        """Open terminal in project directory"""
        try:
            project_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try different terminal applications
            terminals = ['gnome-terminal', 'konsole', 'xterm', 'terminator']
            
            for terminal in terminals:
                try:
                    if terminal == 'gnome-terminal':
                        subprocess.Popen([terminal, '--working-directory', project_dir])
                    elif terminal == 'konsole':
                        subprocess.Popen([terminal, '--workdir', project_dir])
                    else:
                        subprocess.Popen([terminal], cwd=project_dir)
                    
                    self.statusBar().showMessage(f'Opened {terminal} in project directory')
                    return
                    
                except FileNotFoundError:
                    continue
            
            # Fallback: show directory path
            QMessageBox.information(
                self, 'Terminal Not Found',
                f'Could not open terminal automatically.\n\nProject directory:\n{project_dir}'
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Terminal',
                f'Could not open terminal:\n{str(e)}'
            )
    
    def maximize_window(self):
        """Maximize window to available screen space"""
        if self.isFullScreen():
            self.showNormal()
        
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.availableGeometry())
        self.statusBar().showMessage('Maximized mode - F11: Fullscreen | F5: Refresh | Ctrl+W: Windowed | Ctrl+?: Shortcuts')
    
    def toggle_statusbar(self):
        """Toggle status bar visibility"""
        if self.statusbar_action.isChecked():
            self.statusBar().show()
        else:
            self.statusBar().hide()
    
    def open_frigate_documentation(self):
        """Open Frigate documentation in browser"""
        import webbrowser
        try:
            webbrowser.open('https://docs.frigate.video/')
            self.statusBar().showMessage('Opened Frigate documentation in browser')
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Documentation',
                f'Could not open documentation:\n{str(e)}\n\nPlease visit: https://docs.frigate.video/'
            )
    
    def open_memryx_documentation(self):
        """Open MemryX documentation in browser"""
        import webbrowser
        try:
            webbrowser.open('https://developer.memryx.com/')
            self.statusBar().showMessage('Opened MemryX documentation in browser')
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Documentation',
                f'Could not open documentation:\n{str(e)}\n\nPlease visit: https://developer.memryx.com/'
            )
    
    def open_frigate_web_ui(self):
        """Open Frigate Web UI in browser"""
        import webbrowser
        try:
            # Default Frigate web UI URL (localhost:5000)
            frigate_url = 'http://localhost:5000'
            webbrowser.open(frigate_url)
            self.statusBar().showMessage('Opened Frigate Web UI in browser')
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Web UI',
                f'Could not open Frigate Web UI:\n{str(e)}\n\nPlease ensure Frigate is running and visit: http://localhost:5000'
            )
    
    def show_shortcuts(self):
        """Show keyboard shortcuts reference"""
        shortcuts_text = """<h3>Keyboard Shortcuts Reference</h3>
        
        <p><b>File Menu:</b></p>
        <ul>
        <li>Ctrl+O: Open Configuration GUI</li>
        <li>Ctrl+S: Save Configuration</li>
        <li>Ctrl+Q: Exit Application</li>
        </ul>
        
        <p><b>Tools Menu:</b></p>
        <ul>
        <li>Ctrl+Shift+S: Start Frigate</li>
        <li>Ctrl+Shift+T: Stop Frigate</li>
        <li>Ctrl+Shift+R: Restart Frigate</li>
        <li>F5: Check System Status</li>
        <li>Ctrl+L: Clear Progress Logs</li>
        <li>Ctrl+Alt+T: Open Terminal</li>
        </ul>
        
        <p><b>View Menu:</b></p>
        <ul>
        <li>Ctrl+1: PreConfigured Box Tab</li>
        <li>Ctrl+2: Manual Setup Tab</li>
        <li>Ctrl+3: Advanced Settings Tab</li>
        <li>F11: Toggle Fullscreen</li>
        <li>Ctrl+W: Windowed Mode</li>
        <li>Ctrl+M: Maximize Window</li>
        </ul>
        
        <p><b>Advanced Settings Sub-tabs:</b></p>
        <ul>
        <li>Ctrl+Shift+1: Advanced → Configuration</li>
        <li>Ctrl+Shift+2: Advanced → Docker Manager</li>
        <li>Ctrl+Shift+3: Advanced → Docker Logs</li>
        </ul>
        
        <p><b>Help Menu:</b></p>
        <ul>
        <li>F1: Open Frigate Documentation</li>
        <li>F2: Open MemryX Documentation</li>
        <li>Ctrl+?: Show Shortcuts</li>
        </ul>
        
        <p><b>Global Shortcuts:</b></p>
        <ul>
        <li>ESC: Exit Fullscreen Mode</li>
        </ul>"""
        
        QMessageBox.about(self, 'Keyboard Shortcuts', shortcuts_text)
    
    def show_system_info(self):
        """Show system and application information"""
        try:
            import platform
            import sys
            
            # Get system information
            system_info = f"""<h3>System Information</h3>
            
            <p><b>Application:</b></p>
            <ul>
            <li>Name: MemryX + Frigate Launcher</li>
            <li>Version: 1.0.0</li>
            <li>Python Version: {sys.version.split()[0]}</li>
            </ul>
            
            <p><b>System:</b></p>
            <ul>
            <li>OS: {platform.system()} {platform.release()}</li>
            <li>Architecture: {platform.machine()}</li>
            <li>Processor: {platform.processor() or 'Unknown'}</li>
            <li>Python Implementation: {platform.python_implementation()}</li>
            </ul>
            
            <p><b>Environment:</b></p>
            <ul>
            <li>Working Directory: {os.getcwd()}</li>
            <li>User Home: {os.path.expanduser('~')}</li>
            </ul>"""
            
            QMessageBox.about(self, 'System Information', system_info)
            
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Getting System Info',
                f'Could not retrieve system information:\n{str(e)}'
            )
    
    # === End of New Menu Functions ===
    
    # === PreConfigured Box Tab Methods ===
    
    def update_preconfigured_status(self):
        """Update status indicators in PreConfigured Box tab using existing check methods"""
        try:
            # MemryX devices check (using exact same logic as overview tab)
            try:
                memryx_devices = self.get_memryx_devices()
                if "No devices found" in memryx_devices or memryx_devices == "0":
                    self.preconfigured_memryx_status.setText("❌ No Devices")
                    self.preconfigured_memryx_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;")
                else:
                    self.preconfigured_memryx_status.setText(f"✅ {memryx_devices}")
                    self.preconfigured_memryx_status.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;")
            except Exception:
                self.preconfigured_memryx_status.setText("❓ Check Failed")
                self.preconfigured_memryx_status.setStyleSheet("background: #fef5e7; color: #8b5a00; padding: 6px; border-radius: 4px;")
            
            # Frigate setup check (check if frigate repository exists)
            try:
                frigate_path = os.path.join(self.script_dir, 'frigate')
                if os.path.exists(frigate_path):
                    # Check if it's a valid git repository with proper structure
                    git_dir = os.path.join(frigate_path, '.git')
                    if os.path.exists(git_dir):
                        self.preconfigured_frigate_status.setText("✅ Setup Complete")
                        self.preconfigured_frigate_status.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 6px; border-radius: 4px;")
                    else:
                        self.preconfigured_frigate_status.setText("⚠️ Setup Incomplete")
                        self.preconfigured_frigate_status.setStyleSheet("background: #fef5e7; color: #8b5a00; padding: 6px; border-radius: 4px;")
                else:
                    self.preconfigured_frigate_status.setText("❌ Setup Required")
                    self.preconfigured_frigate_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 6px; border-radius: 4px;")
            except Exception:
                self.preconfigured_frigate_status.setText("❓ Check Failed")
            
            # Update button states based on container status
            self.update_preconfigured_button_states()
            
            # Update warning messages based on system status
            self.update_preconfigured_warnings()
                
        except Exception as e:
            # Fallback if something goes wrong
            print(f"Error updating preconfigured status: {e}")

    def update_preconfigured_button_states(self):
        """Update start/stop button states based on container status"""
        try:
            # Check if container exists and is running
            container_exists = self._check_container_exists_sync()
            container_running = False
            
            if container_exists:
                try:
                    result = subprocess.run(['docker', 'ps', '--filter', 'name=frigate', '--format', '{{.Names}}'],
                                          capture_output=True, text=True, timeout=5)
                    container_running = 'frigate' in result.stdout
                except:
                    container_running = False
            
            # Track container status changes to show Web UI guidance
            if not hasattr(self, '_previous_container_running'):
                self._previous_container_running = False
            
            # Check if container just started running (transition from not running to running)
            if not self._previous_container_running and container_running:
                # Container just started running - show Web UI guidance after a short delay
                QTimer.singleShot(3000, self.show_web_ui_guidance)  # 3 second delay
            
            # Update the previous state
            self._previous_container_running = container_running
            
            # Update button states using enhanced state management
            if hasattr(self, 'preconfigured_start_btn') and hasattr(self, 'preconfigured_stop_btn'):
                # Skip if currently in an operation state (building, starting, stopping)
                if hasattr(self, 'button_operation_state') and self.button_operation_state in ["building", "starting", "stopping"]:
                    return
                    
                if container_running:
                    # Container is running - show running state
                    self.update_preconfigured_button_state("running")
                    self.preconfigured_start_btn.setToolTip("Frigate container is already running")
                    self.preconfigured_stop_btn.setToolTip("Stop and remove Frigate container completely")
                elif container_exists:
                    # Container exists but not running - show idle state
                    self.update_preconfigured_button_state("idle")
                    self.preconfigured_start_btn.setToolTip("Start existing Frigate container")
                    self.preconfigured_stop_btn.setToolTip("Container is stopped - click Start to run")
                else:
                    # No container - show idle state (will be built on start)
                    self.update_preconfigured_button_state("idle")
                    self.preconfigured_start_btn.setToolTip("Build and start new Frigate container")
                    self.preconfigured_stop_btn.setToolTip("No container to stop")
            
            # Update Web UI button state - only enabled when container is running
            if hasattr(self, 'preconfigured_open_ui_btn'):
                if container_running:
                    self.preconfigured_open_ui_btn.setEnabled(True)
                    self.preconfigured_open_ui_btn.setToolTip("Open Frigate Web UI (Frigate is running)")
                    # Reset any highlighting style that might have been applied
                    if hasattr(self, '_web_ui_btn_original_style'):
                        self.preconfigured_open_ui_btn.setStyleSheet(self._web_ui_btn_original_style)
                else:
                    self.preconfigured_open_ui_btn.setEnabled(False)
                    self.preconfigured_open_ui_btn.setToolTip("Start Frigate first to access Web UI")
                    # Reset any highlighting style when disabled
                    if hasattr(self, '_web_ui_btn_original_style'):
                        self.preconfigured_open_ui_btn.setStyleSheet(self._web_ui_btn_original_style)
            
            # Show/hide troubleshooting section based on container status
            if hasattr(self, 'troubleshooting_group'):
                # Show troubleshooting ONLY when Frigate container is running
                # (same condition as when Web UI button is enabled)
                self.troubleshooting_group.setVisible(container_running)
                    
        except Exception as e:
            # On error, show idle state and enable start button
            if hasattr(self, 'preconfigured_start_btn') and hasattr(self, 'preconfigured_stop_btn'):
                self.update_preconfigured_button_state("idle")
            if hasattr(self, 'preconfigured_open_ui_btn'):
                self.preconfigured_open_ui_btn.setEnabled(False)
                self.preconfigured_open_ui_btn.setToolTip("Unable to check Frigate status")
            # Hide troubleshooting section on error
            if hasattr(self, 'troubleshooting_group'):
                self.troubleshooting_group.setVisible(False)
            print(f"Error updating button states: {e}")
    
    def update_preconfigured_warnings(self):
        """Show/hide warning messages based on system status"""
        try:
            docker_issue = False
            memryx_issue = False
            frigate_issue = False
            
            # Check Docker status - only flag true installation issues
            try:
                docker_status = self._check_docker_status()
                # Only show warning for actual installation issues, not temporary problems
                if "Not Installed" in docker_status['text']:
                    docker_issue = True
                # Don't flag "Not Available" or "Timeout" as installation issues - could be temporary
            except Exception:
                # Exception during check could mean Docker is not installed
                try:
                    # Double-check with simpler command
                    import subprocess
                    subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5, check=True)
                    # If docker --version works, it's installed but maybe service issue
                    docker_issue = False
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    # Docker command not found - truly not installed
                    docker_issue = True
            
            # Check MemryX status
            try:
                memryx_devices = self.get_memryx_devices()
                if "No devices found" in memryx_devices or memryx_devices == "0":
                    memryx_issue = True
            except Exception:
                memryx_issue = True
            
            # Check Frigate status
            try:
                frigate_path = os.path.join(self.script_dir, 'frigate')
                if not os.path.exists(frigate_path):
                    frigate_issue = True
                else:
                    git_dir = os.path.join(frigate_path, '.git')
                    if not os.path.exists(git_dir):
                        frigate_issue = True
            except Exception:
                frigate_issue = True
            
            # Show/hide warning messages
            if hasattr(self, 'docker_warning'):
                self.docker_warning.setVisible(docker_issue)
            if hasattr(self, 'memryx_warning'):
                self.memryx_warning.setVisible(memryx_issue)
            if hasattr(self, 'frigate_warning'):
                self.frigate_warning.setVisible(frigate_issue)
            if hasattr(self, 'manual_setup_btn'):
                self.manual_setup_btn.setVisible(docker_issue or memryx_issue or frigate_issue)
            if hasattr(self, 'warning_group'):
                self.warning_group.setVisible(docker_issue or memryx_issue or frigate_issue)
                
                # Disable start button if system setup is required
                if hasattr(self, 'preconfigured_start_btn'):
                    if docker_issue or memryx_issue or frigate_issue:
                        self.preconfigured_start_btn.setEnabled(False)
                        self.preconfigured_start_btn.setToolTip("System setup required before starting Frigate")
                    else:
                        # Only enable if no warnings and not in a disabled state
                        if hasattr(self, 'button_operation_state') and self.button_operation_state not in ['building', 'starting', 'stopping']:
                            self.preconfigured_start_btn.setEnabled(True)
                            self.preconfigured_start_btn.setToolTip("Start Frigate container")
                
        except Exception as e:
            print(f"Error updating warnings: {e}")
    
    def on_main_tab_changed(self, index):
        """Handle main tab changes to optimize refresh timer"""
        try:
            if hasattr(self, 'preconfigured_refresh_timer'):
                if index == 0:  # PreConfigured Box tab
                    # Start/resume the refresh timer when on PreConfigured tab
                    if not self.preconfigured_refresh_timer.isActive():
                        self.preconfigured_refresh_timer.start()
                    # Also trigger an immediate refresh when switching to the tab
                    QTimer.singleShot(100, self.update_preconfigured_status)
                else:
                    # Stop the refresh timer when not on PreConfigured tab to save resources
                    if self.preconfigured_refresh_timer.isActive():
                        self.preconfigured_refresh_timer.stop()
        except Exception as e:
            print(f"Error handling tab change: {e}")
    
    def open_simple_camera_gui(self):
        """Open the simple camera GUI"""
        # Check if application is still initializing
        if self.is_initializing:
            QMessageBox.information(
                self, "Please Wait", 
                "The application is still initializing. Please wait for the initialization to complete.",
                QMessageBox.Ok
            )
            return
            
        if SimpleCameraGUI is None:
            QMessageBox.critical(
                self, 'Simple Camera GUI Unavailable',
                'The Simple Camera GUI could not be loaded.\n'
                'Please ensure simple_camera_gui.py is available in the same directory.'
            )
            return
        
        try:
            # Create and show the simple camera GUI
            self.camera_gui = SimpleCameraGUI()
            # Pass reference to this launcher so camera GUI can suppress popups
            self.camera_gui.launcher_parent = self
            
            # Wrap the save_config method to detect successful saves
            original_save_config = self.camera_gui.save_config
            
            def enhanced_save_config():
                try:
                    # Call the original save_config method
                    original_save_config()
                    # If we get here, save was successful (no exception thrown)
                    # Trigger our guidance dialog
                    self.on_camera_config_saved()
                except Exception as e:
                    # If save failed, re-raise the exception to maintain original behavior
                    raise e
            
            # Replace the save_config method with our enhanced version
            self.camera_gui.save_config = enhanced_save_config
            
            self.camera_gui.show()
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Camera GUI',
                f'Could not open the Simple Camera GUI:\n{str(e)}'
            )

    def on_camera_gui_closed(self):
        """Handle when camera GUI is closed - no longer shows guidance"""
        # Removed automatic guidance on close
        # Guidance now only shows when config is actually saved
        pass

    def on_camera_config_saved(self):
        """Handle when camera configuration is saved - show guidance to start Frigate"""
        # Small delay to ensure the save operation is complete
        QTimer.singleShot(500, self.show_start_frigate_guidance)

    def show_start_frigate_guidance(self):
        """Show guidance dialog to start Frigate after camera configuration"""
        guidance_dialog = QDialog(self)
        guidance_dialog.setWindowTitle("Cameras Configured!")
        guidance_dialog.setFixedSize(500, 350)
        guidance_dialog.setModal(True)
        
        # Create layout
        layout = QVBoxLayout(guidance_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icon and title
        title_layout = QHBoxLayout()
        
        # Icon label
        icon_label = QLabel("🎉")
        icon_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Great! Cameras Configured!")
        title_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0694a2;
            margin-left: 10px;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Guidance text
        guidance_text = QLabel(
            "Your cameras are now configured. 🎥<br><br>"
            "Now it's time for the final step:<br><br>"
            "🚀 <b>Click the \"Start Frigate\" button</b> to begin monitoring your cameras!<br><br>"
        )
        guidance_text.setTextFormat(Qt.RichText)
        guidance_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: #2d3748;
            line-height: 1.5;
            padding: 15px;
            background: #f0fff4;
            border-radius: 8px;
            border-left: 4px solid #0694a2;
        """)
        guidance_text.setWordWrap(True)
        layout.addWidget(guidance_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Highlight button
        highlight_btn = QPushButton("🔥 Show Me Start Frigate")
        highlight_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0891b2, stop: 1 #164e63);
            }
        """)
        highlight_btn.clicked.connect(lambda: self.highlight_start_frigate_button(guidance_dialog))
        
        # Got it button
        got_it_btn = QPushButton("Let's Go!")
        got_it_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #2d3748;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #cbd5e0;
            }
        """)
        got_it_btn.clicked.connect(guidance_dialog.accept)
        
        button_layout.addWidget(highlight_btn)
        button_layout.addStretch()
        button_layout.addWidget(got_it_btn)
        
        layout.addLayout(button_layout)
        
        # Show guidance dialog
        guidance_dialog.exec()

    def highlight_start_frigate_button(self, guidance_dialog):
        """Highlight the Start Frigate button"""
        guidance_dialog.accept()  # Close guidance dialog
        
        # Find the Start Frigate button and highlight it
        if hasattr(self, 'preconfigured_start_btn'):
            # Store original stylesheet
            original_style = self.preconfigured_start_btn.styleSheet()
            
            # Apply highlight style
            highlight_style = """
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #c084fc, stop: 1 #a855f7);
                    color: white;
                    border: 3px solid #c084fc;
                    border-radius: 8px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 16px;
                    font-weight: 700;
                    text-align: center;
                    padding: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ddd6fe, stop: 1 #8b5cf6);
                }
            """
            
            self.preconfigured_start_btn.setStyleSheet(highlight_style)
            
            # Reset to original style after 5 seconds
            QTimer.singleShot(5000, lambda: self.preconfigured_start_btn.setStyleSheet(original_style))

    def show_web_ui_guidance(self):
        """Show guidance dialog to open Frigate Web UI after Frigate starts"""
        # Check if we should show this guidance (not shown before)
        web_ui_guidance_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.web_ui_guidance_shown')
        if os.path.exists(web_ui_guidance_file):
            return  # Don't show again
        
        guidance_dialog = QDialog(self)
        guidance_dialog.setWindowTitle("Frigate is Now Running!")
        guidance_dialog.setFixedSize(520, 350)
        guidance_dialog.setModal(True)
        
        # Create layout
        layout = QVBoxLayout(guidance_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icon and title
        title_layout = QHBoxLayout()
        
        # Icon label
        icon_label = QLabel("🎉")
        icon_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Frigate is Now Running!")
        title_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0694a2;
            margin-left: 10px;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Guidance text
        guidance_text = QLabel(
            "🚀 Frigate has started successfully!<br><br>"
            "🌐 Click the <b>\"Open Frigate Web UI\" button</b> to view your camera feeds and manage settings.<br><br>"
        )
        guidance_text.setTextFormat(Qt.RichText)
        guidance_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: #2d3748;
            line-height: 1.5;
            padding: 15px;
            background: #f0fff4;
            border-radius: 8px;
            border-left: 4px solid #0694a2;
        """)
        guidance_text.setWordWrap(True)
        layout.addWidget(guidance_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Highlight button
        highlight_btn = QPushButton("🔍 Show Me Web UI Button")
        highlight_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0891b2, stop: 1 #164e63);
            }
        """)
        highlight_btn.clicked.connect(lambda: self.highlight_web_ui_button(guidance_dialog))
        
        # Got it button
        got_it_btn = QPushButton("Got It!")
        got_it_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #2d3748;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #cbd5e0;
            }
        """)
        got_it_btn.clicked.connect(lambda: self.close_web_ui_guidance(guidance_dialog, web_ui_guidance_file))
        
        button_layout.addWidget(highlight_btn)
        button_layout.addStretch()
        button_layout.addWidget(got_it_btn)
        
        layout.addLayout(button_layout)
        
        # Show guidance dialog
        guidance_dialog.exec()

    def highlight_web_ui_button(self, guidance_dialog):
        """Highlight the Open Frigate Web UI button"""
        guidance_dialog.accept()  # Close guidance dialog
        
        # Find the Web UI button and highlight it
        if hasattr(self, 'preconfigured_open_ui_btn'):
            # Store original stylesheet for proper restoration
            self._web_ui_btn_original_style = self.preconfigured_open_ui_btn.styleSheet()
            
            # Apply highlight style
            highlight_style = """
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #c084fc, stop: 1 #a855f7);
                    color: white;
                    border: 3px solid #c084fc;
                    border-radius: 8px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 16px;
                    font-weight: 700;
                    text-align: center;
                    padding: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ddd6fe, stop: 1 #8b5cf6);
                }
                QPushButton:disabled {
                    background: #e2e8f0;
                    color: #a0aec0;
                    border: 1px solid #cbd5e0;
                }
            """
            
            self.preconfigured_open_ui_btn.setStyleSheet(highlight_style)
            
            # Reset to original style after 5 seconds
            QTimer.singleShot(5000, lambda: self.preconfigured_open_ui_btn.setStyleSheet(self._web_ui_btn_original_style))

    def close_web_ui_guidance(self, dialog, guidance_file):
        """Close the Web UI guidance and mark as shown"""
        dialog.accept()
        # Create file to mark that guidance has been shown
        try:
            with open(guidance_file, 'w') as f:
                f.write("shown")
        except:
            pass  # Ignore errors creating the tracking file

    def show_camera_setup_guide(self):
        """Display the camera setup guide in a professional dialog with modern styling"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Setup Guide")
        dialog.resize(1100, 800)  # Slightly smaller for better fit
        dialog.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #e2e8f0);
            }
        """)
        
        # Create main layout
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Modern header with gradient and shadow
        header_frame = QFrame()
        header_frame.setFixedHeight(85)  # Smaller header
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                border: none;
                border-bottom: 2px solid rgba(0,0,0,0.15);
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(25, 15, 25, 15)
        
        # Header icon and title
        icon_label = QLabel("📹")
        icon_label.setStyleSheet("""
            font-size: 28px;
            color: white;
            background: rgba(255,255,255,0.15);
            border-radius: 20px;
            padding: 6px;
            margin-right: 12px;
        """)
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        
        title_label = QLabel("Camera Setup Guide")
        title_label.setStyleSheet("""
            font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: white;
            background: none;
        """)
        
        subtitle_label = QLabel("Complete step-by-step setup instructions")
        subtitle_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: rgba(255,255,255,0.9);
            background: none;
            margin-top: 3px;
        """)
        
        title_container = QVBoxLayout()
        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)
        title_container.setSpacing(5)
        title_container.setContentsMargins(0, 0, 0, 0)
        
        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        
        main_layout.addWidget(header_frame)
        
        # Content area with modern card-style design
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #e2e8f0;
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0aec0;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 20, 30, 20)  # Reduced margins
        content_layout.setSpacing(18)  # Tighter spacing
        
        # Get cam_assets directory
        cam_assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cam_assets")
        
        # Step data with modern styling
        steps = [
            {
                "title": "STEP 1: Power On Camera",
                "description": "Connect the power adapter to your camera's power port and wait 30 seconds for initialization.",
                "points": [
                    "Look for the green LED light on the camera's back",
                    "Camera may rotate during startup (normal behavior)",
                    "Green LED solid = ready for setup"
                ],
                "image": None
            },
            {
                "title": "STEP 2: Install Mobile App",
                "description": "Download 'Amcrest View Pro' from your device's app store.",
                "points": [
                    "iOS: App Store | Android: Google Play Store",
                    "Search for 'Amcrest View Pro'",
                    "Install and open the app"
                ],
                "image": "setup_1.png"
            },
            {
                "title": "STEP 3: App Initial Setup",
                "description": "Launch the app and follow the welcome screens.",
                "points": [
                    "Allow required permissions (camera, location)",
                    "Tap 'Start' to begin setup"
                ],
                "image": "setup_2.jpg"
            },
            {
                "title": "STEP 4: Select WiFi Camera",
                "description": "Choose WiFi Camera setup option.",
                "points": [
                    "Select 'WiFi Camera' from menu"
                ],
                "image": "setup_3.jpg"
            },
            {
                "title": "STEP 4.1: WiFi Configuration Setup",
                "description": "Select WiFi configuration setup option.",
                "points": [
                    "Choose WiFi configuration setup",
                    "<b>Important: Your phone must be connected to the WiFi network you want the camera to use</b>"
                ],
                "image": "setup_4.jpg"
            },
            {
                "title": "STEP 5: Scan Camera QR Code",
                "description": "Find and scan the QR code on your camera's back.",
                "points": [
                    "Allow camera access for QR scanning",
                    "Locate QR code on camera's back and scan it"
                ],
                "image": "setup_5.jpg"
            },
            {
                "title": "STEP 6: Configure Camera Settings",
                "description": "Set up camera name and credentials.",
                "points": [
                    "Enter a descriptive camera name (e.g., 'Front Door', 'Garage')",
                    "Default username/password: admin/admin"
                ],
                "image": "setup_7.jpg"
            },
            {
                "title": "STEP 6.1: Enter WiFi Password",
                "description": "Enter your WiFi network password.",
                "points": [
                    "Enter your WiFi network password carefully",
                    "Ensure password is correct",
                    "Double-check for typos"
                ],
                "image": "setup_8.jpg"
            },
            {
                "title": "STEP 7: Network Connection",
                "description": "Connect camera to your network.",
                "points": [
                    "Allow app to find local network devices",
                    "Wait for WiFi connection process (30-60 seconds)"
                ],
                "image": "setup_9.jpg"
            },
            {
                "title": "STEP 7.1: Connection Success",
                "description": "Camera setup completed successfully.",
                "points": [
                    "Connection successful! Camera is now online",
                    "Click on 'Start Live View' to proceed",
                    "Camera is ready for use"
                ],
                "image": "setup_11.jpg"
            },
            {
                "title": "STEP 8: Set Security Password",
                "description": "Create a secure password for camera access.",
                "points": [
                    "Tap 'Start Live View'",
                    "Create strong password (8-32 characters)",
                    "Use mix of letters and numbers"
                ],
                "image": "setup_12.jpg"
            }
        ]
        
        # Create step cards
        for i, step in enumerate(steps):
            step_frame = QFrame()
            step_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    padding: 0;
                    margin: 3px 0;
                }
                QFrame:hover {
                    border: 1px solid #0694a2;
                    background: #f8faff;
                }
            """)
            
            step_layout = QHBoxLayout(step_frame)
            step_layout.setContentsMargins(18, 12, 18, 12)
            step_layout.setSpacing(16)
            
            # Left content area
            left_content = QVBoxLayout()
            left_content.setSpacing(8)
            
            # Step header
            step_header = QLabel(step["title"])
            step_header.setStyleSheet("""
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                font-weight: 700;
                color: #1a365d;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                padding: 10px 18px;
                border-radius: 6px;
                margin-bottom: 5px;
            """)
            
            # Description
            desc_label = QLabel(step["description"])
            desc_label.setStyleSheet("""
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            """)
            desc_label.setWordWrap(True)
            
            # Points list
            points_widget = QWidget()
            points_layout = QVBoxLayout(points_widget)
            points_layout.setContentsMargins(0, 0, 0, 0)
            points_layout.setSpacing(3)
            
            for point in step["points"]:
                point_label = QLabel(f"<span style='color: #0694a2; font-weight: bold;'>•</span> {point}")
                point_label.setStyleSheet("""
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 15px;
                    color: #4a5568;
                    padding: 3px 0;
                """)
                point_label.setWordWrap(True)
                points_layout.addWidget(point_label)
            
            left_content.addWidget(step_header)
            left_content.addWidget(desc_label)
            left_content.addWidget(points_widget)
            left_content.addStretch()
            
            step_layout.addLayout(left_content, 2)
            
            # Right image area
            if step["image"]:
                image_label = QLabel()
                image_path = os.path.join(cam_assets_dir, step["image"])
                
                if os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        # Scale image to fit nicely
                        scaled_pixmap = pixmap.scaled(250, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        image_label.setPixmap(scaled_pixmap)
                        image_label.setStyleSheet("""
                            border: 2px solid #e2e8f0;
                            border-radius: 8px;
                            padding: 5px;
                            background: #f7fafc;
                        """)
                        image_label.setAlignment(Qt.AlignCenter)
                        step_layout.addWidget(image_label, 1)
                
            content_layout.addWidget(step_frame)
        
        # Completion section
        completion_frame = QFrame()
        completion_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                border: none;
                border-radius: 10px;
                padding: 15px;
                margin: 8px 0;
            }
        """)
        
        completion_layout = QVBoxLayout(completion_frame)
        completion_layout.setSpacing(8)
        
        completion_title = QLabel("🎉 SETUP COMPLETE!")
        completion_title.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: white;
        """)
        
        credentials_text = QLabel("Your camera credentials: Username: admin | Password: [your secure password]")
        credentials_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 16px;
            color: white;
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 6px;
        """)
        
        completion_layout.addWidget(completion_title)
        completion_layout.addWidget(credentials_text)
        
        content_layout.addWidget(completion_frame)
        
        # Frigate Integration Steps (after hardware setup completion)
        frigate_steps = [
            {
                "title": "NEXT STEPS: Configure Camera in Frigate",
                "description": "Now that your camera is set up, add it to Frigate for AI detection.",
                "points": [
                    "Camera hardware setup is complete",
                    "Next: Add camera to Frigate application",
                    "Use the 'Set Up Your Cameras' button below"
                ],
                "image": "gui_1.png"
            },
            {
                "title": "STEP 9: Open Camera Setup Tool", 
                "description": "Go to setup your camera button to add cameras to Frigate.",
                "points": [
                    "Click on 'Set Up Your Cameras' button",
                    "This opens the camera configuration interface",
                    "You'll configure detection and recording settings"
                ],
                "image": "gui_2.png"
            },
            {
                "title": "STEP 10: Discover Camera IP Address",
                "description": "Inside the setup tool, click on discover camera button to identify IP addresses.",
                "points": [
                    "Click on 'Discover Camera' button",
                    "This will scan your network for IP cameras",
                    "Automatically finds camera IP addresses"
                ],
                "image": "gui_3.png"
            },
            {
                "title": "STEP 11: Start Network Scan",
                "description": "Start scan to identify the IP addresses of cameras connected in your house.",
                "points": [
                    "Click 'Start Scan' to begin network discovery",
                    "Wait for scan to complete (may take 30-60 seconds)",
                    "All connected IP cameras will be detected"
                ],
                "image": "gui_4.png"
            },
            {
                "title": "STEP 12: Select Camera and Configure",
                "description": "Select your IP camera and enter username/password to complete setup.",
                "points": [
                    "You will see detected IP cameras in the list",
                    "Select your camera from the discovered devices",
                    "Enter the username and password you created earlier",
                    "Click to proceed and complete camera integration"
                ],
                "image": "gui_5.png"
            }
        ]
        
        # Create Frigate integration step cards
        for i, step in enumerate(frigate_steps):
            step_frame = QFrame()
            step_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    padding: 0;
                    margin: 3px 0;
                }
                QFrame:hover {
                    border: 1px solid #0694a2;
                    background: #f9fafb;
                }
            """)
            
            step_layout = QHBoxLayout(step_frame)
            step_layout.setContentsMargins(20, 15, 20, 15)
            step_layout.setSpacing(20)
            
            # Left content area
            left_content = QVBoxLayout()
            left_content.setSpacing(8)
            
            # Step header
            step_header = QLabel(step["title"])
            step_header.setStyleSheet("""
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                font-weight: 700;
                color: #1a365d;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                padding: 10px 18px;
                border-radius: 6px;
                margin-bottom: 5px;
            """)
            
            # Description
            desc_label = QLabel(step["description"])
            desc_label.setStyleSheet("""
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            """)
            desc_label.setWordWrap(True)
            
            # Points list
            points_widget = QWidget()
            points_layout = QVBoxLayout(points_widget)
            points_layout.setContentsMargins(0, 0, 0, 0)
            points_layout.setSpacing(3)
            
            for point in step["points"]:
                point_label = QLabel(f"<span style='color: #0694a2; font-weight: bold;'>•</span> {point}")
                point_label.setStyleSheet("""
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 15px;
                    color: #4a5568;
                    padding: 3px 0;
                """)
                point_label.setWordWrap(True)
                points_layout.addWidget(point_label)
            
            left_content.addWidget(step_header)
            left_content.addWidget(desc_label)
            left_content.addWidget(points_widget)
            left_content.addStretch()
            
            step_layout.addLayout(left_content, 2)
            
            # Right image area
            if step["image"]:
                image_label = QLabel()
                image_path = os.path.join(cam_assets_dir, step["image"])
                
                if os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        # Scale image to fit nicely
                        scaled_pixmap = pixmap.scaled(250, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        image_label.setPixmap(scaled_pixmap)
                        image_label.setStyleSheet("""
                            border: 2px solid #e2e8f0;
                            border-radius: 8px;
                            padding: 5px;
                            background: #f7fafc;
                        """)
                        image_label.setAlignment(Qt.AlignCenter)
                        step_layout.addWidget(image_label, 1)
                
            content_layout.addWidget(step_frame)
        
        # Troubleshooting section
        trouble_frame = QFrame()
        trouble_frame.setStyleSheet("""
            QFrame {
                background: #fef2f2;
                border: 1px solid #fca5a5;
                border-radius: 12px;
                padding: 15px;
                margin: 10px 0;
            }
        """)
        
        trouble_layout = QVBoxLayout(trouble_frame)
        trouble_title = QLabel("🛠️ Quick Troubleshooting")
        trouble_title.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 16px;
            font-weight: 700;
            color: #b91c1c;
            margin-bottom: 6px;
        """)
        
        trouble_points = [
            "Camera won't power on: Check power connection, try different outlet",
            "Can't find camera: Restart camera (unplug 10 seconds), ensure same WiFi network",
            "WiFi won't connect: Verify password, use 2.4GHz network, move closer to router",
            "App issues: Restart app, check internet, update to latest version"
        ]
        
        trouble_layout.addWidget(trouble_title)
        for point in trouble_points:
            point_label = QLabel(f"• {point}")
            point_label.setStyleSheet("""
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #b91c1c;
                padding: 2px 0;
            """)
            point_label.setWordWrap(True)
            trouble_layout.addWidget(point_label)
        
        content_layout.addWidget(trouble_frame)
        
        content_scroll.setWidget(content_widget)
        main_layout.addWidget(content_scroll)
        
        # Modern footer with close button
        footer_frame = QFrame()
        footer_frame.setFixedHeight(70)  # Smaller footer
        footer_frame.setStyleSheet("""
            QFrame {
                background: white;
                border-top: 1px solid #e2e8f0;
            }
        """)
        
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(20, 15, 20, 15)
        footer_layout.addStretch()
        
        close_btn = QPushButton("✕ Close Guide")
        close_btn.setFixedSize(150, 40)  # Smaller button
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #4b5563, stop: 1 #0694a2);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0f766e, stop: 1 #111827);
            }
        """)
        close_btn.clicked.connect(lambda: self.close_guide_with_guidance(dialog))
        
        footer_layout.addWidget(close_btn)
        main_layout.addWidget(footer_frame)
        
        # Show dialog
        dialog.exec()

    def close_guide_with_guidance(self, dialog):
        """Close the guide and show next steps guidance"""
        dialog.accept()  # Close the camera setup guide first
        
        # Show guidance dialog
        guidance_dialog = QDialog(self)
        guidance_dialog.setWindowTitle("Next Steps")
        guidance_dialog.setFixedSize(450, 300)
        guidance_dialog.setModal(True)
        
        # Create layout
        layout = QVBoxLayout(guidance_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icon and title
        title_layout = QHBoxLayout()
        
        # Icon label
        icon_label = QLabel("🎯")
        icon_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Ready to Set Up Your Cameras!")
        title_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0694a2;
            margin-left: 10px;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Guidance text
        guidance_text = QLabel(
            "Now you're ready for the next step:<br><br>"
            "👉 <b>Click the \"🎥 Set Up Your Cameras\" button</b> below to start adding your cameras to Frigate.<br><br>"
            "This will open the camera configuration tool where you can discover and configure your Amcrest cameras."
        )
        guidance_text.setTextFormat(Qt.RichText)  # Enable HTML rendering
        guidance_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: #2d3748;
            line-height: 1.5;
            padding: 15px;
            background: #f7fafc;
            border-radius: 8px;
            border-left: 4px solid #0694a2;
        """)
        guidance_text.setWordWrap(True)
        layout.addWidget(guidance_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Highlight button
        highlight_btn = QPushButton("💡 Show Me the Button")
        highlight_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0891b2, stop: 1 #164e63);
            }
        """)
        highlight_btn.clicked.connect(lambda: self.highlight_setup_button(guidance_dialog))
        
        # Got it button
        got_it_btn = QPushButton("Got It!")
        got_it_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #2d3748;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #cbd5e0;
            }
        """)
        got_it_btn.clicked.connect(guidance_dialog.accept)
        
        button_layout.addWidget(highlight_btn)
        button_layout.addStretch()
        button_layout.addWidget(got_it_btn)
        
        layout.addLayout(button_layout)
        
        # Show guidance dialog
        guidance_dialog.exec()

    def highlight_setup_button(self, guidance_dialog):
        """Highlight the setup cameras button and close guidance"""
        guidance_dialog.accept()  # Close guidance dialog
        
        # Add temporary highlight animation to the setup button
        if hasattr(self, 'setup_cameras_btn'):
            # Store original stylesheet
            original_style = self.setup_cameras_btn.styleSheet()
            
            # Apply highlight style
            highlight_style = """
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #c084fc, stop: 1 #a855f7);
                    color: white;
                    border: 3px solid #c084fc;
                    border-radius: 8px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 16px;
                    font-weight: 700;
                    text-align: center;
                    padding: 8px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ddd6fe, stop: 1 #8b5cf6);
                }
            """
            
            self.setup_cameras_btn.setStyleSheet(highlight_style)
            
            # Scroll to the button to make sure it's visible
            if hasattr(self, 'scroll_area'):
                self.setup_cameras_btn.ensurePolished()
                # Force update
                self.setup_cameras_btn.update()
            
            # Reset to original style after 5 seconds
            QTimer.singleShot(5000, lambda: self.setup_cameras_btn.setStyleSheet(original_style))

    def launch_simple_gui(self):
        """Launch the monitoring GUI - this could open Frigate web UI or monitoring interface"""
        try:
            # Check if Frigate is running and web interface is available
            import webbrowser
            
            # Try to import requests, fallback if not available
            try:
                import requests
                REQUESTS_AVAILABLE = True
            except ImportError:
                REQUESTS_AVAILABLE = False
            
            # Try to access Frigate web interface (usually on port 5000)
            frigate_url = "http://localhost:5000"
            
            if REQUESTS_AVAILABLE:
                try:
                    # Quick check if Frigate web interface is accessible
                    response = requests.get(frigate_url, timeout=3)
                    if response.status_code == 200:
                        # Open Frigate web interface
                        webbrowser.open(frigate_url)
                        return
                except requests.exceptions.RequestException:
                    pass
            
            # If Frigate web interface is not available, show message
            QMessageBox.information(
                self, 'Monitor Cameras',
                'To monitor your cameras, please ensure Frigate is running first.\n\n'
                'You can start Frigate using the "Start Frigate" button, '
                'then access the monitoring interface at:\nhttp://localhost:5000'
            )
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Monitor',
                f'Could not open the monitoring interface:\n{str(e)}'
            )
    
    def view_current_config(self):
        """Show current Frigate configuration in a dialog"""
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_content = f.read()
                
                dialog = QDialog(self)
                dialog.setWindowTitle("Current Frigate Configuration")
                dialog.setModal(True)
                dialog.resize(700, 500)
                
                layout = QVBoxLayout(dialog)
                
                text_edit = QTextEdit()
                text_edit.setPlainText(config_content)
                text_edit.setReadOnly(True)
                text_edit.setFont(QFont("Consolas", 10))
                layout.addWidget(text_edit)
                
                button_layout = QHBoxLayout()
                
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                button_layout.addStretch()
                button_layout.addWidget(close_btn)
                
                layout.addLayout(button_layout)
                
                dialog.exec_()
                
            except Exception as e:
                QMessageBox.critical(
                    self, 'Error Reading Configuration',
                    f'Could not read configuration file:\n{str(e)}'
                )
        else:
            QMessageBox.information(
                self, 'No Configuration',
                'No Frigate configuration file found. Use the camera setup wizard to create one.'
            )
    
    def apply_camera_configs(self, cameras):
        """Apply camera configurations to Frigate config"""
        try:
            # Generate Frigate configuration YAML
            config_yaml = self.generate_frigate_config(cameras)
            
            # Save to config file
            config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                f.write(config_yaml)
            
            QMessageBox.information(
                self, 'Configuration Applied',
                f'Camera configuration has been saved!\n\n'
                f'Configured {len(cameras)} camera(s).\n'
                f'You can now start Frigate to begin monitoring.'
            )
            
            # Refresh status
            self.update_preconfigured_status()
            
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Applying Configuration',
                f'Could not apply camera configuration:\n{str(e)}'
            )
    
    def generate_frigate_config(self, cameras):
        """Generate Frigate configuration YAML from camera list"""
        # Get unique objects from all cameras
        all_objects = set()
        for camera in cameras:
            all_objects.update(camera.get('objects', ['person']))
        
        config = f"""# MemryX + Frigate Configuration
# Generated automatically by PreConfigured Box setup

# MemryX detector configuration
detectors:
  memx0:
    type: memryx
    device: PCIe:0
    
# Object tracking configuration
objects:
  track:
"""
        
        for obj in sorted(all_objects):
            config += f"    - {obj}\n"
        
        config += """
# Recording configuration
record:
  enabled: true
  retain:
    days: 7
    mode: active_objects
  events:
    retain:
      default: 30
      
# Snapshots configuration
snapshots:
  enabled: true
  clean_copy: true
  retain:
    default: 30

# Camera configurations
cameras:
"""
        
        for i, camera in enumerate(cameras):
            camera_name = camera.get('name', f'camera_{i+1}').replace(' ', '_').lower()
            username = camera.get('username', '')
            password = camera.get('password', '')
            ip_address = camera.get('ip_address', '')
            port = camera.get('port', '554')
            stream_path = camera.get('stream_path', '/stream1')
            
            # Construct RTSP URL
            if username and password:
                rtsp_url = f"rtsp://{username}:{password}@{ip_address}:{port}{stream_path}"
            else:
                rtsp_url = f"rtsp://{ip_address}:{port}{stream_path}"
            
            config += f"""  {camera_name}:
    ffmpeg:
      inputs:
        - path: {rtsp_url}
          roles:
            - detect
            - record
    detect:
      width: 1920
      height: 1080
      fps: 5
    objects:
      track:
"""
            
            camera_objects = camera.get('objects', ['person'])
            for obj in camera_objects:
                config += f"        - {obj}\n"
        
        return config

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()
        modifiers = event.modifiers()
        
        # F11 for fullscreen toggle
        if key == Qt.Key_F11:
            self.toggle_fullscreen()
            event.accept()
        # F5 for status refresh
        elif key == Qt.Key_F5:
            self.check_system_status()
            event.accept()
        # F1 for documentation
        elif key == Qt.Key_F1:
            self.open_frigate_documentation()
            event.accept()
        # F2 for MemryX documentation
        elif key == Qt.Key_F2:
            self.open_memryx_documentation()
            event.accept()
        # ESC to exit fullscreen
        elif key == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
            screen = QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self.statusBar().showMessage('Maximized mode - F11: Fullscreen | F5: Refresh | Ctrl+W: Windowed | Ctrl+?: Shortcuts')
            event.accept()
        
        # Ctrl shortcuts
        elif modifiers == Qt.ControlModifier:
            if key == Qt.Key_Q:
                self.close_application()
                event.accept()
            elif key == Qt.Key_W:
                self.set_windowed_mode()
                event.accept()
            elif key == Qt.Key_M:
                self.maximize_window()
                event.accept()
            elif key == Qt.Key_N:
                # Removed new configuration - use config GUI instead
                event.accept()
            elif key == Qt.Key_O:
                self.open_config()
                event.accept()
            elif key == Qt.Key_S:
                self.save_configuration()
                event.accept()
            elif key == Qt.Key_L:
                self.clear_progress_logs()
                event.accept()
            elif key == Qt.Key_Question:  # Ctrl+?
                self.show_shortcuts()
                event.accept()
            elif key == Qt.Key_1:
                self.main_tab_widget.setCurrentIndex(0)  # PreConfigured Box
                event.accept()
            elif key == Qt.Key_2:
                self.main_tab_widget.setCurrentIndex(1)  # Manual Setup
                event.accept()
            elif key == Qt.Key_3:
                self.main_tab_widget.setCurrentIndex(2)  # Advanced Settings
                event.accept()
            else:
                super().keyPressEvent(event)
        
        # Ctrl+Shift shortcuts
        elif modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            if key == Qt.Key_S:
                self.docker_action('start')
                event.accept()
            elif key == Qt.Key_T:
                self.docker_action('stop')
                event.accept()
            elif key == Qt.Key_R:
                self.docker_action('restart')
                event.accept()
            elif key == Qt.Key_1:
                self.go_to_advanced_config()
                event.accept()
            elif key == Qt.Key_2:
                self.go_to_advanced_docker()
                event.accept()
            elif key == Qt.Key_3:
                self.go_to_advanced_logs()
                event.accept()
            else:
                super().keyPressEvent(event)
        
        # Ctrl+Alt shortcuts
        elif modifiers == (Qt.ControlModifier | Qt.AltModifier):
            if key == Qt.Key_T:
                self.open_terminal()
                event.accept()
            else:
                super().keyPressEvent(event)
        
        else:
            super().keyPressEvent(event)

    def create_header(self, layout):
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 10px;
                border: 1px solid #dee2e6;
                margin: 5px;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Logos
        memryx_logo_path = os.path.join(self.script_dir, "assets", "memryx.png")
        if os.path.exists(memryx_logo_path):
            memryx_logo = QLabel()
            memryx_logo.setPixmap(QPixmap(memryx_logo_path).scaledToHeight(60, Qt.SmoothTransformation))
            header_layout.addWidget(memryx_logo)
        
        # Title with improved professional formatting
        title = QLabel("MemryX + Frigate Control Center")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #2d3748; 
            margin: 10px;
            padding: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(74, 144, 164, 0.1), stop:1 rgba(74, 144, 164, 0.05));
            border-radius: 8px;
        """)
        header_layout.addWidget(title, 1)
        
        frigate_logo_path = os.path.join(self.script_dir, "assets", "frigate.png")
        if os.path.exists(frigate_logo_path):
            frigate_logo = QLabel()
            frigate_logo.setPixmap(QPixmap(frigate_logo_path).scaledToHeight(60, Qt.SmoothTransformation))
            header_layout.addWidget(frigate_logo)
        
        layout.addWidget(header_frame)
    
    def create_overview_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        

        
        # Current System Status section
        status_group = QGroupBox("📊 Current System Status")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(12)
        
        # Create separate status labels for Overview tab
        self.frigate_status = QLabel("🔄 Initializing...")
        self.frigate_status.setProperty("status", True)
        self.docker_status = QLabel("🔄 Initializing...")
        self.docker_status.setProperty("status", True)
        self.config_status = QLabel("🔄 Initializing...")
        self.config_status.setProperty("status", True)
        
        status_layout.addWidget(QLabel("Frigate Container:"), 0, 0)
        status_layout.addWidget(self.frigate_status, 0, 1)
        status_layout.addWidget(QLabel("Docker Service:"), 1, 0)
        status_layout.addWidget(self.docker_status, 1, 1)
        status_layout.addWidget(QLabel("Configuration:"), 2, 0)
        status_layout.addWidget(self.config_status, 2, 1)
        
        # Add MemryX status
        self.memryx_overview_status = QLabel("🔄 Checking...")
        status_layout.addWidget(QLabel("MemryX Hardware:"), 3, 0)
        status_layout.addWidget(self.memryx_overview_status, 3, 1)
        
        layout.addWidget(status_group)
        
        # Quick Actions section (for experienced users)
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_layout = QGridLayout(actions_group)
        actions_layout.setSpacing(12)
        
        open_ui_btn = QPushButton("🌐 Open Frigate Web UI")
        open_ui_btn.clicked.connect(self.open_web_ui)
        open_ui_btn.setMinimumHeight(40)
        open_ui_btn.setToolTip("Open Frigate Web UI (only works when Frigate is running)")
        
        config_btn = QPushButton("⚙️ Open Configuration GUI")
        config_btn.clicked.connect(self.open_config)
        config_btn.setMinimumHeight(40)
        config_btn.setToolTip("Open the configuration editor")
        
        start_btn = QPushButton("▶️ Start Frigate")
        start_btn.clicked.connect(lambda: self.docker_action('start'))
        start_btn.setMinimumHeight(40)
        start_btn.setToolTip("Start Frigate container")
        
        stop_btn = QPushButton("⏹️ Stop Frigate")
        stop_btn.clicked.connect(lambda: self.docker_action('stop'))
        stop_btn.setMinimumHeight(40)
        stop_btn.setToolTip("Stop Frigate container")
        
        actions_layout.addWidget(config_btn, 0, 0)
        actions_layout.addWidget(open_ui_btn, 0, 1)
        actions_layout.addWidget(start_btn, 1, 0)
        actions_layout.addWidget(stop_btn, 1, 1)
        
        layout.addWidget(actions_group)
        
        # System Information section (collapsible for space)
        info_group = QGroupBox("🖥️ System Information")
        info_layout = QFormLayout(info_group)
        info_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        info_layout.setSpacing(8)
        
        info_layout.addRow("MemryX Devices:", QLabel("🔄 Checking..."))
        info_layout.addRow("Installation Path:", QLabel(self.script_dir))
        info_layout.addRow("Config Path:", QLabel(os.path.join(self.script_dir, "frigate", "config")))
        
        # Add more system details
        import platform
        
        info_layout.addRow("Operating System:", QLabel(f"{platform.system()} {platform.release()}"))
        info_layout.addRow("Architecture:", QLabel(platform.machine()))
        info_layout.addRow("Python Version:", QLabel(platform.python_version()))
        
        # System resources (if psutil is available)
        if PSUTIL_AVAILABLE:
            info_layout.addRow("CPU Cores:", QLabel(str(psutil.cpu_count())))
            memory_gb = psutil.virtual_memory().total / (1024**3)
            info_layout.addRow("Total Memory:", QLabel(f"{memory_gb:.1f} GB"))
            
            # Disk space for project directory
            disk_usage = psutil.disk_usage(self.script_dir)
            free_gb = disk_usage.free / (1024**3)
            total_gb = disk_usage.total / (1024**3)
            info_layout.addRow("Disk Space (Free/Total):", QLabel(f"{free_gb:.1f} GB / {total_gb:.1f} GB"))
        
        layout.addWidget(info_group)
        
        # Live System Monitor (if psutil is available)
        if PSUTIL_AVAILABLE:
            monitor_group = QGroupBox("📈 Live System Monitor")
            monitor_layout = QFormLayout(monitor_group)
            monitor_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            monitor_layout.setSpacing(8)
            
            self.cpu_usage_label = QLabel("Calculating...")
            self.memory_usage_label = QLabel("Calculating...")
            self.disk_usage_label = QLabel("Calculating...")
            
            monitor_layout.addRow("CPU Usage:", self.cpu_usage_label)
            monitor_layout.addRow("Memory Usage:", self.memory_usage_label)
            monitor_layout.addRow("Disk Usage:", self.disk_usage_label)
            
            layout.addWidget(monitor_group)
        
        layout.addStretch()
        
        return widget
    

    
    def create_prerequisites_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)  # Slightly reduced margins
        layout.setSpacing(8)  # Reduced spacing to be more compact
        
        # Header description - made more compact
        header_label = QLabel(
            "🔧 This tab handles system-level prerequisites required before setting up Frigate. "
            "Complete these steps first before proceeding to Frigate Setup."
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("""
            QLabel {
                background: #e8f4f0;
                color: #2d5a4a;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(header_label)
        
        # Step 1: System Prerequisites Check
        prereq_step_group = QGroupBox("Step 1: System Prerequisites Check")
        prereq_step_layout = QVBoxLayout(prereq_step_group)
        prereq_step_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #b3d9d0;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 5px;
                padding-top: 10px;
                padding-bottom: 8px;
                min-height: 160px;
                max-height: 180px;
            }
            QGroupBox::title {
                color: #5a9b8a;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                font-size: 12px;
            }
        """)
        
        # Prerequisites grid with status and install buttons
        prereq_grid = QGridLayout()
        prereq_grid.setSpacing(6)  # Better spacing
        
        # Git row
        prereq_grid.addWidget(QLabel("Git:"), 0, 0)
        self.prereq_git_check = QLabel("🔄 Verifying...")
        self.prereq_git_check.setProperty("status", True)
        prereq_grid.addWidget(self.prereq_git_check, 0, 1)
        
        self.install_git_btn = QPushButton("📦 Install Git")
        self.install_git_btn.clicked.connect(lambda: self.install_system_prereq('git'))
        self.install_git_btn.setMaximumWidth(110)  # Slightly wider
        self.install_git_btn.setMinimumHeight(30)  # Better height
        self.install_git_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #dc3545, stop:1 #c82333);
                color: white;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #e3444e, stop:1 #dc3545);
            }
        """)
        self.install_git_btn.setVisible(False)  # Initially hidden
        prereq_grid.addWidget(self.install_git_btn, 0, 2)
        
        # Build Tools row
        prereq_grid.addWidget(QLabel("Build Tools:"), 1, 0)
        self.prereq_build_check = QLabel("🔄 Verifying...")
        self.prereq_build_check.setProperty("status", True)
        self.prereq_build_check.setToolTip("Build Tools include GCC, Make, and other compilation tools needed for DKMS and package building")
        prereq_grid.addWidget(self.prereq_build_check, 1, 1)
        
        self.install_build_btn = QPushButton("🔧 Install Build Tools")
        self.install_build_btn.clicked.connect(lambda: self.install_system_prereq('build-tools'))
        self.install_build_btn.setMaximumWidth(110)  # Slightly wider
        self.install_build_btn.setMinimumHeight(30)  # Better height
        self.install_build_btn.setToolTip("Installs build-essential package (GCC, Make, G++, etc.) required for compiling software")
        self.install_build_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #28a745, stop:1 #1e7e34);
                color: white;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #34ce57, stop:1 #28a745);
            }
        """)
        self.install_build_btn.setVisible(False)  # Initially hidden
        prereq_grid.addWidget(self.install_build_btn, 1, 2)
        
        prereq_step_layout.addLayout(prereq_grid)
        
        # Add explanation for Build Tools - better sized
        build_tools_info = QLabel(
            "💡 Includes GCC, Make, and tools for MemryX driver compilation and Docker builds."
        )
        build_tools_info.setWordWrap(True)
        build_tools_info.setStyleSheet("""
            QLabel {
                background: #f8f9fa;
                color: #495057;
                padding: 6px;
                border-radius: 4px;
                font-size: 10px;
                border-left: 3px solid #28a745;
                margin: 4px 0px;
            }
        """)
        prereq_step_layout.addWidget(build_tools_info)
        
        check_prereq_btn = QPushButton("🔍 Check System Prerequisites")
        check_prereq_btn.clicked.connect(self.check_system_prerequisites)
        check_prereq_btn.setMinimumHeight(45)  # Better height
        prereq_step_layout.addWidget(check_prereq_btn)
        
        layout.addWidget(prereq_step_group)
        
        # Step 2: Docker Setup
        docker_step_group = QGroupBox("Step 2: Docker Installation & Setup")
        docker_step_layout = QVBoxLayout(docker_step_group)
        docker_step_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #c8d4e3;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 8px;
                padding-top: 10px;
                padding-bottom: 8px;
                min-height: 140px;
                max-height: 160px;
            }
            QGroupBox::title {
                color: #7a8fab;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                font-size: 12px;
            }
        """)
        
        # Docker status section
        docker_status_layout = QHBoxLayout()
        
        docker_status_title = QLabel("Docker Status:")
        docker_status_title.setFont(QFont("Arial", 10, QFont.Bold))  # Better font size
        docker_status_layout.addWidget(docker_status_title)
        
        self.prereq_docker_status = QLabel("🔄 Checking Docker status...")
        self.prereq_docker_status.setProperty("status", "repo")
        self.prereq_docker_status.setWordWrap(True)
        docker_status_layout.addWidget(self.prereq_docker_status, 1)
        
        refresh_docker_btn = QPushButton("🔄 Refresh")
        refresh_docker_btn.clicked.connect(self.check_docker_prereq_status)
        refresh_docker_btn.setMaximumWidth(125)  # Wider to show full text
        docker_status_layout.addWidget(refresh_docker_btn)
        
        docker_step_layout.addLayout(docker_status_layout)
        
        # Docker installation button (only shown when needed)
        self.install_docker_prereq_btn = QPushButton("🐳 Install Docker from Scratch")
        self.install_docker_prereq_btn.clicked.connect(self.install_docker_prereq)
        self.install_docker_prereq_btn.setMinimumHeight(38)  # Better height
        self.install_docker_prereq_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2563eb, stop:1 #1d4ed8);
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0694a2, stop:1 #2563eb);
            }
            QPushButton:pressed {
                background: #0f766e;
            }
        """)
        self.install_docker_prereq_btn.setVisible(True)
        docker_step_layout.addWidget(self.install_docker_prereq_btn)
        
        # Docker setup guidance
        self.docker_prereq_guidance = QLabel()
        self.docker_prereq_guidance.setWordWrap(True)
        self.docker_prereq_guidance.setStyleSheet("color: #6c757d; font-size: 10px; padding: 4px; line-height: 1.3;")  # Better sizing
        docker_step_layout.addWidget(self.docker_prereq_guidance)
        
        layout.addWidget(docker_step_group)
        
        # Step 3: MemryX Driver Setup
        memryx_step_group = QGroupBox("Step 3: MemryX Driver Installation & Setup")
        memryx_step_layout = QVBoxLayout(memryx_step_group)
        memryx_step_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #d6c8e3;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 8px;
                padding-top: 10px;
                padding-bottom: 8px;
                min-height: 160px;
                max-height: 180px;
            }
            QGroupBox::title {
                color: #8a7fab;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                font-size: 12px;
            }
        """)
        
        # MemryX status section
        memryx_status_layout = QHBoxLayout()
        
        memryx_status_title = QLabel("MemryX Status:")
        memryx_status_title.setFont(QFont("Arial", 10, QFont.Bold))  # Better font size
        memryx_status_layout.addWidget(memryx_status_title)
        
        self.prereq_memryx_status = QLabel("🔄 Checking MemryX status...")
        self.prereq_memryx_status.setProperty("status", "repo")
        self.prereq_memryx_status.setWordWrap(True)
        memryx_status_layout.addWidget(self.prereq_memryx_status, 1)
        
        refresh_memryx_btn = QPushButton("🔄 Refresh")
        refresh_memryx_btn.clicked.connect(self.check_memryx_prereq_status)
        refresh_memryx_btn.setMaximumWidth(125)  # Wider to show full text
        memryx_status_layout.addWidget(refresh_memryx_btn)
        
        memryx_step_layout.addLayout(memryx_status_layout)
        
        # MemryX installation button (only shown when needed)
        self.install_memryx_prereq_btn = QPushButton("🧠 Install MemryX Drivers & Runtime")
        self.install_memryx_prereq_btn.clicked.connect(self.install_memryx_prereq)
        self.install_memryx_prereq_btn.setMinimumHeight(38)  # Better height
        self.install_memryx_prereq_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #7c3aed, stop:1 #6d28d9);
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #8b5cf6, stop:1 #7c3aed);
            }
            QPushButton:pressed {
                background: #5b21b6;
            }
        """)
        self.install_memryx_prereq_btn.setVisible(True)
        memryx_step_layout.addWidget(self.install_memryx_prereq_btn)
        
        # System restart button (shown when MemryX drivers need restart)
        self.restart_system_btn = QPushButton("🔄 Restart System Now")
        self.restart_system_btn.clicked.connect(self.restart_system)
        self.restart_system_btn.setMinimumHeight(38)  # Better height
        self.restart_system_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #dc3545, stop:1 #c82333);
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #e85d75, stop:1 #dc3545);
            }
            QPushButton:pressed {
                background: #bd2130;
            }
        """)
        self.restart_system_btn.setVisible(False)  # Hidden by default
        memryx_step_layout.addWidget(self.restart_system_btn)
        
        # MemryX setup guidance
        self.memryx_prereq_guidance = QLabel()
        self.memryx_prereq_guidance.setWordWrap(True)
        self.memryx_prereq_guidance.setStyleSheet("color: #6c757d; font-size: 10px; padding: 4px; line-height: 1.3;")  # Better sizing
        memryx_step_layout.addWidget(self.memryx_prereq_guidance)
        
        layout.addWidget(memryx_step_group)
        
        # Progress area - optimized size for better balance
        progress_group = QGroupBox("Installation Progress")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(10, 10, 10, 10)
        
        self.prereq_progress = QTextEdit()
        self.prereq_progress.setPlainText("Ready to begin prerequisites setup...")
        # MemryX setup guidance
        self.memryx_prereq_guidance = QLabel()
        self.memryx_prereq_guidance.setWordWrap(True)
        self.memryx_prereq_guidance.setStyleSheet("color: #6c757d; font-size: 10px; padding: 4px; line-height: 1.3;")  # Better sizing
        memryx_step_layout.addWidget(self.memryx_prereq_guidance)
        
        layout.addWidget(memryx_step_group)
        
        # Progress area - optimized size for better balance
        progress_group = QGroupBox("Installation Progress")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(10, 10, 10, 10)
        
        self.prereq_progress = QTextEdit()
        self.prereq_progress.setPlainText("Ready to begin prerequisites setup...")
        self.prereq_progress.setMinimumHeight(250)  # Slightly reduced to balance with taller step sections
        # Set a preferred size that will expand to fill available space
        self.prereq_progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Enable auto-scroll to bottom when new text is added
        self.prereq_progress.textChanged.connect(self.auto_scroll_prereq_progress)
        self.prereq_progress.setStyleSheet("""
            QTextEdit {
                background: #fafbfc;
                border: 1px solid #e5e8eb;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #2d3748;
                padding: 12px;
                line-height: 1.3;
            }
        """)
        progress_layout.addWidget(self.prereq_progress)
        
        # Give the progress group a size policy to expand
        progress_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(progress_group, 1)  # Stretch factor of 1 to take remaining space
        
        # Initial checks
        self.check_system_prerequisites()
        self.check_docker_prereq_status()
        self.check_memryx_prereq_status()
        
        return widget
    
    def create_setup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Header description
        header_label = QLabel(
            "⚙️ This tab handles Frigate repository setup. Ensure you have completed the Prerequisites "
            "tab first (Docker, MemryX, and system tools must be installed). The Python environment "
            "is already configured by the launcher script."
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("""
            QLabel {
                background: #e8f4f0;
                color: #2d5a4a;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(header_label)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Repository management section
        repo_widget = QWidget()
        repo_widget.setMinimumHeight(150)  # Minimum height to ensure readability
        repo_widget.setMaximumHeight(300)  # Increased max height to accommodate guidance text
        repo_layout = QVBoxLayout(repo_widget)
        repo_layout.setContentsMargins(4, 4, 4, 4)
        repo_layout.setSpacing(6)  # Reduced spacing
        
        step1_group = QGroupBox("Step 1: Frigate Repository Management")
        step1_layout = QVBoxLayout(step1_group)
        step1_layout.setSpacing(6)  # Slightly increased for guidance text readability
        step1_layout.setContentsMargins(8, 8, 8, 8)  # Keep compact margins
        step1_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #c8d4e3;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 6px;
                padding-top: 8px;
            }
            QGroupBox::title {
                color: #7a8fab;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                font-size: 12px;
            }
        """)
        
        # Repository status section
        repo_status_layout = QHBoxLayout()
        repo_status_layout.setSpacing(8)  # Reduced spacing
        
        repo_status_label = QLabel("Repository Status:")
        repo_status_label.setFont(QFont("Arial", 10, QFont.Bold))
        repo_status_layout.addWidget(repo_status_label)
        
        self.repo_status_label = QLabel("🔄 Checking repository status...")
        self.repo_status_label.setProperty("status", "repo")
        self.repo_status_label.setWordWrap(True)
        repo_status_layout.addWidget(self.repo_status_label, 1)
        
        refresh_status_btn = QPushButton("🔄 Refresh")
        refresh_status_btn.clicked.connect(self.check_repo_status)
        refresh_status_btn.setMaximumWidth(125)  # Wider to show full text
        repo_status_layout.addWidget(refresh_status_btn)
        
        step1_layout.addLayout(repo_status_layout)
        
        # Repository action buttons
        repo_buttons_layout = QHBoxLayout()
        repo_buttons_layout.setSpacing(6)  # Further reduced spacing between buttons
        repo_buttons_layout.setContentsMargins(0, 4, 0, 4)  # Minimal margins
        
        # Clone Frigate button
        self.clone_frigate_btn = QPushButton("📥 Clone Fresh Repository")
        self.clone_frigate_btn.clicked.connect(lambda: self.install_frigate('clone_only'))
        self.clone_frigate_btn.setMinimumHeight(35)  # Reduced height
        self.clone_frigate_btn.setToolTip(
            "Downloads a fresh copy of Frigate repository.\n"
            "• Use for first-time setup\n"
            "• Removes existing directory if present\n"
            "• Use to fix repository corruption issues"
        )
        
        # Update Frigate button
        self.update_frigate_btn = QPushButton("🔄 Update Existing Repository")
        self.update_frigate_btn.clicked.connect(lambda: self.install_frigate('update_only'))
        self.update_frigate_btn.setMinimumHeight(35)  # Reduced height
        self.update_frigate_btn.setToolTip(
            "Updates existing Frigate repository to latest version.\n"
            "• Requires valid git repository\n"
            "• Local changes will be stashed\n"
            "• Pulls latest changes from remote"
        )
        
        repo_buttons_layout.addWidget(self.clone_frigate_btn)
        repo_buttons_layout.addWidget(self.update_frigate_btn)
        step1_layout.addLayout(repo_buttons_layout)
        
        # Step 1 guidance
        step1_guidance = QLabel()
        step1_guidance.setWordWrap(True)
        step1_guidance.setStyleSheet("color: #6c757d; font-size: 10px; padding: 4px;")
        self.step2_guidance = step1_guidance  # Store reference for updates (keeping same name for compatibility)
        step1_layout.addWidget(step1_guidance)
        
        # Set size policy to adapt to content - minimum when empty, preferred when has content
        step1_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        repo_layout.addWidget(step1_group)
        splitter.addWidget(repo_widget)
        
        # Progress display - now much larger
        progress_group = QGroupBox("Frigate Setup Progress")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(6, 6, 6, 6)
        
        self.install_progress = QTextEdit()
        self.install_progress.setPlainText("Ready to begin setup process...")
        # Enable auto-scroll to bottom when new text is added
        self.install_progress.textChanged.connect(self.auto_scroll_install_progress)
        self.install_progress.setMinimumHeight(200)  # Good size for installation progress
        self.install_progress.setMaximumHeight(350)  # Prevent excessive growth
        self.install_progress.setStyleSheet(f"""
            QTextEdit {{
                background: #fafbfc;
                border: 1px solid #e5e8eb;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #2d3748;
                padding: 10px;
                line-height: 1.3;
            }}
            {self.scroll_bar_style}
        """)
        progress_layout.addWidget(self.install_progress)
        
        splitter.addWidget(progress_group)
        
        # Set splitter proportions - balanced for both scenarios
        splitter.setSizes([200, 250])  # Repository section gets more space when needed
        splitter.setStretchFactor(0, 1)  # Repository section can expand if needed
        splitter.setStretchFactor(1, 1)  # Progress section also flexible
        
        layout.addWidget(splitter)
        
        # Next Steps section
        next_steps_group = QGroupBox("🎯 Next Steps")
        next_steps_layout = QVBoxLayout(next_steps_group)
        next_steps_layout.setSpacing(10)
        
        next_steps_message = QLabel(
            "✅ <b>Frigate Setup Complete!</b><br><br>"
            "🎥 <b>Ready to configure cameras and start monitoring?</b><br>"
            "Go to the <b>PreConfigured Box</b> tab for easy camera setup and Frigate control.<br><br>"
            "⚙️ <b>Want advanced configuration control?</b><br>"
            "Use the <b>Advanced Settings</b> tab for detailed configuration editing and Docker logs monitoring."
        )
        next_steps_message.setWordWrap(True)
        next_steps_message.setStyleSheet("""
            QLabel {
                background: #e8f4f0;
                color: #2d5a4a;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
                border-left: 4px solid #48bb78;
            }
        """)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # Button to go to PreConfigured Box
        go_to_preconfigured_btn = QPushButton("📦 Go to PreConfigured Box")
        go_to_preconfigured_btn.clicked.connect(lambda: self.main_tab_widget.setCurrentIndex(0))
        go_to_preconfigured_btn.setMinimumHeight(35)
        go_to_preconfigured_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #48bb78, stop:1 #38a169);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #68d391, stop:1 #48bb78);
            }
            QPushButton:pressed {
                background: #2f855a;
            }
        """)
        
        # Button to go to Advanced Settings
        go_to_advanced_btn = QPushButton("⚙️ Go to Advanced Settings")
        go_to_advanced_btn.clicked.connect(lambda: self.main_tab_widget.setCurrentIndex(2))
        go_to_advanced_btn.setMinimumHeight(35)
        go_to_advanced_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4a90a4, stop:1 #38758a);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #5b9bb0, stop:1 #428299);
            }
            QPushButton:pressed {
                background: #2d6374;
            }
        """)
        
        buttons_layout.addWidget(go_to_preconfigured_btn)
        buttons_layout.addWidget(go_to_advanced_btn)
        
        next_steps_layout.addWidget(next_steps_message)
        next_steps_layout.addLayout(buttons_layout)
        
        layout.addWidget(next_steps_group)
        
        # Initial checks
        self.check_repo_status()
        self.check_prerequisites()
        self.update_step2_guidance()
        
        return widget
    
    def create_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Create a small header section for actions and controls
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(4, 4, 4, 4)
        
        config_group = QGroupBox("Configuration Management")
        config_group_layout = QVBoxLayout(config_group)
        
        # Configuration actions
        actions_layout = QHBoxLayout()
        
        config_gui_btn = QPushButton("🎛️ Open Configuration")
        config_gui_btn.clicked.connect(self.open_config)
        
        edit_manual_btn = QPushButton("📝 Edit Configuration File")
        edit_manual_btn.clicked.connect(self.edit_config_manual)
        
        actions_layout.addWidget(config_gui_btn)
        actions_layout.addWidget(edit_manual_btn)
        actions_layout.addStretch()
        
        config_group_layout.addLayout(actions_layout)
        header_layout.addWidget(config_group)
        
        # Configuration editor section header
        editor_header_layout = QHBoxLayout()
        preview_label = QLabel("Configuration Editor:")
        preview_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Auto-reload indicator
        auto_reload_label = QLabel("🔄 Auto-reload enabled")
        auto_reload_label.setStyleSheet("""
            QLabel {
                color: #28a745;
                font-size: 10px;
                font-weight: normal;
                padding: 2px 6px;
                background: #e8f4f0;
                border-radius: 10px;
                margin-left: 10px;
            }
        """)
        auto_reload_label.setToolTip("Configuration will automatically reload when modified externally")
        
        # Edit, Save and reload buttons in header
        self.edit_config_btn = QPushButton("✏️ Edit")
        self.edit_config_btn.clicked.connect(self.toggle_config_edit_mode)
        self.edit_config_btn.setMinimumWidth(120)
        self.edit_config_btn.setMaximumWidth(120)
        self.edit_config_btn.setMinimumHeight(35)
        self.edit_config_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fbbf24, stop:1 #f59e0b);
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fcd34d, stop:1 #fbbf24);
            }
        """)
        self.edit_config_btn.setToolTip("Switch to edit mode to modify the configuration")
        
        self.save_config_btn = QPushButton("💾 Save")
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_btn.setMinimumWidth(120)  # Set minimum width
        self.save_config_btn.setMaximumWidth(120)  # Same width as reload button
        self.save_config_btn.setMinimumHeight(35)  # Set minimum height for better appearance
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #28a745, stop:1 #1e7e34);
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #34ce57, stop:1 #28a745);
            }
        """)
        self.save_config_btn.setEnabled(False)  # Initially disabled
        self.save_config_btn.setToolTip("Save changes to configuration file")
        
        reload_config_btn = QPushButton("🔄 Reload")
        reload_config_btn.clicked.connect(self.load_config_preview)
        reload_config_btn.setMinimumWidth(120)  # Set minimum width
        reload_config_btn.setMaximumWidth(120)  # Wider to show full text
        reload_config_btn.setMinimumHeight(35)  # Set minimum height for better appearance
        reload_config_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4a90a4, stop:1 #38758a);
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #5b9bb0, stop:1 #428299);
            }
        """)
        reload_config_btn.setToolTip("Reload configuration from file (discards unsaved changes)")
        
        editor_header_layout.addWidget(preview_label)
        editor_header_layout.addWidget(auto_reload_label)
        editor_header_layout.addStretch()
        editor_header_layout.addWidget(self.edit_config_btn)
        editor_header_layout.addWidget(self.save_config_btn)
        editor_header_layout.addWidget(reload_config_btn)
        
        header_layout.addLayout(editor_header_layout)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Add header to splitter (small, fixed-ish)
        splitter.addWidget(header_widget)
        
        # Configuration editor - now takes most of the space
        self.config_preview = QTextEdit()
        self.config_preview.setPlainText("Loading configuration...")
        self.config_preview.setReadOnly(True)  # Start in read-only mode
        self.config_preview.setMinimumHeight(300)  # Good minimum height for config editing
        self.config_preview.setStyleSheet(f"""
            QTextEdit {{
                background: #fafbfc;
                border: 1px solid #cbd5e0;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                font-size: 13px;
                color: #2d3748;
                padding: 12px;
                line-height: 1.5;
            }}
            QTextEdit[readOnly="true"] {{
                background: #f8f9fa;
                color: #495057;
            }}
            {self.scroll_bar_style}
        """)
        self.config_is_read_only = True  # Track edit state
        self.load_config_preview()
        
        splitter.addWidget(self.config_preview)
        
        # Set splitter proportions - most space to editor
        splitter.setSizes([120, 700])  # Header small, editor large
        splitter.setStretchFactor(0, 0)  # Header doesn't stretch
        splitter.setStretchFactor(1, 1)  # Editor gets all extra space
        
        layout.addWidget(splitter)
        
        return widget
    
    def create_docker_manager_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)  # Reduce margins for more space
        layout.setSpacing(8)  # Reduce spacing between sections
        
        # Create a splitter to allow user to resize sections
        splitter = QSplitter(Qt.Vertical)
        
        # Docker controls section
        docker_widget = QWidget()
        docker_layout = QVBoxLayout(docker_widget)
        docker_layout.setContentsMargins(4, 4, 4, 4)
        
        docker_group = QGroupBox("Frigate Docker Container Controls")
        docker_group_layout = QVBoxLayout(docker_group)
        
        # Control buttons - organized in two rows for better UX
        controls_layout = QVBoxLayout()
        
        # Primary controls row
        primary_controls = QHBoxLayout()
        
        # Store button references as instance variables so we can disable/enable them
        self.docker_start_btn = QPushButton("▶️ Start")
        self.docker_start_btn.clicked.connect(lambda: self.docker_action('start'))
        self.docker_start_btn.setToolTip(
            "🔵 START FRIGATE\n\n"
            "• Starts existing Frigate container if it exists\n"
            "• Creates new container automatically if none exists\n"
            "• Preserves all existing configuration and data\n"
            "• Best for: Getting Frigate running (works in all situations)\n\n"
            "✅ Smart Start Behavior:\n"
            "• Container exists & stopped → Starts it\n"
            "• Container exists & running → Nothing to do\n"
            "• No container exists → Creates and starts new one\n\n"
            "⚠️ Note: Other buttons will be disabled during this operation\n"
            "✅ Stop button remains available for emergency use"
        )
        
        self.docker_stop_btn = QPushButton("⏹️ Stop")
        self.docker_stop_btn.clicked.connect(lambda: self.docker_action('stop'))
        self.docker_stop_btn.setToolTip(
            "🔴 STOP CONTAINER\n\n"
            "• Gracefully stops the running Frigate container\n"
            "• Container remains available for future restart\n"
            "• All configuration and data are preserved\n"
            "• Best for: Temporary shutdown or before making config changes\n\n"
            "✅ Emergency Stop: This button remains enabled during other operations\n"
            "• Can be used to stop container even during rebuild/restart\n"
            "• Useful for canceling long-running operations"
        )
        
        self.docker_restart_btn = QPushButton("🔄 Restart")
        self.docker_restart_btn.clicked.connect(lambda: self.docker_action('restart'))
        self.docker_restart_btn.setToolTip(
            "🔄 RESTART CONTAINER\n\n"
            "• Quick restart of the existing container\n"
            "• Stops and immediately starts the same container\n"
            "• Uses existing image and configuration\n"
            "• Best for: Applying configuration changes or fixing temporary issues\n\n"
            "❌ Will fail if: No container exists\n"
            "💡 Solution: Use 'Start' to create and start new container\n"
            "💡 Or use 'Rebuild' for complete fresh build\n\n"
            "⚠️ Note: Other buttons will be disabled during this operation\n"
            "✅ Stop button remains available for emergency use"
        )
        
        primary_controls.addWidget(self.docker_start_btn)
        primary_controls.addWidget(self.docker_stop_btn)
        primary_controls.addWidget(self.docker_restart_btn)
        
        # Secondary controls row
        secondary_controls = QHBoxLayout()
        
        self.docker_rebuild_btn = QPushButton("🔨 Rebuild")
        self.docker_rebuild_btn.clicked.connect(lambda: self.docker_action('rebuild'))
        self.docker_rebuild_btn.setToolTip(
            "🔨 COMPLETE REBUILD\n\n"
            "• Stops and removes existing container completely\n"
            "• Builds fresh Docker image from latest source\n"
            "• Creates and starts new container with current config\n"
            "• Best for: Major updates, troubleshooting, or first-time setup\n\n"
            "⚠️ WARNING: This is a destructive operation!\n"
            "• Takes several minutes to complete\n"
            "• Will interrupt any ongoing recordings\n"
            "• Requires confirmation dialog\n"
            "• Other buttons will be disabled during this operation\n"
            "• Stop button remains available for emergency use"
        )
        self.docker_rebuild_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fde68a, stop:1 #fcd34d);
                color: #92400e;
                border: 1px solid #f59e0b;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fef3c7, stop:1 #fde68a);
                border: 1px solid #d97706;
            }
            QPushButton:pressed {
                background: #f59e0b;
                color: white;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                color: #9ca3af;
                border: 1px solid #d1d5db;
            }
        """)
        
        self.docker_remove_btn = QPushButton("🗑️ Remove")
        self.docker_remove_btn.clicked.connect(lambda: self.docker_action('remove'))
        self.docker_remove_btn.setToolTip(
            "🗑️ REMOVE CONTAINER\n\n"
            "• Stops and completely removes the Frigate container\n"
            "• Container must be recreated with Rebuild to use again\n"
            "• All container state is lost (config files remain)\n"
            "• Best for: Complete cleanup or major troubleshooting\n\n"
            "⚠️ WARNING: This is a destructive operation!\n"
            "• Container cannot be recovered once removed\n"
            "• Requires confirmation dialog\n"
            "• Other buttons will be disabled during this operation\n"
            "• Stop button remains available for emergency use"
        )
        self.docker_remove_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fecaca, stop:1 #fca5a5);
                color: #991b1b;
                border: 1px solid #dc2626;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fee2e2, stop:1 #fecaca);
                border: 1px solid #b91c1c;
            }
            QPushButton:pressed {
                background: #dc2626;
                color: white;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                color: #9ca3af;
                border: 1px solid #d1d5db;
            }
        """)
        
        self.docker_open_ui_btn = QPushButton("🌐 Open Frigate Web UI")
        self.docker_open_ui_btn.clicked.connect(self.open_frigate_web_ui)
        self.docker_open_ui_btn.setToolTip(
            "🌐 OPEN WEB INTERFACE\n\n"
            "• Opens Frigate's web interface in your default browser\n"
            "• Access live camera feeds, recordings, and settings\n"
            "• Default URL: http://localhost:5000\n"
            "• Best for: Monitoring cameras and viewing recordings\n\n"
            "📋 Note: This button stays enabled during operations\n"
            "• You can open the web UI anytime to check status"
        )
        self.docker_open_ui_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #bfdbfe, stop:1 #93c5fd);
                color: #0f766e;
                border: 1px solid #0694a2;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #dbeafe, stop:1 #bfdbfe);
                border: 1px solid #2563eb;
            }
            QPushButton:pressed {
                background: #0694a2;
                color: white;
            }
            QPushButton:disabled {
                background: #f3f4f6;
                color: #9ca3af;
                border: 1px solid #d1d5db;
            }
        """)
        
        secondary_controls.addWidget(self.docker_rebuild_btn)
        secondary_controls.addWidget(self.docker_remove_btn)
        secondary_controls.addWidget(self.docker_open_ui_btn)
        secondary_controls.addStretch()  # Push buttons to the left
        
        controls_layout.addLayout(primary_controls)
        controls_layout.addLayout(secondary_controls)
        
        docker_group_layout.addLayout(controls_layout)
        # Operation status indicator
        self.operation_status_label = QLabel("🟢 Ready - All operations available")
        self.operation_status_label.setStyleSheet("""
            QLabel {
                background: #e8f4f0;
                color: #2d5a4a;
                padding: 8px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                margin: 4px 0px;
            }
        """)
        docker_group_layout.addWidget(self.operation_status_label)
        docker_layout.addWidget(docker_group)
        
        # Container status monitoring
        monitor_group = QGroupBox("Container Status")
        monitor_layout = QFormLayout(monitor_group)
        
        # Create separate status label for Docker Manager tab
        self.docker_manager_frigate_status = QLabel("🔄 Initializing...")
        self.docker_manager_frigate_status.setProperty("status", True)
        monitor_layout.addRow("Frigate Container:", self.docker_manager_frigate_status)
        
        docker_layout.addWidget(monitor_group)
        
        splitter.addWidget(docker_widget)
        
        # Progress section - now much larger and resizable
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(4, 4, 4, 4)
        
        # Progress display with header
        progress_header_layout = QHBoxLayout()
        progress_label = QLabel("Docker Operations Progress:")
        progress_label.setFont(QFont("Arial", 11, QFont.Bold))
        
        # Clear progress button
        clear_progress_btn = QPushButton("🗑️ Clear")
        clear_progress_btn.clicked.connect(lambda: self.docker_progress.clear())
        clear_progress_btn.setMaximumWidth(120)  # Wider to show full text
        clear_progress_btn.setToolTip("Clear the progress display")
        
        progress_header_layout.addWidget(progress_label)
        progress_header_layout.addStretch()
        progress_header_layout.addWidget(clear_progress_btn)
        
        progress_layout.addLayout(progress_header_layout)
        
        # Progress display - now takes much more space
        self.docker_progress = QTextEdit()
        self.docker_progress.setPlainText("🐳 Docker Manager Console Ready\n\nSelect a container operation above to view detailed progress logs and real-time status updates.\n\nSupported Operations:\n• Start/Stop/Restart: Standard container lifecycle management\n• Rebuild: Complete container regeneration with latest image\n• Remove: Complete container cleanup and removal")
        # Enable auto-scroll to bottom when new text is added
        self.docker_progress.textChanged.connect(self.auto_scroll_docker_progress)
        self.docker_progress.setMinimumHeight(250)  # Good size for docker logs
        self.docker_progress.setStyleSheet(f"""
            QTextEdit {{
                background: #fafbfc;
                border: 1px solid #e5e8eb;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                font-size: 12px;
                color: #2d3748;
                padding: 12px;
                line-height: 1.4;
            }}
            {self.scroll_bar_style}
        """)
        progress_layout.addWidget(self.docker_progress)
        
        splitter.addWidget(progress_widget)
        
        # Set initial splitter proportions - give more space to progress
        splitter.setSizes([250, 600])  # Controls section smaller, progress section much larger
        splitter.setStretchFactor(0, 0)  # Controls section doesn't stretch
        splitter.setStretchFactor(1, 1)  # Progress section gets all extra space
        
        layout.addWidget(splitter)
        
        return widget
    
    def create_logs_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Simple clear button for convenience
        clear_btn = QPushButton("🗑️ Clear Display")
        clear_btn.clicked.connect(lambda: self.logs_display.clear())
        clear_btn.setMaximumWidth(160)
        clear_btn.setToolTip("Clear the current log display (logs will reload automatically)")
        layout.addWidget(clear_btn)
        
        # Logs display - takes up most of the space
        self.logs_display = QTextEdit()
        self.logs_display.setFont(QFont("Consolas", 10))
        self.logs_display.setMinimumHeight(300)
        self.logs_display.setPlaceholderText("Docker logs will appear here automatically...\n\nIf no logs appear, make sure the Frigate container is running.")
        
        # Configure text edit for better auto-scrolling
        self.logs_display.setReadOnly(True)  # Make it read-only for better performance
        self.logs_display.setLineWrapMode(QTextEdit.WidgetWidth)
        
        # Apply enhanced scroll styling
        self.logs_display.setStyleSheet(f"""
            QTextEdit {{
                background: #fafbfc;
                border: 1px solid #e5e8eb;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                font-size: 10px;
                color: #2d3748;
                padding: 8px;
                line-height: 1.3;
            }}
            {self.scroll_bar_style}
        """)
        
        # Apply enhanced scroll styling
        self.logs_display.setStyleSheet(f"""
            QTextEdit {{
                background: #fafbfc;
                border: 1px solid #e5e8eb;
                border-radius: 6px;
                font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                font-size: 10px;
                color: #2d3748;
                padding: 8px;
                line-height: 1.3;
            }}
            {self.scroll_bar_style}
        """)
        
        # Enable auto-scroll to bottom when new text is added (same as Prerequisites tab)
        self.logs_display.textChanged.connect(self.auto_scroll_logs_display)
        
        layout.addWidget(self.logs_display)
        
        # Start auto-refresh immediately when tab is created
        QTimer.singleShot(500, self.start_logs_auto_refresh)  # Start after short delay
        
        return widget
    
    def create_preconfigured_tab(self):
        """Create the PreConfigured Box tab - improved 70%/25% layout with prominent main panel"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Create a container widget with responsive 10% padding on all sides
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # Calculate responsive 10% padding based on current window size
        window_size = self.size()
        padding_horizontal = max(20, int(window_size.width() * 0.05))  # 5% each side = 10% total, min 20px
        padding_vertical = max(15, int(window_size.height() * 0.05))   # 5% each side = 10% total, min 15px
        
        container_layout.setContentsMargins(padding_horizontal, padding_vertical, padding_horizontal, padding_vertical)
        container_layout.setSpacing(15)
        
        # Store container reference for responsive updates
        self.responsive_containers.append(('preconfigured', container_layout))
        
        # Create horizontal splitter for improved 70%/25% layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)  # Prevent collapsing panels
        splitter.setHandleWidth(6)  # Slightly smaller handle for cleaner look
        
        # LEFT PANEL (70%) - Main functionality (bigger and more prominent)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)  # More padding for prominence
        left_layout.setSpacing(20)  # More spacing for cleaner look
        
        # Welcome Header - prominent and centered design for main panel
        header_group = QGroupBox("📦 Welcome to Your MemryX + Frigate Box")
        header_layout = QVBoxLayout(header_group)
        header_layout.setSpacing(12)
        
        welcome_message = QLabel(
            "🎯 Your system comes pre-configured and ready to go. "
            "Simply set up your cameras below to start intelligent video monitoring."
        )
        welcome_message.setWordWrap(True)
        welcome_message.setAlignment(Qt.AlignCenter)  # Center the text
        welcome_message.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4a90a4, stop:0.5 #38758a, stop:1 #2c6b7d);
                color: white;
                padding: 18px;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 15px;
                border: 3px solid rgba(255,255,255,0.3);
            }
        """)
        header_layout.addWidget(welcome_message)
        left_layout.addWidget(header_group)
        
        # System Issues Warning section (hidden by default)
        status_group = QGroupBox("📊 System Status")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(12)
        
        # System status indicators
        self.preconfigured_status_docker = QLabel("🔄 Checking...")
        self.preconfigured_status_memryx = QLabel("🔄 Checking...")
        self.preconfigured_status_frigate = QLabel("🔄 Checking...")
        
        # Create status labels using existing style from Overview tab

        self.preconfigured_memryx_status = QLabel("🔄 Initializing...")
        self.preconfigured_memryx_status.setProperty("status", True)
        self.preconfigured_frigate_status = QLabel("🔄 Initializing...")
        self.preconfigured_frigate_status.setProperty("status", True)
        
        status_layout.addWidget(QLabel("MemryX Devices:"), 0, 0)
        status_layout.addWidget(self.preconfigured_memryx_status, 0, 1)
        status_layout.addWidget(QLabel("Frigate Setup:"), 1, 0)
        status_layout.addWidget(self.preconfigured_frigate_status, 1, 1)
        
        # System Issues Warning section (hidden by default)
        self.warning_group = QGroupBox("⚠️ System Setup Required")
        self.warning_group.setVisible(False)  # Hidden by default
        warning_layout = QVBoxLayout(self.warning_group)
        warning_layout.setSpacing(10)
        
        # Warning message labels with light red styling
        self.docker_warning = QLabel("🐳 Docker not installed or not running. Docker setup required.")
        self.docker_warning.setVisible(False)
        self.docker_warning.setWordWrap(True)
        self.docker_warning.setStyleSheet("""
            QLabel {
                background: #fef2f2;
                color: #dc2626;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
                border-left: 4px solid #fca5a5;
                margin: 4px 0px;
            }
        """)
        
        self.memryx_warning = QLabel("🔧 MemryX device not detected. Manual setup required.")
        self.memryx_warning.setVisible(False)
        self.memryx_warning.setWordWrap(True)
        self.memryx_warning.setStyleSheet("""
            QLabel {
                background: #fef2f2;
                color: #dc2626;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
                border-left: 4px solid #fca5a5;
                margin: 4px 0px;
            }
        """)
        
        self.frigate_warning = QLabel("🎥 Frigate not properly configured. Manual setup recommended.")
        self.frigate_warning.setVisible(False)
        self.frigate_warning.setWordWrap(True)
        self.frigate_warning.setStyleSheet("""
            QLabel {
                background: #fef2f2;
                color: #dc2626;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
                border-left: 4px solid #fca5a5;
                margin: 4px 0px;
            }
        """)
        
        # Manual setup suggestion button
        self.manual_setup_btn = QPushButton("🛠️ Go to Manual Setup")
        self.manual_setup_btn.setVisible(False)
        self.manual_setup_btn.clicked.connect(lambda: self.main_tab_widget.setCurrentIndex(1))  # Switch to Manual Setup tab
        self.manual_setup_btn.setMinimumHeight(40)
        self.manual_setup_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fca5a5, stop:1 #f87171);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
                margin: 8px 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fed7d7, stop:1 #fca5a5);
            }
            QPushButton:pressed {
                background: #f87171;
            }
        """)
        
        warning_layout.addWidget(self.docker_warning)
        warning_layout.addWidget(self.memryx_warning)
        warning_layout.addWidget(self.frigate_warning)
        warning_layout.addWidget(self.manual_setup_btn)
        
        # Main Camera Setup section - wrapped in scroll area for responsive resizing
        camera_setup_scroll = QScrollArea()
        camera_setup_scroll.setWidgetResizable(True)
        camera_setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        camera_setup_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        camera_setup_scroll.setFrameShape(QFrame.NoFrame)  # Remove frame for cleaner look
        camera_setup_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #4a90a4;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38758a;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #4a90a4;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38758a;
            }
        """)
        
        setup_group = QGroupBox("🎥 Camera Setup")
        setup_group.setMinimumHeight(220)  # Ensure adequate height to prevent squeezing
        setup_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4a90a4;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
                margin-top: 12px;
                padding-top: 20px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f8f9fa, stop:1 #f0f7ff);
            }
            QGroupBox::title {
                color: #2c6b7d;
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                font-size: 15px;
                font-weight: bold;
                background: white;
                border-radius: 6px;
            }
        """)
        setup_layout = QVBoxLayout(setup_group)
        setup_layout.setSpacing(25)  # Increased spacing to prevent cramping
        setup_layout.setContentsMargins(15, 15, 15, 15)  # Add margins for breathing room
        
        # Info section with enhanced styling and visual appeal - improved spacing
        info_label = QLabel(
            "🚀 Ready to get started? Click below to configure your cameras. "
            "You'll need your camera IP addresses, login credentials, and that's it!"
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignCenter)  # Center the info text
        info_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f7ff, stop:0.5 #e8f2ff, stop:1 #e8f5e8);
                color: #2c3e50;
                padding: 18px;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 600;
                border: 2px solid #a8c8e8;
                margin: 8px 2px;
            }
        """)
        setup_layout.addWidget(info_label)
        
        # Camera Setup Guide section (FIRST - for learning how to setup cameras)
        guide_container = QWidget()
        guide_layout = QVBoxLayout(guide_container)  # Changed to VBoxLayout for better responsive behavior
        guide_layout.setContentsMargins(0, 10, 0, 0)
        guide_layout.setSpacing(10)
        
        # Create a horizontal container for larger screens, but allow vertical stacking on small screens
        guide_row_container = QWidget()
        guide_row_layout = QHBoxLayout(guide_row_container)
        guide_row_layout.setContentsMargins(0, 0, 0, 0)
        
        # Guide button (primary step) - with responsive sizing
        self.camera_guide_btn = QPushButton("📖 Camera Setup Guide")
        self.camera_guide_btn.setMinimumHeight(45)
        self.camera_guide_btn.setMinimumWidth(200)
        self.camera_guide_btn.setMaximumWidth(250)  # Prevent excessive stretching
        self.camera_guide_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.camera_guide_btn.clicked.connect(self.show_camera_setup_guide)
        self.camera_guide_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #007bff, stop:1 #0056b3);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px 20px;
                font-size: 14px;
                font-weight: 600;
                margin: 4px 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0084ff, stop:1 #0062cc);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0062cc, stop:1 #004a9f);
            }
        """)
        
        # Guide description - with responsive text wrapping
        guide_description = QLabel(
            "<b>Step 1:</b> Learn how to setup your Amcrest camera (with WiFi, username/password)"
        )
        guide_description.setWordWrap(True)
        guide_description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        guide_description.setStyleSheet("""
            QLabel {
                background: #e8f4fd;
                color: #0f766e;
                padding: 12px 15px;
                border-radius: 8px;
                font-size: 13px;
                border: 1px solid #bfdbfe;
                margin-left: 10px;
            }
        """)
        
        guide_row_layout.addWidget(self.camera_guide_btn)
        guide_row_layout.addWidget(guide_description, 1)  # Stretch factor 1
        guide_layout.addWidget(guide_row_container)
        setup_layout.addWidget(guide_container)
        
        # Setup Cameras section (SECOND - after learning from guide)
        setup_container = QWidget()
        setup_container_layout = QVBoxLayout(setup_container)  # Changed to VBoxLayout for better responsive behavior
        setup_container_layout.setContentsMargins(0, 15, 0, 5)
        setup_container_layout.setSpacing(10)
        
        # Create button container with centering
        setup_button_container = QWidget()
        setup_button_layout = QHBoxLayout(setup_button_container)
        setup_button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add stretch before button for centering
        setup_button_layout.addStretch(1)
        
        # Setup button (secondary step) - responsive sizing
        self.setup_cameras_btn = QPushButton("🎥 Set Up Your Cameras")
        self.setup_cameras_btn.setMinimumHeight(55)
        self.setup_cameras_btn.setMinimumWidth(300)
        self.setup_cameras_btn.setMaximumWidth(400)  # Prevent excessive stretching
        self.setup_cameras_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setup_cameras_btn.clicked.connect(self.open_simple_camera_gui)
        self.setup_cameras_btn.setEnabled(False)  # Disabled during initialization
        self.setup_cameras_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #48bb78, stop:1 #38a169);
                color: white;
                border: none;
                border-radius: 12px;
                padding: 16px 24px;
                font-size: 16px;
                font-weight: 600;
                margin: 4px 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4bc985, stop:1 #3fba7a);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3fba7a, stop:1 #309656);
            }
            QPushButton:disabled {
                background: #d4edda;
                color: #6c757d;
                border: 2px solid #c3e6cb;
            }
        """)
        
        # Add the button to the layout!
        setup_button_layout.addWidget(self.setup_cameras_btn)
        
        # Add stretch after button for centering
        setup_button_layout.addStretch(1)
        
        setup_container_layout.addWidget(setup_button_container)
        
        # Setup description - centered and responsive
        setup_description = QLabel(
            "<b>Step 2:</b> Add your cameras to Frigate application and configure detection settings. "
            "Once set up, <b>click the Start Frigate button below</b>."
        )
        setup_description.setWordWrap(True)
        setup_description.setAlignment(Qt.AlignCenter)
        setup_description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        setup_description.setStyleSheet("""
            QLabel {
                background: #f0f9f0;
                color: #166534;
                padding: 12px 15px;
                border-radius: 8px;
                font-size: 13px;
                border: 1px solid #bbf7d0;
                margin: 10px 0px;
            }
        """)
        
        setup_container_layout.addWidget(setup_description)
        setup_layout.addWidget(setup_container)
        
        # Set the camera setup group as the scroll area's widget
        camera_setup_scroll.setWidget(setup_group)
        
        left_layout.addWidget(camera_setup_scroll)
        
        # Quick Actions section - matching Overview tab style
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(12)
        
        # Docker control buttons row with custom sizing
        docker_buttons_layout = QHBoxLayout()
        docker_buttons_layout.setSpacing(8)
        
        # Start Frigate button (65% width)
        self.preconfigured_start_btn = QPushButton("▶️ Start Frigate")
        self.preconfigured_start_btn.clicked.connect(lambda: self.docker_action('start'))
        self.preconfigured_start_btn.setMinimumHeight(45)
        self.preconfigured_start_btn.setToolTip("Start Frigate container")
        self.preconfigured_start_btn.setEnabled(False)  # Disabled during initialization
        
        # Stop Frigate button (35% width) 
        self.preconfigured_stop_btn = QPushButton("⏹️ Stop + Remove")
        self.preconfigured_stop_btn.clicked.connect(lambda: self.docker_action('remove'))
        self.preconfigured_stop_btn.setMinimumHeight(45)
        self.preconfigured_stop_btn.setToolTip("Stop and remove Frigate container completely")
        self.preconfigured_stop_btn.setEnabled(False)  # Disabled during initialization
        self.preconfigured_stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f87171, stop:1 #ef4444);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 16px;
                font-weight: 600;
                font-size: 14px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QPushButton:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fca5a5, stop:1 #f87171);
            }
            QPushButton:pressed {
                background: #dc2626;
            }
            QPushButton:disabled {
                background: #a0aec0;
                color: #718096;
            }
        """)
        
        # Add buttons with stretch factors (65% and 35%)
        docker_buttons_layout.addWidget(self.preconfigured_start_btn, 65)
        docker_buttons_layout.addWidget(self.preconfigured_stop_btn, 35)
        
        actions_layout.addLayout(docker_buttons_layout)
        
        # Open Web UI button (full width) - store as instance variable for state management
        self.preconfigured_open_ui_btn = QPushButton("🌐 Open Frigate Web UI")
        self.preconfigured_open_ui_btn.clicked.connect(self.open_frigate_web_ui)
        self.preconfigured_open_ui_btn.setMinimumHeight(40)
        self.preconfigured_open_ui_btn.setToolTip("Open Frigate Web UI (enabled only when Frigate is running)")
        self.preconfigured_open_ui_btn.setEnabled(False)  # Disabled during initialization
        
        # Store the original style for proper restoration after highlighting
        self._web_ui_btn_original_style = self.preconfigured_open_ui_btn.styleSheet()
        
        actions_layout.addWidget(self.preconfigured_open_ui_btn)
        left_layout.addWidget(actions_group)
        
        left_layout.addStretch()
        
        # RIGHT PANEL (15%) - More Compact Sidebar with Status and Information
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 10, 8, 10)  # Even smaller margins for more compact look
        right_layout.setSpacing(8)  # Tighter spacing for maximum compactness
        
        # Add spacing at top to align with left panel content (matches left panel header section)
        # This spacer aligns the status section with the camera setup section
        top_spacer = QWidget()
        top_spacer.setFixedHeight(120)  # Increased to better match the welcome header + spacing
        right_layout.addWidget(top_spacer)
        
        # System Status section - more compact sidebar style
        status_group = QGroupBox("📊 Status")
        status_layout = QGridLayout(status_group)
        status_layout.setSpacing(6)  # Even tighter spacing
        status_layout.setContentsMargins(8, 8, 8, 8)  # Smaller margins for compact look
        
        # Create status labels using existing style from Overview tab
        self.preconfigured_memryx_status = QLabel("🔄 Initializing...")
        self.preconfigured_memryx_status.setProperty("status", True)
        self.preconfigured_frigate_status = QLabel("🔄 Initializing...")
        self.preconfigured_frigate_status.setProperty("status", True)
        
        status_layout.addWidget(QLabel("MemryX Devices:"), 0, 0)
        status_layout.addWidget(self.preconfigured_memryx_status, 0, 1)
        status_layout.addWidget(QLabel("Frigate Setup:"), 1, 0)
        status_layout.addWidget(self.preconfigured_frigate_status, 1, 1)
        
        right_layout.addWidget(status_group)
        
        # Add warning group to right panel
        right_layout.addWidget(self.warning_group)
        
        # System Information section - very compact version with essential info
        system_info_group = QGroupBox("🖥️ System Information")
        system_info_layout = QFormLayout(system_info_group)
        system_info_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        system_info_layout.setSpacing(6)  # Tighter spacing
        system_info_layout.setContentsMargins(8, 8, 8, 8)  # Smaller margins for compact sidebar
        
        # Add system details (reusing code from overview tab)
        import platform
        
        system_info_layout.addRow("Config Path:", QLabel(os.path.join(self.script_dir, "frigate", "config")))
        system_info_layout.addRow("Operating System:", QLabel(f"{platform.system()} {platform.release()}"))
        system_info_layout.addRow("Architecture:", QLabel(platform.machine()))
        system_info_layout.addRow("Python Version:", QLabel(platform.python_version()))
        
        right_layout.addWidget(system_info_group)
        
        # Troubleshooting section - appears when Docker is running (moved to right panel)
        self.troubleshooting_group = QGroupBox("🛠️ Having Trouble?")
        self.troubleshooting_group.setVisible(False)  # Hidden by default, shows when Frigate is running
        troubleshooting_layout = QVBoxLayout(self.troubleshooting_group)
        troubleshooting_layout.setSpacing(8)  # Tighter spacing for sidebar
        troubleshooting_layout.setContentsMargins(8, 8, 8, 8)  # Smaller margins for compact sidebar
        
        # Troubleshooting message - more compact for sidebar
        troubleshooting_message = QLabel(
            "⚠️ If Frigate isn't working as expected, check the logs for detailed information."
        )
        troubleshooting_message.setWordWrap(True)
        troubleshooting_message.setStyleSheet("""
            QLabel {
                background: #fffbf5;
                color: #fb923c;
                padding: 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                border: 2px solid #fde4cc;
                margin: 2px 0px;
            }
        """)
        
        # Button to go to Docker logs - more compact for sidebar and left-aligned
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        
        self.view_logs_btn = QPushButton("📋 View Logs")
        self.view_logs_btn.clicked.connect(self.go_to_docker_logs)
        self.view_logs_btn.setMinimumHeight(35)
        self.view_logs_btn.setMaximumWidth(120)  # Limit width to make it smaller
        self.view_logs_btn.setToolTip("Open Advanced Settings → Docker Logs to view detailed Frigate logs")
        self.view_logs_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fb923c, stop:1 #f97316);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 600;
                margin: 4px 0px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #fdba74, stop:1 #fb923c);
            }
            QPushButton:pressed {
                background: #ea580c;
            }
        """)
        
        button_layout.addWidget(self.view_logs_btn)
        button_layout.addStretch()  # Push button to the left
        
        troubleshooting_layout.addWidget(troubleshooting_message)
        troubleshooting_layout.addWidget(button_container)
        
        right_layout.addWidget(self.troubleshooting_group)
        
        right_layout.addStretch()
        
        # Add panels to splitter with 75%/15% sizing (10% empty space for maximum breathing room)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Set explicit 75%/15% proportions with 10% buffer space for better visual balance
        splitter.setSizes([750, 150])  
        
        # Ensure the left panel stays prominent while making right panel more compact
        splitter.setStretchFactor(0, 75)  # Left panel: stretch factor 75 (75% - unchanged)
        splitter.setStretchFactor(1, 15)  # Right panel: stretch factor 15 (15% - smaller sidebar)
        
        # Add splitter to container layout (with padding)
        container_layout.addWidget(splitter)
        
        # Add container to main layout with scroll area for content that might get squeezed
        scroll_area = QScrollArea()
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)  # Allow the widget to resize with the scroll area
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)  # Remove frame for cleaner look
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #4a90a4;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38758a;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #4a90a4;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38758a;
            }
        """)
        layout.addWidget(scroll_area)
        
        # Update status on tab creation - reuse existing check_status method
        QTimer.singleShot(500, self.update_preconfigured_status)
        
        # Update button states after tab creation
        QTimer.singleShot(1000, self.update_preconfigured_button_states)  # Check container status after tab loads
        
        # Set up auto-refresh timer for PreConfigured tab (every 30 seconds to reduce CPU usage)
        self.preconfigured_refresh_timer = QTimer()
        self.preconfigured_refresh_timer.timeout.connect(self.update_preconfigured_status)
        self.preconfigured_refresh_timer.setInterval(30000)  # 30 seconds
        self.preconfigured_refresh_timer.start()
        
        return widget
    
    def create_manual_setup_tab(self):
        """Create the Manual Setup tab with Prerequisites and Frigate Setup"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Create a container widget with responsive 5% padding on all sides
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # Calculate responsive 5% padding based on current window size
        window_size = self.size()
        padding_horizontal = max(15, int(window_size.width() * 0.025))  # 2.5% each side = 5% total, min 15px
        padding_vertical = max(10, int(window_size.height() * 0.025))   # 2.5% each side = 5% total, min 10px
        
        container_layout.setContentsMargins(padding_horizontal, padding_vertical, padding_horizontal, padding_vertical)
        container_layout.setSpacing(12)
        
        # Store container reference for responsive updates
        self.responsive_containers.append(('manual', container_layout))
        
        # Manual setup sub-tabs
        self.manual_tab_widget = QTabWidget()
        
        # Add Prerequisites and Frigate Setup tabs
        self.manual_tab_widget.addTab(self.create_prerequisites_tab(), "🔧 Prerequisites")
        self.manual_tab_widget.addTab(self.create_setup_tab(), "⚙️ Frigate Setup")
        
        container_layout.addWidget(self.manual_tab_widget)
        
        # Add container to main layout with scroll area for content that might get squeezed
        scroll_area = QScrollArea()
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)  # Allow the widget to resize with the scroll area
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)  # Remove frame for cleaner look
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #4a90a4;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38758a;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #4a90a4;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38758a;
            }
        """)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_advanced_settings_tab(self):
        """Create the Advanced Settings tab containing all current functionality"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Create a container widget with responsive 5% padding on all sides
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # Calculate responsive 5% padding based on current window size
        window_size = self.size()
        padding_horizontal = max(15, int(window_size.width() * 0.025))  # 2.5% each side = 5% total, min 15px
        padding_vertical = max(10, int(window_size.height() * 0.025))   # 2.5% each side = 5% total, min 10px
        
        container_layout.setContentsMargins(padding_horizontal, padding_vertical, padding_horizontal, padding_vertical)
        container_layout.setSpacing(6)
        
        # Store container reference for responsive updates
        self.responsive_containers.append(('advanced', container_layout))
        
        # Advanced settings sub-tabs (all the original functionality)
        self.advanced_tab_widget = QTabWidget()
        
        # Add remaining advanced tabs (Prerequisites and Frigate Setup moved to Manual Setup tab, Overview tab removed)
        self.advanced_tab_widget.addTab(self.create_config_tab(), "🎛️ Configuration")
        self.advanced_tab_widget.addTab(self.create_docker_manager_tab(), "🐳 Docker Manager")
        self.advanced_tab_widget.addTab(self.create_logs_tab(), "📋 Docker Logs")
        
        container_layout.addWidget(self.advanced_tab_widget)
        
        # Add container to main layout with scroll area for content that might get squeezed
        scroll_area = QScrollArea()
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)  # Allow the widget to resize with the scroll area
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)  # Remove frame for cleaner look
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #4a90a4;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38758a;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #4a90a4;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38758a;
            }
        """)
        layout.addWidget(scroll_area)
        return widget
    
    def _check_container_exists_sync(self):
        """Synchronously check if Frigate container exists (for UI updates)"""
        try:
            result = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=frigate', '--format', '{{.Names}}'], 
                                    capture_output=True, text=True, timeout=5)
            return 'frigate' in result.stdout
        except:
            return False
    
    def check_status(self):
        """Check system status using background thread to avoid UI blocking"""
        # Use background worker instead of blocking subprocess calls
        self.start_background_status_check()
    
    def update_system_monitoring(self):
        """Update system monitoring labels for both Overview and Docker Manager tabs"""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            import psutil
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_text = f"{cpu_percent:.1f}%"
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            memory_text = f"{memory_percent:.1f}% ({memory_used_gb:.1f} GB / {memory_total_gb:.1f} GB)"
            
            # Update Overview tab labels (if they exist)
            if hasattr(self, 'cpu_usage_label'):
                self.cpu_usage_label.setText(cpu_text)
            if hasattr(self, 'memory_usage_label'):
                self.memory_usage_label.setText(memory_text)
            if hasattr(self, 'disk_usage_label'):
                # Get disk usage for the script directory
                disk_usage = psutil.disk_usage(self.script_dir)
                disk_percent = (disk_usage.used / disk_usage.total) * 100
                disk_used_gb = disk_usage.used / (1024**3)
                disk_total_gb = disk_usage.total / (1024**3)
                disk_text = f"{disk_percent:.1f}% ({disk_used_gb:.1f} GB / {disk_total_gb:.1f} GB)"
                self.disk_usage_label.setText(disk_text)
                
        except Exception as e:
            # Handle any errors gracefully
            error_text = f"❌ Error: {str(e)[:20]}..."
            
            # Update Overview tab labels with error
            if hasattr(self, 'cpu_usage_label'):
                self.cpu_usage_label.setText(error_text)
            if hasattr(self, 'memory_usage_label'):
                self.memory_usage_label.setText(error_text)
            if hasattr(self, 'disk_usage_label'):
                self.disk_usage_label.setText(error_text)
    
    def get_memryx_devices(self):
        """Get MemryX devices with caching to improve performance"""
        # Use cached result if available and not too old (cache for 10 seconds)
        current_time = time.time()
        if hasattr(self, '_memryx_cache') and hasattr(self, '_memryx_cache_time'):
            if current_time - self._memryx_cache_time < 10:
                return self._memryx_cache
        
        try:
            import glob
            devices = [d for d in glob.glob("/dev/memx*") if "_feature" not in d]
            result = f"{len(devices)} devices found" if devices else "No devices found"
            
            # Cache the result
            self._memryx_cache = result
            self._memryx_cache_time = current_time
            return result
        except Exception:
            result = "Unable to check devices"
            # Cache the error result too (but for shorter time)
            self._memryx_cache = result
            self._memryx_cache_time = current_time - 5  # Cache error for only 5 seconds
            return result
    
    def check_repo_status(self):
        """Check the current status of the Frigate repository"""
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if not os.path.exists(frigate_path):
            self.repo_status_label.setText("❌ No Frigate repository found")
            self.repo_status_label.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
            return
        
        git_dir = os.path.join(frigate_path, '.git')
        if not os.path.exists(git_dir):
            self.repo_status_label.setText("⚠️ Frigate directory exists but is not a git repository")
            self.repo_status_label.setStyleSheet("background: #fdf6e3; color: #8b7355; padding: 8px; border-radius: 6px;")
            return
        
        try:
            # Check git status
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  cwd=frigate_path, capture_output=True, text=True)
            if result.returncode != 0:
                self.repo_status_label.setText("❌ Git repository is corrupted")
                self.repo_status_label.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
                return
            
            # Check for local changes
            has_changes = bool(result.stdout.strip())
            
            # Get current branch and commit info
            branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                         cwd=frigate_path, capture_output=True, text=True)
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "detached"
            
            # Get last commit info
            commit_result = subprocess.run(['git', 'log', '-1', '--format=%h - %s (%cr)'], 
                                         cwd=frigate_path, capture_output=True, text=True)
            last_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"
            
            # Check if we can fetch (to see if there are remote updates)
            try:
                subprocess.run(['git', 'fetch', '--dry-run'], cwd=frigate_path, 
                             capture_output=True, timeout=10)
                fetch_status = "✅ Can connect to remote"
            except:
                fetch_status = "⚠️ Cannot connect to remote"
            
            status_text = f"✅ Valid git repository\n"
            status_text += f"Branch: {current_branch}\n"
            status_text += f"Last commit: {last_commit}\n"
            status_text += f"Local changes: {'Yes' if has_changes else 'No'}\n"
            status_text += f"Remote status: {fetch_status}"
            
            self.repo_status_label.setText(status_text)
            self.repo_status_label.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 8px; border-radius: 6px;")
            
        except Exception as e:
            self.repo_status_label.setText(f"❌ Error checking repository: {str(e)}")
            self.repo_status_label.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
        
        # Update guidance after checking status
        if hasattr(self, 'step2_guidance'):
            self.update_step2_guidance()
    
    def install_frigate(self, action_type='skip_frigate'):
        """Start the installation process with specified action type"""
        # Clear progress and show action being performed
        self.install_progress.clear()
        
        action_descriptions = {
            'clone_only': "🚀 Starting Frigate repository clone process...",
            'update_only': "🔄 Starting Frigate repository update process...",
        }
        
        self.install_progress.append(action_descriptions.get(action_type, "Starting installation..."))
        
        # Enhanced validation for repository actions
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if action_type == 'clone_only':
            self.install_progress.append("📋 Cloning fresh Frigate repository...")
            if os.path.exists(frigate_path):
                self.install_progress.append("⚠️  Existing Frigate directory will be removed and replaced.")
        
        if action_type == 'update_only':
            self.install_progress.append("📋 Updating existing Frigate repository...")
            if not os.path.exists(frigate_path):
                QMessageBox.warning(self, "Cannot Update", 
                                  "❌ No Frigate repository found to update.\n\n"
                                  "Please use 'Clone Fresh Repository' instead to download Frigate for the first time.")
                self.install_progress.append("❌ Update aborted: No repository found")
                return
            
            git_dir = os.path.join(frigate_path, '.git')
            if not os.path.exists(git_dir):
                QMessageBox.warning(self, "Cannot Update", 
                                  "❌ Frigate directory exists but is not a git repository.\n\n"
                                  "Please use 'Clone Fresh Repository' instead to fix this issue.")
                self.install_progress.append("❌ Update aborted: Invalid repository")
                return
            
            self.install_progress.append("✅ Valid repository found, proceeding with update...")
        
        # Disable buttons during operation
        if hasattr(self, 'clone_frigate_btn'):
            self.clone_frigate_btn.setEnabled(False)
        if hasattr(self, 'update_frigate_btn'):
            self.update_frigate_btn.setEnabled(False)
        
        # Start the worker
        self.worker = InstallWorker(self.script_dir, action_type)
        self.worker.progress.connect(self.handle_install_progress)
        self.worker.finished.connect(self.on_install_finished)
        self.worker.start()
    
    def handle_install_progress(self, message):
        """Handle progress messages from install worker, with special handling for config file updates"""
        if message == "UPDATE_CONFIG_MTIME":
            # Special signal to update config file mtime after creating default config
            # This prevents the reload popup when we automatically create the config
            config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
            if os.path.exists(config_path):
                try:
                    self.config_file_mtime = os.path.getmtime(config_path)
                except Exception:
                    pass  # Silently handle any errors
        else:
            # Normal progress message, append to log
            self.install_progress.append(message)
    
    def on_install_finished(self, success):
        # Re-enable buttons
        if hasattr(self, 'clone_frigate_btn'):
            self.clone_frigate_btn.setEnabled(True)
        if hasattr(self, 'update_frigate_btn'):
            self.update_frigate_btn.setEnabled(True)
        
        if success:
            self.install_progress.append("🎉 Operation completed successfully!")
            QMessageBox.information(self, "Success", 
                                  "✅ Setup completed successfully!\n\n"
                                  "You can now proceed to the next steps or configure Frigate.")
        else:
            self.install_progress.append("💡 Please check the error messages above and try again.")
            QMessageBox.warning(self, "Error", 
                              "❌ Setup failed. Please check the progress log for details.\n\n"
                              "Common issues:\n"
                              "• Missing dependencies (git, python3, docker)\n"
                              "• Network connectivity problems\n"
                              "• Permission issues")
        
        # Refresh status displays
        self.check_status()
        self.check_repo_status()
        if hasattr(self, 'step2_guidance'):
            self.update_step2_guidance()

    def set_docker_buttons_enabled(self, enabled, keep_stop_enabled=False):
        """Enable or disable Docker operation buttons to prevent conflicts
        
        Args:
            enabled (bool): Whether to enable/disable buttons
            keep_stop_enabled (bool): If True, keeps the Stop button enabled even when others are disabled
        """
        # Disable/enable all Docker operation buttons
        if hasattr(self, 'docker_start_btn'):
            self.docker_start_btn.setEnabled(enabled)
        if hasattr(self, 'docker_stop_btn'):
            # Keep stop button enabled if requested, or follow the general enabled state
            self.docker_stop_btn.setEnabled(enabled or keep_stop_enabled)
        if hasattr(self, 'docker_restart_btn'):
            # Smart enable for restart: only enable if operation is enabled AND container exists
            if enabled:
                self.docker_restart_btn.setEnabled(self._check_container_exists_sync())
            else:
                self.docker_restart_btn.setEnabled(False)
        if hasattr(self, 'docker_rebuild_btn'):
            self.docker_rebuild_btn.setEnabled(enabled)
        if hasattr(self, 'docker_remove_btn'):
            self.docker_remove_btn.setEnabled(enabled)
        
        # Note: Web UI button is intentionally NOT disabled as it's just opening a URL
        # Users should be able to check the web interface even during operations

        # Update status indicator if it exists
        if hasattr(self, 'operation_status_label'):
            if enabled:
                self.operation_status_label.setText("🟢 Ready - All operations available")
                self.operation_status_label.setStyleSheet("""
                    QLabel {
                        background: #e8f4f0;
                        color: #2d5a4a;
                        padding: 8px;
                        border-radius: 6px;
                        font-size: 11px;
                        font-weight: bold;
                        margin: 4px 0px;
                    }
                """)
            else:
                if keep_stop_enabled:
                    self.operation_status_label.setText("🟡 Operation in progress - Stop button remains available")
                    self.operation_status_label.setStyleSheet("""
                        QLabel {
                            background: #fef3c7;
                            color: #92400e;
                            padding: 8px;
                            border-radius: 6px;
                            font-size: 11px;
                            font-weight: bold;
                            margin: 4px 0px;
                        }
                    """)
                else:
                    self.operation_status_label.setText("🔴 Operation in progress - buttons disabled")
                    self.operation_status_label.setStyleSheet("""
                        QLabel {
                            background: #fbeaea;
                            color: #6b3737;
                            padding: 8px;
                            border-radius: 6px;
                            font-size: 11px;
                            font-weight: bold;
                            margin: 4px 0px;
                        }
                    """)

    def show_first_time_startup_info_if_needed(self):
        """Show first-time startup info only if this is the first time starting Frigate"""
        try:
            # Check if we've shown this dialog before by looking for a flag file
            first_start_flag = os.path.join(self.script_dir, '.frigate_first_start_shown')
            
            # Also check if Frigate container exists (if it exists, probably not first time)
            container_exists = self._check_container_exists_sync()
            
            # Only show dialog if:
            # 1. We haven't shown it before (.frigate_first_start_shown doesn't exist)
            # 2. AND no Frigate container exists (truly first time)
            if not os.path.exists(first_start_flag) and not container_exists:
                self.show_first_time_startup_info()
                # Create flag file to prevent showing again
                try:
                    with open(first_start_flag, 'w') as f:
                        f.write("First start dialog shown")
                except Exception as e:
                    print(f"Could not create first start flag: {e}")
                    
        except Exception as e:
            print(f"Error checking first-time startup status: {e}")
            # On error, don't show the dialog to be safe

    def _check_container_exists_sync(self):
        """Synchronously check if Frigate container exists"""
        try:
            result = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=frigate', '--format', '{{.Names}}'], 
                                  capture_output=True, text=True, timeout=10)
            return 'frigate' in result.stdout
        except Exception:
            return False

    def show_first_time_startup_info(self):
        """Show information dialog about first-time Frigate startup duration"""
        info_dialog = QDialog(self)
        info_dialog.setWindowTitle("Starting Frigate")
        info_dialog.setFixedSize(480, 320)
        info_dialog.setModal(True)
        
        # Create layout
        layout = QVBoxLayout(info_dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icon and title
        title_layout = QHBoxLayout()
        
        # Icon label
        icon_label = QLabel("🚀")
        icon_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Starting Frigate...")
        title_label.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #0694a2;
            margin-left: 10px;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Info text
        info_text = QLabel(
            "⏰ <b>First-time startup may take 3-5 minutes</b><br><br>"
            "You'll see <b>\"🔨 Building Image\"</b> in the button - this is normal and expected."
        )
        info_text.setTextFormat(Qt.RichText)
        info_text.setStyleSheet("""
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: #2d3748;
            line-height: 1.5;
            padding: 15px;
            background: #f0f9ff;
            border-radius: 8px;
            border-left: 4px solid #0694a2;
        """)
        info_text.setWordWrap(True)
        layout.addWidget(info_text)
        
        # Button
        got_it_btn = QPushButton("Got It, Let's Start!")
        got_it_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0694a2, stop: 1 #0f766e);
                color: white;
                border: none;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                font-weight: 600;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0891b2, stop: 1 #164e63);
            }
        """)
        got_it_btn.clicked.connect(info_dialog.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(got_it_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Show dialog
        info_dialog.exec()

    def get_operation_status_message(self, enabled, keep_stop_enabled=False):
        """Get a user-friendly message about button states"""
        if enabled:
            return "🔓 All Docker operation buttons are now available"
        else:
            if keep_stop_enabled:
                return "🔒 Docker operation buttons disabled to prevent conflicts - Stop button remains available for emergency use"
            else:
                return "🔒 Docker operation buttons disabled to prevent conflicts - please wait for current operation to complete"
            
    def docker_action(self, action):
        # Check if application is still initializing
        if self.is_initializing:
            QMessageBox.information(
                self, "Please Wait", 
                "The application is still initializing. Please wait for the initialization to complete.",
                QMessageBox.Ok
            )
            return
            
        # PREVENT MULTIPLE CONCURRENT OPERATIONS
        if hasattr(self, 'docker_worker') and self.docker_worker is not None:
            if self.docker_worker.isRunning():
                if hasattr(self, 'docker_progress'):
                    self.docker_progress.append("⚠️ Another Docker operation is already in progress!")
                    self.docker_progress.append("Please wait for the current operation to complete, or use Stop to cancel it.")
                else:
                    QMessageBox.information(self, "Operation in Progress", 
                                          "Another Docker operation is already in progress!\n"
                                          "Please wait for it to complete.")
                return
            else:
                # Clean up finished worker
                try:
                    self.docker_worker.deleteLater()
                except:
                    pass
                self.docker_worker = None

        # Clear progress and show initial message
        if hasattr(self, 'docker_progress'):
            self.docker_progress.clear()
        
        # Store current action for completion message
        self.current_docker_action = action
        
        # Show first-time startup information dialog for start action (only on first time)
        if action == 'start':
            self.show_first_time_startup_info_if_needed()
        
        action_messages = {
            'start': "▶️ Initiating Frigate container start...",
            'stop': "⏹️ Initiating Frigate container stop...",
            'restart': "🔄 Initiating Frigate container restart...",
            'rebuild': "🔨 Initiating complete Frigate rebuild...",
            'remove': "🗑️ Initiating Frigate container removal..."
        }
        
        if hasattr(self, 'docker_progress'):
            self.docker_progress.append(action_messages.get(action, f"Starting {action} operation..."))
            self.docker_progress.append("=" * 50)  # Visual separator
        
        # DISABLE BUTTONS TO PREVENT CONFLICTS
        # For non-stop operations, keep the Stop button enabled for emergency use
        keep_stop_enabled = action != 'stop'
        self.set_docker_buttons_enabled(False, keep_stop_enabled=keep_stop_enabled)
        
        # Also disable PreConfigured Box buttons during operation
        if hasattr(self, 'preconfigured_start_btn'):
            self.preconfigured_start_btn.setEnabled(False)
        if hasattr(self, 'preconfigured_stop_btn'):
            # For stop operations, disable the stop button completely
            # For other operations, keep stop enabled for emergency use
            self.preconfigured_stop_btn.setEnabled(keep_stop_enabled)
            
        if hasattr(self, 'docker_progress'):
            self.docker_progress.append(self.get_operation_status_message(False, keep_stop_enabled=keep_stop_enabled))
        
        # Show confirmation for destructive actions
        if action in ['rebuild', 'remove']:
            action_names = {
                'rebuild': 'rebuild the Frigate container completely',
                'remove': 'stop and remove the Frigate container'
            }
            
            reply = QMessageBox.question(
                self, "Confirm Action", 
                f"Are you sure you want to {action_names[action]}?\n\n"
                f"This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                if hasattr(self, 'docker_progress'):
                    self.docker_progress.append("❌ Operation cancelled by user")
                # RE-ENABLE BUTTONS IF USER CANCELS
                self.set_docker_buttons_enabled(True)
                if hasattr(self, 'docker_progress'):
                    self.docker_progress.append(self.get_operation_status_message(True))
                return
        
        # Create and start the worker
        self.docker_worker = DockerWorker(self.script_dir, action)
        self.docker_worker.progress.connect(self._append_docker_progress)
        self.docker_worker.progress.connect(self.on_docker_progress_for_button)  # Connect button updates
        self.docker_worker.finished.connect(self.on_docker_finished)
        
        # Update button state based on action
        if action == 'start' or action == 'rebuild':
            self.update_preconfigured_button_state("building")
        elif action == 'remove':
            # For remove action (stop+remove), show stopping state
            self.update_preconfigured_button_state("stopping")
            
        self.docker_worker.start()

    def update_preconfigured_button_state(self, state, operation_text=""):
        """Update the preconfigured Start/Stop Frigate button states with animation"""
        if not hasattr(self, 'preconfigured_start_btn'):
            return
            
        self.button_operation_state = state
        
        if state == "idle":
            self.button_animation_timer.stop()
            self.preconfigured_start_btn.setText("▶️ Start Frigate")
            self.preconfigured_start_btn.setStyleSheet("")  # Reset to default
            self.preconfigured_start_btn.setEnabled(True)
            
            # Reset stop button to default state
            if hasattr(self, 'preconfigured_stop_btn'):
                self.preconfigured_stop_btn.setText("⏹️ Stop + Remove")
                self.preconfigured_stop_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                            stop:0 #f87171, stop:1 #ef4444);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 14px 16px;
                        font-weight: 600;
                        font-size: 14px;
                        font-family: 'Segoe UI', 'Inter', sans-serif;
                    }
                    QPushButton:hover:enabled {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                            stop:0 #fca5a5, stop:1 #f87171);
                    }
                    QPushButton:pressed {
                        background: #dc2626;
                    }
                    QPushButton:disabled {
                        background: #a0aec0;
                        color: #718096;
                    }
                """)
                self.preconfigured_stop_btn.setEnabled(False)
            
        elif state == "building":
            self.button_base_text = "🔨 Building Image"
            self.button_animation_dots = 0
            self.preconfigured_start_btn.setEnabled(False)
            self.preconfigured_start_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #ff9800, stop:1 #f57c00);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 16px;
                    font-weight: 600;
                    font-size: 14px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
            """)
            self.button_animation_timer.start(500)  # Update every 500ms
            
        elif state == "starting":
            self.button_base_text = "🚀 Starting Container"
            self.button_animation_dots = 0
            self.preconfigured_start_btn.setEnabled(False)
            self.preconfigured_start_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #2196f3, stop:1 #1976d2);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 16px;
                    font-weight: 600;
                    font-size: 14px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
            """)
            self.button_animation_timer.start(500)
            
        elif state == "stopping":
            self.button_base_text = "🛑 Stopping + Removing"
            self.button_animation_dots = 0
            self.preconfigured_start_btn.setEnabled(False)
            
            # Update stop button state during stopping
            if hasattr(self, 'preconfigured_stop_btn'):
                self.stop_button_base_text = "🛑 Stopping + Removing"
                self.preconfigured_stop_btn.setEnabled(False)
                self.preconfigured_stop_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                            stop:0 #ff5722, stop:1 #d84315);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 14px 16px;
                        font-weight: 600;
                        font-size: 14px;
                        font-family: 'Segoe UI', 'Inter', sans-serif;
                    }
                """)
            self.button_animation_timer.start(500)
            
        elif state == "running":
            self.button_animation_timer.stop()
            self.preconfigured_start_btn.setText("✅ Frigate Running")
            self.preconfigured_start_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #4caf50, stop:1 #388e3c);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 16px;
                    font-weight: 600;
                    font-size: 14px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
            """)
            self.preconfigured_start_btn.setEnabled(False)
            
            # Enable stop button when running
            if hasattr(self, 'preconfigured_stop_btn'):
                self.preconfigured_stop_btn.setText("⏹️ Stop + Remove")
                self.preconfigured_stop_btn.setEnabled(True)
                
        elif state == "stopped":
            self.button_animation_timer.stop()
            self.preconfigured_start_btn.setText("▶️ Start Frigate")
            self.preconfigured_start_btn.setStyleSheet("")  # Reset to default
            self.preconfigured_start_btn.setEnabled(True)
            
            # Update stop button to stopped state
            if hasattr(self, 'preconfigured_stop_btn'):
                self.preconfigured_stop_btn.setText("✅ Stopped & Removed")
                self.preconfigured_stop_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                            stop:0 #6c757d, stop:1 #5a6268);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 14px 16px;
                        font-weight: 600;
                        font-size: 14px;
                        font-family: 'Segoe UI', 'Inter', sans-serif;
                    }
                """)
                self.preconfigured_stop_btn.setEnabled(False)
            
        elif state == "error":
            self.button_animation_timer.stop()
            self.preconfigured_start_btn.setText("❌ Error - Click to Retry")
            self.preconfigured_start_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #f44336, stop:1 #d32f2f);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 14px 16px;
                    font-weight: 600;
                    font-size: 14px;
                    font-family: 'Segoe UI', 'Inter', sans-serif;
                }
            """)
            self.preconfigured_start_btn.setEnabled(True)

    def update_button_animation(self):
        """Update button text with animated dots"""
        if not hasattr(self, 'preconfigured_start_btn') or self.button_operation_state == "idle":
            return
            
        # Cycle through different numbers of dots (0, 1, 2, 3, then repeat)
        self.button_animation_dots = (self.button_animation_dots + 1) % 4
        dots = "." * self.button_animation_dots
        
        # Add padding spaces to keep button width consistent
        padding = "   " if self.button_animation_dots == 0 else "  " if self.button_animation_dots == 1 else " " if self.button_animation_dots == 2 else ""
        
        # Update start button animation
        if hasattr(self, 'button_base_text'):
            animated_text = f"{self.button_base_text}{dots}{padding}"
            self.preconfigured_start_btn.setText(animated_text)
        
        # Update stop button animation during stopping state
        if (self.button_operation_state == "stopping" and 
            hasattr(self, 'preconfigured_stop_btn') and 
            hasattr(self, 'stop_button_base_text')):
            stop_animated_text = f"{self.stop_button_base_text}{dots}{padding}"
            self.preconfigured_stop_btn.setText(stop_animated_text)

    def on_docker_progress_for_button(self, text):
        """Handle docker progress updates for button state enhancement"""
        if not hasattr(self, 'preconfigured_start_btn'):
            return
            
        # Map progress messages to button states
        text_lower = text.lower()
        
        if "building" in text_lower or "build" in text_lower:
            self.update_preconfigured_button_state("building")
        elif "starting" in text_lower or "creating" in text_lower:
            self.update_preconfigured_button_state("starting")
        elif "started successfully" in text_lower or "frigate is now running" in text_lower:
            self.update_preconfigured_button_state("running")
        elif "error" in text_lower or "failed" in text_lower:
            self.update_preconfigured_button_state("error")

    
    def _append_docker_progress(self, text):
        """Append text to docker progress with timestamp"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Don't add timestamp to separator lines or empty lines
        if text.strip() and not text.startswith("="):
            formatted_text = f"[{timestamp}] {text}"
        else:
            formatted_text = text
            
        if hasattr(self, 'docker_progress'):
            self.docker_progress.append(formatted_text)
        else:
            # Print to console if no docker_progress widget available
            print(f"Docker Progress: {formatted_text}")
    
    def on_docker_finished(self, success):
        # Update button state based on completion
        if hasattr(self, 'current_docker_action'):
            action = self.current_docker_action
            if action == 'start':
                if success:
                    self.update_preconfigured_button_state("running")
                else:
                    self.update_preconfigured_button_state("error")
            else:
                # For other actions, reset to idle state
                self.update_preconfigured_button_state("idle")
        
        # Add completion separator
        if hasattr(self, 'docker_progress'):
            self.docker_progress.append("=" * 50)
        
        if success:
            # Check what operation was performed and provide specific messages
            if hasattr(self, 'current_docker_action'):
                if self.current_docker_action == 'start':
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Frigate Docker container started successfully!")
                    QMessageBox.information(self, "Success", "Frigate Docker container started successfully!\n\nOpen Frigate Web UI to monitor.")
                elif self.current_docker_action == 'stop':
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Frigate Docker container stopped successfully!")
                    QMessageBox.information(self, "Success", "Frigate Docker container stopped successfully!")
                elif self.current_docker_action == 'restart':
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Frigate Docker container restarted successfully!")
                    QMessageBox.information(self, "Success", "Frigate Docker container restarted successfully!\n\nOpen Frigate Web UI to monitor.")
                elif self.current_docker_action == 'rebuild':
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Frigate Docker container rebuilt successfully!")
                    QMessageBox.information(self, "Success", "Frigate Docker container rebuilt successfully!")
                elif self.current_docker_action == 'remove':
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Frigate Docker container stopped and removed successfully!")
                    QMessageBox.information(self, "Success", "Frigate Docker container stopped and removed successfully!")
                    # Set stopped state for buttons
                    if hasattr(self, 'preconfigured_start_btn'):
                        QTimer.singleShot(500, lambda: self.update_preconfigured_button_state("stopped"))
                else:
                    # Fallback for unknown operations
                    if hasattr(self, 'docker_progress'):
                        self.docker_progress.append("🎉 Docker operation completed successfully!")
                    QMessageBox.information(self, "Success", "Docker operation completed successfully!")
            else:
                # Fallback if no action stored
                if hasattr(self, 'docker_progress'):
                    self.docker_progress.append("🎉 Docker operation completed successfully!")
                QMessageBox.information(self, "Success", "Docker operation completed successfully!")
        else:
            if hasattr(self, 'docker_progress'):
                self.docker_progress.append("❌ Docker operation failed. Check the logs above for details.")
            QMessageBox.warning(self, "Error", "Docker operation failed. Please check the logs.")
        
        # RE-ENABLE ALL BUTTONS AFTER OPERATION COMPLETES
        self.set_docker_buttons_enabled(True)
        
        # Re-enable PreConfigured Box buttons and update their states
        if hasattr(self, 'preconfigured_start_btn'):
            self.preconfigured_start_btn.setEnabled(True)
        
        if hasattr(self, 'docker_progress'):
            self.docker_progress.append(self.get_operation_status_message(True))
        
        # Update PreConfigured Box button states after operation
        if hasattr(self, 'preconfigured_start_btn') and hasattr(self, 'preconfigured_stop_btn'):
            QTimer.singleShot(1000, self.update_preconfigured_button_states)  # Update after 1 second delay
        
        # CLEAN UP WORKER THREAD
        if hasattr(self, 'docker_worker') and self.docker_worker is not None:
            try:
                self.docker_worker.deleteLater()
            except:
                pass
            self.docker_worker = None
        
        # Refresh the status
        self.check_status()
    
    def resizeEvent(self, event):
        """Handle window resize events to update responsive layouts"""
        super().resizeEvent(event)
        
        # Only update layouts if not in initialization phase
        if not getattr(self, 'is_initializing', True):
            # Use QTimer to defer the update and avoid blocking during resize
            QTimer.singleShot(50, self.update_responsive_layouts)
    
    def update_responsive_layouts(self):
        """Update responsive container layouts based on current window size"""
        if not hasattr(self, 'responsive_containers'):
            return
            
        window_size = self.size()
        # Calculate new responsive 10% padding with minimum values
        new_horizontal = max(20, int(window_size.width() * 0.05))   # 5% each side = 10% total, min 20px
        new_vertical = max(15, int(window_size.height() * 0.05))    # 5% each side = 10% total, min 15px
        
        # Update all registered responsive containers
        for tab_name, layout in self.responsive_containers:
            if layout and not layout.parent().isHidden():  # Only update visible layouts
                layout.setContentsMargins(new_horizontal, new_vertical, new_horizontal, new_vertical)
    
    def changeEvent(self, event):
        """Handle window state changes (minimize, maximize, restore)"""
        super().changeEvent(event)
        
        # If window is restored from minimized state or window state changes
        if event.type() == QEvent.WindowStateChange:
            # Update layouts after a short delay to ensure window is fully restored
            if not self.isMinimized():
                QTimer.singleShot(100, self.update_responsive_layouts)
    
    def showEvent(self, event):
        """Handle window show events"""
        super().showEvent(event)
        
        # Update layouts when window is shown
        if not getattr(self, 'is_initializing', True):
            QTimer.singleShot(50, self.update_responsive_layouts)
    
    def closeEvent(self, event):
        """Handle application close event - clean up worker threads"""
        try:
            # Stop and clean up docker worker thread
            if hasattr(self, 'docker_worker') and self.docker_worker is not None:
                if self.docker_worker.isRunning():
                    self.docker_worker.terminate()  # Force terminate if still running
                    self.docker_worker.wait(3000)  # Wait up to 3 seconds for termination
                try:
                    self.docker_worker.deleteLater()
                except:
                    pass
                self.docker_worker = None
            
            # Stop all timers
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()
            if hasattr(self, 'config_watcher_timer'):
                self.config_watcher_timer.stop()
            if hasattr(self, 'logs_timer'):
                self.logs_timer.stop()
            if hasattr(self, 'preconfigured_refresh_timer'):
                self.preconfigured_refresh_timer.stop()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        # Accept the close event
        event.accept()
    
    def open_web_ui(self):
        subprocess.Popen(['xdg-open', 'http://localhost:5000'])
    
    def open_config(self):
        """Open the advanced configuration GUI"""
        # Check if application is still initializing
        if self.is_initializing:
            QMessageBox.information(
                self, "Please Wait", 
                "The application is still initializing. Please wait for the initialization to complete.",
                QMessageBox.Ok
            )
            return
            
        if ConfigGUI is None:
            QMessageBox.critical(
                self, 'Advanced Config GUI Unavailable',
                'The Advanced Configuration GUI could not be loaded.\n'
                'Please ensure advanced_config_gui.py is available in the same directory.'
            )
            return
        
        try:
            # Create and show the advanced config GUI (same pattern as simple camera GUI)
            self.config_gui = ConfigGUI()
            # Pass reference to this launcher so config GUI can suppress popups if needed
            self.config_gui.launcher_parent = self
            self.config_gui.show()
        except Exception as e:
            QMessageBox.critical(
                self, 'Error Opening Config GUI',
                f'Could not open the Advanced Configuration GUI:\n{str(e)}'
            )
    
    def edit_config_manual(self):
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        subprocess.Popen(['xdg-open', config_path])
    
    def save_config(self):
        """Save the configuration from the editor to the config file"""
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        
        try:
            # Ensure the config directory exists
            config_dir = os.path.dirname(config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            # Get content from the text editor
            content = self.config_preview.toPlainText()
            
            # Basic YAML validation (optional - just check if it's not empty)
            if not content.strip():
                reply = QMessageBox.question(
                    self, "Empty Configuration", 
                    "The configuration is empty. Are you sure you want to save this?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # Create backup of existing config
            if os.path.exists(config_path):
                backup_path = config_path + '.backup'
                import shutil
                shutil.copy2(config_path, backup_path)
            
            # Save the new configuration
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update the tracked modification time after saving
            self.config_file_mtime = os.path.getmtime(config_path)
            
            QMessageBox.information(
                self, "Configuration Saved", 
                f"✅ Configuration saved successfully to:\n{config_path}\n\n"
                "A backup of the previous configuration was created."
            )
            
            # Update the config status in overview
            self.check_status()
            
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error", 
                f"❌ Failed to save configuration:\n{str(e)}\n\n"
                "Please check file permissions and try again."
            )
    
    def toggle_config_edit_mode(self):
        """Toggle between read-only and edit mode for configuration editor"""
        if self.config_is_read_only:
            # Switch to edit mode
            self.config_preview.setReadOnly(False)
            self.config_is_read_only = False
            self.edit_config_btn.setText("👁️ View")
            self.edit_config_btn.setToolTip("Switch to read-only view mode")
            self.save_config_btn.setEnabled(True)
            
            # Update styling for edit mode
            self.config_preview.setStyleSheet("""
                QTextEdit {
                    background: #ffffff;
                    border: 2px solid #28a745;
                    border-radius: 6px;
                    font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                    font-size: 13px;
                    color: #2d3748;
                    padding: 12px;
                    line-height: 1.5;
                }
            """)
        else:
            # Switch to read-only mode
            self.config_preview.setReadOnly(True)
            self.config_is_read_only = True
            self.edit_config_btn.setText("✏️ Edit")
            self.edit_config_btn.setToolTip("Switch to edit mode to modify the configuration")
            self.save_config_btn.setEnabled(False)
            
            # Update styling for read-only mode
            self.config_preview.setStyleSheet("""
                QTextEdit {
                    background: #f8f9fa;
                    border: 1px solid #cbd5e0;
                    border-radius: 6px;
                    font-family: 'Consolas', 'Monaco', 'Liberation Mono', monospace;
                    font-size: 13px;
                    color: #495057;
                    padding: 12px;
                    line-height: 1.5;
                }
            """)
    
    def check_prerequisites(self):
        """Check basic prerequisites - only if widgets exist (for backward compatibility)"""
        # This method is kept for compatibility with existing calls
        # The main prerequisite checking is now in the Prerequisites tab
        if hasattr(self, 'git_check') and hasattr(self, 'python_check') and hasattr(self, 'docker_check'):
            tools = {'git': self.git_check, 'python3': self.python_check, 'docker': self.docker_check}
            
            for tool, label in tools.items():
                result = subprocess.run(['which', tool], capture_output=True)
                if result.returncode == 0:
                    label.setText("✅ Installed")
                    label.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                else:
                    label.setText("❌ Missing")
                    label.setStyleSheet("background: #fbeaea; color: #6b3737;")
    
    def load_config_preview(self):
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.config_preview.setPlainText(content)
                # Update the tracked modification time
                self.config_file_mtime = os.path.getmtime(config_path)
            except Exception as e:
                self.config_preview.setPlainText(f"Error loading configuration file:\n{str(e)}")
        else:
            # Show a default configuration template if no config exists
            default_config = """# Frigate Configuration
# This is a basic template. Customize it for your cameras and setup.

mqtt:
  enabled: False

detectors:
  memx0:
    type: memryx
    device: PCIe:0

model:
  model_type: yolo-generic
  width: 320
  height: 320
  input_tensor: nchw
  input_dtype: float
  labelmap_path: /labelmap/coco-80.txt

# cameras:
# Add your cameras here
# example_camera:
#   ffmpeg:
#     inputs:
#       - path: rtsp://username:password@camera_ip:554/stream
#         roles:
#           - detect
#   detect:
#     width: 1280
#     height: 720

cameras:
  cam1:
    ffmpeg:
      inputs:
        - path: 
            rtsp://username:password@camera_ip:554/stream
          roles:
            - detect
    detect:
      width: 1920
      height: 1080
      fps: 20
      enabled: true

    objects:
      track:
        - person
        - car
        - bottle
        - cup

    snapshots:
      enabled: false
      bounding_box: true
      retain:
        default: 0  # Keep snapshots for 2 days
    record:
      enabled: false
      alerts:
        retain:
          days: 0
      detections:
        retain:
          days: 0

version: 0.17-0

# For more configuration options, visit:
# https://docs.frigate.video/configuration/
"""
            self.config_preview.setPlainText(default_config)
            self.config_file_mtime = 0  # No file exists yet
        
        # Ensure read-only state is maintained after reload
        if hasattr(self, 'config_is_read_only') and self.config_is_read_only:
            self.config_preview.setReadOnly(True)
    
    def check_config_file_changes(self):
        """Check if the config file has been modified externally and reload if necessary"""
        # Skip check if popup is suppressed (e.g., when saving from simple camera GUI)
        if self.suppress_config_change_popup:
            return
            
        config_path = os.path.join(self.script_dir, "frigate", "config", "config.yaml")
        
        if os.path.exists(config_path):
            try:
                current_mtime = os.path.getmtime(config_path)
                # If the file has been modified since we last loaded it
                if current_mtime > self.config_file_mtime:
                    # Check if the text editor has unsaved changes
                    with open(config_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    editor_content = self.config_preview.toPlainText()
                    
                    # Only reload if the content is actually different
                    if file_content != editor_content:
                        # Ask user if they want to reload (to avoid losing unsaved changes)
                        reply = QMessageBox.question(
                            self, "Configuration File Changed",
                            "The configuration file has been modified externally.\n"
                            "Do you want to reload it? This will discard any unsaved changes in the editor.",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.Yes
                        )
                        
                        if reply == QMessageBox.Yes:
                            self.config_preview.setPlainText(file_content)
                            self.config_file_mtime = current_mtime
                        else:
                            # User chose not to reload, update mtime to avoid asking again
                            # until the file changes again
                            self.config_file_mtime = current_mtime
                    else:
                        # Content is the same, just update mtime silently
                        self.config_file_mtime = current_mtime
                        
            except Exception as e:
                # Silently handle errors (file might be temporarily locked during writing)
                pass
        elif self.config_file_mtime > 0:
            # File was deleted externally
            self.config_file_mtime = 0
    
    def refresh_logs(self):
        try:
            # Get recent logs (last 200 lines to show more context)
            result = subprocess.run(['docker', 'logs', '--tail', '200', 'frigate'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                new_text = result.stdout
                current_text = self.logs_display.toPlainText()
                
                # Only update if text has changed
                if new_text != current_text:
                    # Check if this is new content being appended or completely different content
                    if current_text and new_text.startswith(current_text):
                        # New content appended - extract and append only the new part
                        new_part = new_text[len(current_text):]
                        if new_part.strip():  # Only append if there's actual new content
                            # Remove leading newline if present
                            new_part = new_part.lstrip('\n')
                            if new_part:
                                self.logs_display.append(new_part.rstrip('\n'))
                    else:
                        # Completely different content or first load - use setPlainText and force scroll
                        self.logs_display.setPlainText(new_text)
                        # Force scroll to bottom immediately after setPlainText
                        scrollbar = self.logs_display.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
            else:
                self.logs_display.setPlainText("Unable to fetch logs. Is Frigate container running?")
        except subprocess.FileNotFoundError:
            self.logs_display.setPlainText("Docker not found. Please ensure Docker is installed and running.")
        except Exception as e:
            self.logs_display.setPlainText(f"Error fetching logs: {str(e)}\n\nIs Frigate container running?")
    
    def start_logs_auto_refresh(self):
        """Start automatic logs refresh with 3-second interval"""
        # Start the logs timer immediately
        self.logs_timer.start(3000)  # Refresh every 3 seconds
        # Also refresh immediately to show current logs
        self.refresh_logs()
    
    def update_step2_guidance(self):
        """Update the guidance text for Step 2 based on current repository status"""
        # Only update if the step2_guidance label exists
        if not hasattr(self, 'step2_guidance'):
            return
            
        frigate_path = os.path.join(self.script_dir, 'frigate')
        
        if not os.path.exists(frigate_path):
            # No repository found
            guidance_text = (
                "💡 No Frigate repository found. Choose 'Clone Fresh Repository' to download "
                "Frigate for the first time."
            )
            self.step2_guidance.setText(guidance_text)
            if hasattr(self, 'clone_frigate_btn'):
                self.clone_frigate_btn.setEnabled(True)
            if hasattr(self, 'update_frigate_btn'):
                self.update_frigate_btn.setEnabled(False)
            
        elif not os.path.exists(os.path.join(frigate_path, '.git')):
            # Directory exists but not a git repository
            guidance_text = (
                "⚠️ Frigate directory exists but is not a git repository. "
                "Choose 'Clone Fresh Repository' to fix this issue."
            )
            self.step2_guidance.setText(guidance_text)
            if hasattr(self, 'clone_frigate_btn'):
                self.clone_frigate_btn.setEnabled(True)
            if hasattr(self, 'update_frigate_btn'):
                self.update_frigate_btn.setEnabled(False)
            
        else:
            # Valid git repository exists
            try:
                result = subprocess.run(['git', 'status', '--porcelain'], 
                                      cwd=frigate_path, capture_output=True, text=True)
                if result.returncode == 0:
                    guidance_text = (
                        "✅ Valid Frigate repository found. You can either:\n"
                        "• Use 'Update Existing Repository' to get the latest changes\n"
                        "• Use 'Clone Fresh Repository' to start completely fresh"
                    )
                    self.step2_guidance.setText(guidance_text)
                    if hasattr(self, 'clone_frigate_btn'):
                        self.clone_frigate_btn.setEnabled(True)
                    if hasattr(self, 'update_frigate_btn'):
                        self.update_frigate_btn.setEnabled(True)
                else:
                    guidance_text = (
                        "❌ Git repository appears corrupted. "
                        "Choose 'Clone Fresh Repository' to fix this issue."
                    )
                    self.step2_guidance.setText(guidance_text)
                    if hasattr(self, 'clone_frigate_btn'):
                        self.clone_frigate_btn.setEnabled(True)
                    if hasattr(self, 'update_frigate_btn'):
                        self.update_frigate_btn.setEnabled(False)
            except:
                guidance_text = (
                    "❓ Cannot determine repository status. "
                    "Choose 'Clone Fresh Repository' to be safe."
                )
                self.step2_guidance.setText(guidance_text)
                if hasattr(self, 'clone_frigate_btn'):
                    self.clone_frigate_btn.setEnabled(True)
                if hasattr(self, 'update_frigate_btn'):
                    self.update_frigate_btn.setEnabled(False)

    def check_setup_dependencies(self):
        """Check the Python environment dependencies for Frigate Setup"""
        try:
            # Check Python 3
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.setup_python_check.setText(f"✅ {version}")
                self.setup_python_check.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                self.install_setup_python_btn.setVisible(False)
            else:
                self.setup_python_check.setText("❌ Not Installed")
                self.setup_python_check.setStyleSheet("background: #fbeaea; color: #6b3737;")
                self.install_setup_python_btn.setVisible(True)
            
            # Check Pip
            result = subprocess.run(['python3', '-m', 'pip', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.split()[1] if result.stdout else "installed"
                self.setup_pip_check.setText(f"✅ pip {version}")
                self.setup_pip_check.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                self.install_setup_pip_btn.setVisible(False)
            else:
                self.setup_pip_check.setText("❌ Not Available")
                self.setup_pip_check.setStyleSheet("background: #fbeaea; color: #6b3737;")
                self.install_setup_pip_btn.setVisible(True)
            
            # Check Virtual Environment
            venv_path = os.path.join(self.script_dir, '.venv')
            if os.path.exists(venv_path) and os.path.exists(os.path.join(venv_path, 'bin', 'python')):
                self.setup_venv_check.setText("✅ Created")
                self.setup_venv_check.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                self.install_setup_venv_btn.setVisible(False)
            else:
                self.setup_venv_check.setText("❌ Not Created")
                self.setup_venv_check.setStyleSheet("background: #fbeaea; color: #6b3737;")
                self.install_setup_venv_btn.setVisible(True)
                
        except Exception as e:
            self.install_progress.append(f"❌ Error checking setup dependencies: {str(e)}")
    
    def install_setup_dependency(self, dep_type):
        """Install a setup dependency (python, pip, or venv)"""
        # Disable all install buttons during installation
        self.install_setup_python_btn.setEnabled(False)
        self.install_setup_pip_btn.setEnabled(False)
        self.install_setup_venv_btn.setEnabled(False)
        
        # Clear progress and show starting message
        self.install_progress.clear()
        dep_names = {
            'python': 'Python 3',
            'pip': 'Pip Package Manager',
            'venv': 'Virtual Environment'
        }
        
        self.install_progress.append(f"🚀 Starting {dep_names[dep_type]} setup...")
        
        if dep_type == 'python':
            self._install_python_for_setup()
        elif dep_type == 'pip':
            self._install_pip_for_setup()
        elif dep_type == 'venv':
            self._create_virtual_environment()
    
    def _install_python_for_setup(self):
        """Install Python 3 for setup tab"""
        try:
            self.install_progress.append("📦 Installing Python 3 and related packages...")
            
            # Update package repositories
            self.install_progress.append("🔄 Updating package repositories...")
            subprocess.run(['sudo', 'apt', 'update'], check=True)
            
            # Install Python 3 and related packages
            self.install_progress.append("📥 Installing Python 3, pip, and venv...")
            subprocess.run(['sudo', 'apt', 'install', '-y', 
                           'python3', 'python3-pip', 'python3-venv', 'python3-dev'], check=True)
            
            # Verify installation
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            self.install_progress.append(f"✅ Python installed successfully: {version}")
            
            # Re-enable buttons
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)
            
            # Refresh checks
            self.check_setup_dependencies()
            
        except subprocess.CalledProcessError as e:
            self.install_progress.append(f"❌ Python installation failed: {str(e)}")
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)
    
    def _install_pip_for_setup(self):
        """Install/upgrade pip for setup tab"""
        try:
            self.install_progress.append("📦 Installing/upgrading pip...")
            
            # Check if python3 is available
            result = subprocess.run(['python3', '--version'], capture_output=True)
            if result.returncode != 0:
                self.install_progress.append("❌ Python 3 must be installed first")
                return
            
            # Install/upgrade pip
            self.install_progress.append("📥 Installing pip...")
            subprocess.run(['sudo', 'apt', 'install', '-y', 'python3-pip'], check=True)
            
            # Upgrade pip
            self.install_progress.append("⬆️ Upgrading pip...")
            subprocess.run(['python3', '-m', 'pip', 'install', '--upgrade', '--user', 'pip'], check=True)
            
            # Verify installation
            result = subprocess.run(['python3', '-m', 'pip', '--version'], capture_output=True, text=True, check=True)
            version = result.stdout.split()[1] if result.stdout else "unknown"
            self.install_progress.append(f"✅ Pip installed successfully: version {version}")
            
            # Re-enable buttons
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)
            
            # Refresh checks
            self.check_setup_dependencies()
            
        except subprocess.CalledProcessError as e:
            self.install_progress.append(f"❌ Pip installation failed: {str(e)}")
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)
    
    def _create_virtual_environment(self):
        """Create virtual environment for setup tab"""
        try:
            venv_path = os.path.join(self.script_dir, '.venv')
            
            # Check if python3 and venv are available
            result = subprocess.run(['python3', '-m', 'venv', '--help'], capture_output=True)
            if result.returncode != 0:
                self.install_progress.append("❌ Python 3 venv module not available. Install python3-venv first.")
                return
            
            # Check if environment already exists and is functional
            if os.path.exists(venv_path):
                venv_python = os.path.join(venv_path, 'bin', 'python')
                if os.path.exists(venv_python):
                    try:
                        # Test if the existing venv works
                        result = subprocess.run([venv_python, '--version'], capture_output=True, timeout=5)
                        if result.returncode == 0:
                            self.install_progress.append("✅ Virtual environment already exists and is functional!")
                            # Re-enable buttons and refresh checks
                            self.install_setup_python_btn.setEnabled(True)
                            self.install_setup_pip_btn.setEnabled(True)
                            self.install_setup_venv_btn.setEnabled(True)
                            self.check_setup_dependencies()
                            return
                    except:
                        pass
            
            self.install_progress.append(f"🏠 Creating virtual environment at: {venv_path}")
            
            # Remove existing venv if it exists but is broken
            if os.path.exists(venv_path):
                self.install_progress.append("🗑️ Removing existing virtual environment...")
                subprocess.run(['rm', '-rf', venv_path], check=True)
            
            # Create new virtual environment
            subprocess.run(['python3', '-m', 'venv', venv_path], check=True)
            
            # Verify creation
            venv_python = os.path.join(venv_path, 'bin', 'python')
            if os.path.exists(venv_python):
                self.install_progress.append("✅ Virtual environment created successfully!")
                
                # Upgrade pip in venv
                self.install_progress.append("⬆️ Upgrading pip in virtual environment...")
                subprocess.run([venv_python, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
                
            else:
                raise Exception("Virtual environment creation failed")
            
            # Re-enable buttons
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)
            
            # Refresh checks
            self.check_setup_dependencies()
            
        except subprocess.CalledProcessError as e:
            self.install_progress.append(f"❌ Virtual environment creation failed: {str(e)}")
            self.install_setup_python_btn.setEnabled(True)
            self.install_setup_pip_btn.setEnabled(True)
            self.install_setup_venv_btn.setEnabled(True)

    def auto_scroll_prereq_progress(self):
        """Auto-scroll the prerequisites progress text to the bottom when new content is added"""
        # Get the scroll bar of the QTextEdit
        scrollbar = self.prereq_progress.verticalScrollBar()
        # Move to the maximum (bottom) position
        scrollbar.setValue(scrollbar.maximum())
    
    def auto_scroll_install_progress(self):
        """Auto-scroll the setup/install progress text to the bottom when new content is added"""
        scrollbar = self.install_progress.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def auto_scroll_docker_progress(self):
        """Auto-scroll the docker progress text to the bottom when new content is added"""
        scrollbar = self.docker_progress.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def auto_scroll_logs_display(self):
        """Auto-scroll the logs display to the bottom when new content is added"""
        scrollbar = self.logs_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    
    def check_system_prerequisites(self):
        """Check the system-level prerequisites for Frigate"""
        try:
            # Check Git
            result = subprocess.run(['git', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.prereq_git_check.setText("✅ Installed")
                self.prereq_git_check.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                self.install_git_btn.setVisible(False)
            else:
                self.prereq_git_check.setText("❌ Not Installed")
                self.prereq_git_check.setStyleSheet("background: #fbeaea; color: #6b3737;")
                self.install_git_btn.setVisible(True)
            
            # Check build-essential (for DKMS and other build tools)
            result = subprocess.run(['dpkg', '-l', 'build-essential'], capture_output=True)
            if result.returncode == 0:
                self.prereq_build_check.setText("✅ Installed")
                self.prereq_build_check.setStyleSheet("background: #e8f4f0; color: #2d5a4a;")
                self.install_build_btn.setVisible(False)
            else:
                self.prereq_build_check.setText("❌ Not Installed")
                self.prereq_build_check.setStyleSheet("background: #fbeaea; color: #6b3737;")
                self.install_build_btn.setVisible(True)
            
        except Exception as e:
            self.prereq_progress.append(f"❌ Error checking prerequisites: {str(e)}")
    
    def install_system_prereq(self, install_type):
        """Install a system prerequisite (git, python, or build-tools)"""
        # Get sudo password from user
        install_names = {
            'git': 'Git',
            'build-tools': 'Build Tools'
        }
        
        sudo_password = PasswordDialog.get_sudo_password(self, f"{install_names[install_type]} installation")
        if sudo_password is None:
            self.prereq_progress.append(f"❌ {install_names[install_type]} installation cancelled - password required")
            return
        
        # Disable all install buttons during installation
        self.install_git_btn.setEnabled(False)
        self.install_build_btn.setEnabled(False)
        
        # Clear progress and show starting message
        self.prereq_progress.clear()
        
        self.prereq_progress.append(f"🚀 Starting {install_names[install_type]} installation...")
        
        # Create and start worker thread with password
        self.system_prereq_worker = SystemPrereqInstallWorker(self.script_dir, install_type, sudo_password)
        self.system_prereq_worker.progress.connect(self.prereq_progress.append)
        self.system_prereq_worker.finished.connect(self.on_system_prereq_install_finished)
        self.system_prereq_worker.start()
    
    def on_system_prereq_install_finished(self, success):
        """Handle completion of system prerequisite installation"""
        # Re-enable install buttons
        self.install_git_btn.setEnabled(True)
        self.install_build_btn.setEnabled(True)
        
        if success:
            self.prereq_progress.append("✅ Installation completed successfully!")
            # Refresh the status checks
            self.check_system_prerequisites()
        else:
            self.prereq_progress.append("❌ Installation failed. Please check the error messages above.")
    
    def check_docker_prereq_status(self):
        """Check the Docker installation and service status"""
        try:
            status_lines = []
            docker_installed = False
            docker_accessible = False
            
            # Check if Docker is installed
            result = subprocess.run(['which', 'docker'], capture_output=True, text=True)
            if result.returncode == 0:
                docker_installed = True
                
                # Get Docker version
                try:
                    version_check = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
                    if version_check.returncode == 0:
                        docker_accessible = True
                        version_info = version_check.stdout.strip()
                        status_lines.append(f"✅ {version_info}")
                        
                        # Check Docker service status
                        service_check = subprocess.run(['systemctl', 'is-active', 'docker'], 
                                                     capture_output=True, text=True)
                        if service_check.returncode == 0:
                            status_lines.append("✅ Service: Active")
                        else:
                            status_lines.append("⚠️ Service: Inactive")
                        
                    else:
                        status_lines.append("❌ Docker installed but not accessible")
                        status_lines.append("💡 Try: logout and login again")
                        
                except subprocess.TimeoutExpired:
                    status_lines.append("⏰ Docker not responding")
                    status_lines.append("💡 Try: sudo systemctl restart docker")
            else:
                status_lines.append("❌ Docker not installed")
                status_lines.append("💡 Click 'Install Docker' below")
            
            # Set the status text
            status_text = '\n'.join(status_lines)
            self.prereq_docker_status.setText(status_text)
            
            # Set style based on overall status
            if docker_installed and docker_accessible:
                self.prereq_docker_status.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 8px; border-radius: 6px;")
                self.install_docker_prereq_btn.setVisible(False)
            elif docker_installed:
                self.prereq_docker_status.setStyleSheet("background: #fff3cd; color: #856404; padding: 8px; border-radius: 6px;")
                self.install_docker_prereq_btn.setVisible(False)
            else:
                self.prereq_docker_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
                self.install_docker_prereq_btn.setVisible(True)
        
        except Exception as e:
            self.prereq_progress.append(f"❌ Error checking Docker status: {str(e)}")
            self.prereq_docker_status.setText(f"❌ Error checking Docker: {str(e)}")
            self.prereq_docker_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
            self.install_docker_prereq_btn.setVisible(True)
    
    def check_memryx_prereq_status(self):
        """Check the MemryX driver and runtime installation status"""
        try:
            # Check if MemryX devices exist
            devices = [d for d in glob.glob("/dev/memx*") if "_feature" not in d]
            device_count = len(devices)
            
            # Helper function to get package version
            def get_package_version(package_name):
                """Get the installed version of a package using apt policy"""
                try:
                    result = subprocess.run(['apt', 'policy', package_name], capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'Installed:' in line:
                                version = line.split('Installed:')[1].strip()
                                if version and version != '(none)':
                                    # Extract just the version number (e.g., "2.0.1" from "2.0.1-1ubuntu1")
                                    version_parts = version.split('-')[0].split('+')[0]
                                    return version_parts
                except:
                    pass
                return None
            
            # Check if memx-drivers package is installed
            drivers_result = subprocess.run(['dpkg', '-l', 'memx-drivers'], capture_output=True, text=True)
            drivers_installed = drivers_result.returncode == 0
            drivers_version = get_package_version('memx-drivers') if drivers_installed else None
            
            # Check if mxa-manager package is installed
            manager_result = subprocess.run(['dpkg', '-l', 'mxa-manager'], capture_output=True, text=True)
            manager_installed = manager_result.returncode == 0
            manager_version = get_package_version('mxa-manager') if manager_installed else None
            
            # Check if memx-accl package is installed
            accl_result = subprocess.run(['dpkg', '-l', 'memx-accl'], capture_output=True, text=True)
            accl_installed = accl_result.returncode == 0
            accl_version = get_package_version('memx-accl') if accl_installed else None
            
            if not drivers_installed:
                self.prereq_memryx_status.setText("❌ MemryX drivers not installed")
                self.prereq_memryx_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
                self.install_memryx_prereq_btn.setVisible(True)
                self.install_memryx_prereq_btn.setEnabled(True)
                self.restart_system_btn.setVisible(False)  # Hide restart button
                self.memryx_prereq_guidance.setText(
                    "⚠️ MemryX drivers are not installed. Click 'Install MemryX Drivers & Runtime' to "
                    "automatically install the MemryX drivers and runtime components required for hardware acceleration."
                )
                return
            
            if device_count == 0:
                drivers_text = "drivers installed"
                if drivers_version:
                    drivers_text += f" (v{drivers_version})"
                self.prereq_memryx_status.setText(f"⚠️ MemryX {drivers_text} but no devices detected, restart required")
                self.prereq_memryx_status.setStyleSheet("background: #fdf6e3; color: #8b7355; padding: 8px; border-radius: 6px;")
                self.install_memryx_prereq_btn.setVisible(False)
                self.restart_system_btn.setVisible(True)  # Show restart button
                self.memryx_prereq_guidance.setText(
                    "💡 MemryX drivers are installed but no devices are detected.\n"
                    "A system restart is required for the drivers to take effect.\n\n"
                    "Click 'Restart System Now' to restart your computer and activate the MemryX drivers.\n\n"
                    "If devices are still not detected after restart:\n"
                    "• Check that MemryX hardware is properly connected\n"
                    "• Verify hardware compatibility"
                )
                return
            
            if not (manager_installed and accl_installed):
                missing_packages = []
                if not manager_installed:
                    missing_packages.append("mxa-manager")
                if not accl_installed:
                    missing_packages.append("memx-accl")
                
                self.prereq_memryx_status.setText(f"⚠️ Missing runtime packages: {', '.join(missing_packages)}")
                self.prereq_memryx_status.setStyleSheet("background: #fdf6e3; color: #8b7355; padding: 8px; border-radius: 6px;")
                self.install_memryx_prereq_btn.setVisible(True)
                self.install_memryx_prereq_btn.setEnabled(True)
                self.restart_system_btn.setVisible(False)  # Hide restart button
                self.memryx_prereq_guidance.setText(
                    f"💡 MemryX drivers installed but missing runtime packages: {', '.join(missing_packages)}\n"
                    "Click 'Install MemryX Drivers & Runtime' to complete the installation."
                )
                return
            
            # Everything looks good - show version information
            status_text = f"✅ MemryX fully installed and operational\n"
            status_text += f"Devices detected: {device_count}\n"
            
            # Show drivers with version
            drivers_text = "✅ memx-drivers"
            if drivers_version:
                drivers_text += f" (v{drivers_version})"
            status_text += f"Drivers: {drivers_text}\n"
            
            # Show runtime with versions
            runtime_parts = []
            if manager_installed:
                manager_text = "mxa-manager"
                if manager_version:
                    manager_text += f" (v{manager_version})"
                runtime_parts.append(manager_text)
            
            if accl_installed:
                accl_text = "memx-accl"
                if accl_version:
                    accl_text += f" (v{accl_version})"
                runtime_parts.append(accl_text)
            
            status_text += f"Runtime: ✅ {', '.join(runtime_parts)}"
            
            self.prereq_memryx_status.setText(status_text)
            self.prereq_memryx_status.setStyleSheet("background: #e8f4f0; color: #2d5a4a; padding: 8px; border-radius: 6px;")
            self.install_memryx_prereq_btn.setVisible(False)
            self.restart_system_btn.setVisible(False)  # Hide restart button when everything is working
            self.memryx_prereq_guidance.setText(
                "✅ MemryX is ready for use. Hardware acceleration is available for Frigate."
            )
            
        except Exception as e:
            self.prereq_memryx_status.setText(f"❌ Error checking MemryX: {str(e)}")
            self.prereq_memryx_status.setStyleSheet("background: #fbeaea; color: #6b3737; padding: 8px; border-radius: 6px;")
            self.install_memryx_prereq_btn.setVisible(True)
            self.install_memryx_prereq_btn.setEnabled(True)
            self.restart_system_btn.setVisible(False)  # Hide restart button on error
            self.memryx_prereq_guidance.setText(
                "❓ Could not determine MemryX status. You may need to install MemryX drivers."
            )
    
    def install_docker_prereq(self):
        """Install Docker for Prerequisites tab"""
        reply = QMessageBox.question(
            self, "Install Docker", 
            "This will install Docker CE from scratch on your system.\n\n"
            "The installation process will:\n"
            "• Update package repositories\n"
            "• Install Docker CE and related components\n"
            "• Start and enable Docker service\n"
            "• Add your user to the docker group\n\n"
            "This requires sudo privileges and may take several minutes.\n\n"
            "Continue with Docker installation?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Get sudo password from user
        sudo_password = PasswordDialog.get_sudo_password(self, "Docker installation")
        if sudo_password is None:
            self.prereq_progress.append("❌ Docker installation cancelled - password required")
            return
        
        # Disable the install button during operation
        self.install_docker_prereq_btn.setEnabled(False)
        self.install_docker_prereq_btn.setText("🔄 Installing Docker...")
        
        # Start Docker installation worker with password
        self.docker_install_worker = DockerInstallWorker(self.script_dir, sudo_password)
        self.docker_install_worker.progress.connect(self.prereq_progress.append)
        self.docker_install_worker.finished.connect(self.on_docker_prereq_install_finished)
        self.docker_install_worker.start()
    
    def on_docker_prereq_install_finished(self, success):
        """Handle Docker installation completion for Prerequisites tab"""
        # Re-enable the install button
        self.install_docker_prereq_btn.setEnabled(True)
        self.install_docker_prereq_btn.setText("🐳 Install Docker from Scratch")
        
        if success:
            self.prereq_progress.append("🎉 Docker installation completed successfully!")
            QMessageBox.information(
                self, "Docker Installation Complete", 
                "✅ Docker has been installed successfully!\n\n"
                "Please log out and log back in for group permissions to take effect.\n"
                "After re-login, Docker will be ready for use."
            )
        else:
            self.prereq_progress.append("💡 Please check the error messages above.")
            QMessageBox.warning(
                self, "Docker Installation Failed", 
                "❌ Docker installation failed. Please check the progress log for details.\n\n"
                "You may need to install Docker manually or resolve any system issues."
            )
        
        # Refresh Docker status
        self.check_docker_prereq_status()
        self.check_system_prerequisites()
    
    def install_memryx_prereq(self):
        """Install MemryX for Prerequisites tab"""
        reply = QMessageBox.question(
            self, "Install MemryX", 
            "This will install MemryX drivers and runtime on your system.\n\n"
            "The installation process will:\n"
            "• Remove any existing MemryX installations\n"
            "• Install kernel headers and DKMS\n"
            "• Add MemryX repository and GPG key\n"
            "• Install memx-drivers (requires restart after)\n"
            "• Install memx-accl and mxa-manager runtime\n"
            "• Run ARM setup if on ARM architecture\n\n"
            "This requires sudo privileges and may take several minutes.\n"
            "A system restart will be required after driver installation.\n\n"
            "Continue with MemryX installation?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Get sudo password from user
        sudo_password = PasswordDialog.get_sudo_password(self, "MemryX installation")
        if sudo_password is None:
            self.prereq_progress.append("❌ MemryX installation cancelled - password required")
            return
        
        # Disable the install button during operation
        self.install_memryx_prereq_btn.setEnabled(False)
        self.install_memryx_prereq_btn.setText("🔄 Installing MemryX...")
        
        # Start MemryX installation worker with password
        self.memryx_install_worker = MemryXInstallWorker(self.script_dir, sudo_password)
        self.memryx_install_worker.progress.connect(self.prereq_progress.append)
        self.memryx_install_worker.finished.connect(self.on_memryx_prereq_install_finished)
        self.memryx_install_worker.start()
    
    def on_memryx_prereq_install_finished(self, success):
        """Handle MemryX installation completion for Prerequisites tab"""
        # Re-enable the install button
        self.install_memryx_prereq_btn.setEnabled(True)
        self.install_memryx_prereq_btn.setText("🧠 Install MemryX Drivers & Runtime")
        
        if success:
            self.prereq_progress.append("🎉 MemryX installation completed successfully!")
            
            # Check if restart is needed by checking for devices
            devices = [d for d in glob.glob("/dev/memx*") if "_feature" not in d]
            device_count = len(devices)
            
            if device_count == 0:
                # No devices detected, restart is needed
                QMessageBox.information(
                    self, "MemryX Installation Complete", 
                    "✅ MemryX drivers and runtime have been installed successfully!\n\n"
                    "IMPORTANT: You must restart your computer now for the drivers to take effect.\n\n"
                    "After restart:\n"
                    "• MemryX devices should be detected\n"
                    "• Hardware acceleration will be available\n"
                    "• Frigate can use MemryX for AI inference\n\n"
                    "The 'Restart System Now' button is now available for your convenience."
                )
            else:
                # Devices already detected (unusual but possible)
                QMessageBox.information(
                    self, "MemryX Installation Complete", 
                    "✅ MemryX drivers and runtime have been installed successfully!\n\n"
                    "MemryX devices are already detected and ready for use.\n"
                    "Hardware acceleration is now available for Frigate."
                )
        else:
            self.prereq_progress.append("💡 Please check the error messages above.")
            QMessageBox.warning(
                self, "MemryX Installation Failed", 
                "❌ MemryX installation failed. Please check the progress log for details.\n\n"
                "Common issues:\n"
                "• Missing kernel headers\n"
                "• Network connectivity problems\n"
                "• Unsupported system configuration\n\n"
                "You may need to install MemryX manually or resolve system issues."
            )
        
        # Refresh MemryX status
        self.check_memryx_prereq_status()
        self.check_system_prerequisites()

    def restart_system(self):
        """Restart the system after confirming with user"""
        reply = QMessageBox.question(
            self, "Restart System", 
            "This will restart your computer to activate the MemryX drivers.\n\n"
            "⚠️ IMPORTANT:\n"
            "• Save any open work before proceeding\n"
            "• Close all applications\n"
            "• Make sure no important processes are running\n\n"
            "After restart, MemryX devices should be detected and available for use.\n\n"
            "Do you want to restart your computer now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # Default to No for safety
        )
        
        if reply == QMessageBox.Yes:
            # Get sudo password for restart
            sudo_password = PasswordDialog.get_sudo_password(self, "system restart")
            if sudo_password is None:
                self.prereq_progress.append("❌ System restart cancelled - password required")
                return
            
            try:
                self.prereq_progress.append("🔄 Initiating system restart...")
                self.prereq_progress.append("💾 Please save any open work before the restart completes.")
                
                # Store password for _perform_restart
                self.restart_sudo_password = sudo_password
                
                # Give user a few seconds to see the message
                QTimer.singleShot(2000, self._perform_restart)
                
            except Exception as e:
                self.prereq_progress.append(f"❌ Error initiating restart: {str(e)}")
                QMessageBox.warning(
                    self, "Restart Failed", 
                    f"❌ Could not restart the system automatically: {str(e)}\n\n"
                    "Please restart your computer manually:\n"
                    "• Open terminal and run: sudo reboot\n"
                    "• Or use your system's restart option"
                )
    
    def _perform_restart(self):
        """Actually perform the system restart"""
        try:
            # Show final warning
            QMessageBox.information(
                self, "Restarting Now", 
                "🔄 Your computer will restart in a few seconds.\n\n"
                "The Frigate Launcher will start automatically after restart.\n"
                "MemryX devices should be detected and ready for use.",
                QMessageBox.Ok
            )
            
            # Perform the restart with sudo password
            if hasattr(self, 'restart_sudo_password') and self.restart_sudo_password:
                # Use sudo -S to read password from stdin
                sudo_cmd = ['sudo', '-S', 'reboot']
                result = subprocess.run(sudo_cmd, input=f"{self.restart_sudo_password}\n", 
                                      text=True, check=True, capture_output=True)
                self.prereq_progress.append("✅ Restart command executed successfully")
            else:
                # Fallback to normal sudo (will prompt for password)
                subprocess.run(['sudo', 'reboot'], check=True)
            
        except subprocess.CalledProcessError as e:
            self.prereq_progress.append(f"❌ Restart command failed: {str(e)}")
            if e.stderr:
                self.prereq_progress.append(f"   Error details: {e.stderr}")
            QMessageBox.warning(
                self, "Restart Failed", 
                "❌ Could not restart the system.\n\n"
                "Please restart your computer manually:\n"
                "• Open terminal and run: sudo reboot\n"
                "• Or use your system's restart option"
            )
        except Exception as e:
            self.prereq_progress.append(f"❌ Unexpected error during restart: {str(e)}")
            QMessageBox.warning(
                self, "Restart Error", 
                f"❌ Unexpected error: {str(e)}\n\n"
                "Please restart your computer manually."
            )
        finally:
            # Clean up the stored password
            if hasattr(self, 'restart_sudo_password'):
                self.restart_sudo_password = None

    def run_sudo_command(self, command, description):
        """Run a sudo command with password authentication"""
        try:
            self.progress.emit(description)
            
            if self.sudo_password:
                # Use sudo -S to read password from stdin (safer than shell=True)
                sudo_cmd = ['sudo', '-S'] + command[1:]  # Remove 'sudo' from original command
                password_input = f"{self.sudo_password}\n"
                result = subprocess.run(sudo_cmd, input=password_input, text=True, 
                                      check=True, capture_output=True)
            else:
                # Fallback to regular sudo (will fail if no terminal)
                result = subprocess.run(command, check=True, capture_output=True, text=True)
            
            return True
        except subprocess.CalledProcessError as e:
            self.progress.emit(f"❌ Error in {description}: {e}")
            if e.stderr:
                self.progress.emit(f"Error details: {e.stderr}")
            return False
        except Exception as e:
            self.progress.emit(f"❌ Unexpected error in {description}: {e}")
            return False

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MemryX + Frigate Launcher")
    app.setApplicationVersion("1.0.0")
    
    # Apply system palette for better integration
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(248, 249, 250))
    palette.setColor(QPalette.WindowText, QColor(73, 80, 87))
    app.setPalette(palette)
    
    window = FrigateLauncher()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
