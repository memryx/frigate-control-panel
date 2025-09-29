# Frigate Control Panel

A comprehensive GUI application for managing Frigate + MemryX installations, configuration, and monitoring.

## Features

🚀 **One-click Frigate installation**  
⚙️ **Simple and advanced camera configuration**  
🐳 **Docker management integration**  
🔧 **System monitoring and diagnostics**  
📱 **User-friendly interface**  

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/memryx/frigate-control-panel.git
cd frigate-control-panel
```

### 2. Make Launch Script Executable
```bash
chmod +x launch.sh
```

### 3. Launch the Application
```bash
./launch.sh
```

That's it! The launcher will automatically:
- Set up the Python environment
- Install required dependencies (PySide6, PyYAML)
- Create desktop shortcuts
- Launch the control panel

## System Requirements

- **OS**: Linux (Ubuntu/Debian recommended)
- **Python**: 3.8 or higher
- **Hardware**: MemryX acceleration cards (optional but recommended)
- **Dependencies**: Automatically installed by launcher

## Usage

The control panel provides three main tabs:

- **📦 PreConfigured Box**: Quick camera setup and Frigate control
- **🔧 Manual Setup**: Step-by-step installation (Prerequisites + Frigate Setup)
- **⚙️ Advanced Settings**: Configuration editing and Docker logs monitoring

## Desktop Integration

The first run automatically creates:
- Desktop shortcuts for easy access
- Application menu entries
- Proper system integration

## Configuration

Camera configurations and Frigate settings are automatically saved to:
```
./frigate/config/config.yaml
```

## Troubleshooting

If you encounter issues:

1. **Permission errors**: Ensure `launch.sh` is executable
2. **Missing dependencies**: Re-run `./launch.sh` to reinstall
3. **GUI not starting**: Check Python and PySide6 installation

## Support

For detailed Frigate configuration options, visit:
- [Frigate Documentation](https://docs.frigate.video/)
- [MemryX Documentation](https://developer.memryx.com/)

## License

This project is licensed under the terms specified in the LICENSE file.