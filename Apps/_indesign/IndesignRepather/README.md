# InDesign Repather

A professional tool for managing InDesign document links and repathing operations.

## Features

- 🔗 **Link Analysis**: Analyze all links in InDesign documents
- 🔄 **Link Repathing**: Repath links from old to new folder locations
- 📁 **Batch Processing**: Process multiple InDesign documents at once
- 👁️ **Preview Mode**: Preview repathing operations before execution
- 🌐 **Web Interface**: Modern web-based user interface
- 🔍 **Version Detection**: Automatic InDesign version detection

## Installation

### Option 1: Standalone Executable (If you do not know python...)

1. The executable `IndesignRepather.exe` is automatically built and committed to this folder by GitHub Actions
2. Simply run `IndesignRepather.exe` from the IndesignRepather folder
3. Follow the on-screen instructions

**Note:** The executable is automatically updated whenever changes are pushed to this folder.

### Option 2: Python Module Execution

#### Prerequisites

- Python 3.8 or higher
- Adobe InDesign installed
- Required Python packages

#### Installation Steps

1. **Run the application:**

   ```bash
   # Direct execution (auto-installs dependencies)
   python Apps/_indesign/IndesignRepather/__main__.py
   ```

   **Note:** Dependencies (pywin32) will be automatically installed when you run the application.

## Usage

1. **Launch the application** using one of the methods above
2. **Connect to InDesign** - The app will automatically detect available InDesign versions
3. **Open a document** - Either open a specific document or connect to an active document
4. **Analyze links** - View all links in your document and their status
5. **Repath links** - Specify old and new folder paths to update link locations
6. **Batch processing** - Process multiple documents at once

## Building from Source

### Local Build

To build the executable locally:

```bash
# Install build dependencies
pip install pyinstaller

# Run the build script from project root
python .github/script/build_indesign_repather_executable.py
```

### Automated Build

The executable is automatically built and committed using GitHub Actions when changes are pushed to the IndesignRepather folder. The workflow:

- Triggers on pushes to `Apps/_indesign/IndesignRepather/**`
- Builds Windows executable using PyInstaller
- **Automatically commits the executable to the IndesignRepather folder**
- Uploads artifacts for download
- Creates releases when tagged

## Project Structure

```
IndesignRepather/
├── __main__.py              # Main entry point for Python execution
├── IndesignRepather.spec    # PyInstaller spec file
├── IndesignRepather.exe     # Auto-built executable (committed by GitHub Actions)
├── README.md               # This file
└── src/                    # Source code directory
    ├── backend.py          # Core InDesign operations
    ├── generate_web_app.py # Web server and API
    ├── get_indesign_version.py # Version detection
    ├── IndesignRepather.html # Web interface
    ├── launcher.html       # Launcher page
    ├── styles.css          # Web interface styles
    ├── sounds/             # Audio feedback files
    └── requirements.txt    # Python dependencies

.github/script/
└── build_indesign_repather_executable.py # Build script for executable
```

## API Endpoints

The web interface provides the following API endpoints:

- `GET /api/status` - Check server status
- `POST /api/get_indesign_versions` - Get available InDesign versions
- `POST /api/connect` - Connect to InDesign
- `POST /api/auto_connect` - Auto-connect to active documents
- `POST /api/open_document` - Open a specific document
- `POST /api/get_links` - Get all links in current document
- `POST /api/repath_links` - Repath links
- `POST /api/preview_repath` - Preview repathing operation
- `POST /api/refresh_links` - Refresh all links
- `POST /api/batch_preview` - Preview batch operation
- `POST /api/batch_repath` - Execute batch repathing

## Troubleshooting

### Common Issues

1. **"InDesign COM not registered"**

   - Ensure InDesign is properly installed
   - Try running as administrator
   - Reinstall InDesign if necessary
2. **"Python module not found"**

   - Ensure you're running from the correct directory
   - Install required dependencies: `pip install pywin32`
3. **"Port 8080 already in use"**

   - Close other applications using port 8080
   - Or modify the port in `generate_web_app.py`
4. **"Access denied"**

   - Run as administrator
   - Check file permissions
   - Ensure documents aren't locked by other applications

### Log Files

The application creates log files for debugging:

- `indesign_repath.log` - Main application log
- Console output for real-time debugging

## Development

### Adding New Features

1. Modify the appropriate source files in `src/`
2. Update the web interface in `src/IndesignRepather.html`
3. Add API endpoints in `src/generate_web_app.py`
4. Test using Python module execution
5. Build and test executable

### Testing

```bash
# Test direct execution
python Apps/_indesign/IndesignRepather/__main__.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of the EnneadTab suite. Please refer to the main project license.

## Support

For issues and support:

1. Check the troubleshooting section above
2. Review log files for error details
3. Open an issue on GitHub with detailed information
4. Include system information and error logs

---

**Note**: This tool requires Adobe InDesign to be installed and properly configured on your system. It uses COM automation to interact with InDesign, which is only available on Windows.
