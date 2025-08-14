# InDesign Writer Helper

A professional text management tool for Adobe InDesign that allows you to view, navigate, and edit text frames in your documents through a web-based interface.

## Features

- **Auto-detect InDesign**: Automatically detects and connects to running InDesign instances
- **Text Frame Viewer**: View all text frames in your document in a large, readable text box
- **Navigation**: Navigate between text frames with Previous/Next buttons
- **Page Filtering**: Filter text frames by page
- **Text Search**: Search for specific text content across all frames
- **Statistics**: View document statistics (total frames, pages, words, characters)
- **Real-time Editing**: Edit text content and save changes back to InDesign
- **Modern UI**: Clean, professional web interface

## Installation

1. Ensure Python 3.13 is installed in the `Apps/_engine` directory
2. The application will automatically install required dependencies on first run
3. Run `__IndesignWriterHelper__.bat` to start the application

## Usage

1. **Start InDesign** and open a document with text frames
2. **Run the application** by double-clicking `__IndesignWriterHelper__.bat`
3. **Connect to InDesign** using the launcher interface
4. **Navigate text frames** using the sidebar and navigation buttons
5. **Edit text** in the large text area and save changes

## File Structure

```
IndesignWriterHelper/
├── __IndesignWriterHelper__.bat    # Main launcher
├── src/
│   ├── check_modules.py            # Module dependency checker
│   ├── get_indesign_version.py     # InDesign detection and connection
│   ├── backend.py                  # Text frame management backend
│   ├── generate_web_app.py         # Full web application (requires http.server)
│   ├── simple_server.py            # Basic HTTP server (socket-based)
│   ├── launcher.html               # Connection launcher interface
│   ├── IndesignWriterHelper.html   # Main application interface
│   └── requirements.txt            # Python dependencies
└── README.md                       # This file
```

## Technical Notes

### Current Status
- ✅ Basic file structure and launcher created
- ✅ InDesign connection module implemented
- ✅ Text frame extraction and management backend
- ✅ Modern web interface with navigation and editing
- ✅ Module dependency checker
- ⚠️ HTTP server implementation (socket module issues in current Python installation)

### Dependencies
- Python 3.13+
- pywin32 (for InDesign COM automation)
- Built-in modules: os, sys, json, logging, threading, time, pathlib, webbrowser, typing

### Future Enhancements
- **AI Integration**: OpenAI-powered text suggestions and modifications
- **Advanced Search**: Regex search, case-sensitive options
- **Batch Operations**: Apply changes to multiple frames
- **Export Features**: Export text content to various formats
- **Style Management**: View and edit text styles
- **Collaboration**: Multi-user editing capabilities

## Troubleshooting

### Python Issues
If you encounter Python module errors:
1. Ensure Python 3.13 is properly installed in `Apps/_engine`
2. Run `check_modules.py` to verify dependencies
3. The application will attempt to install missing modules automatically

### InDesign Connection Issues
1. Make sure InDesign is running and has an open document
2. Try the "Auto Connect" button first
3. If that fails, use "Connect to InDesign" and select a specific version

### Server Issues
If the web server fails to start:
1. Check if port 8081 is available
2. Try restarting the application
3. Check Windows Firewall settings

## Development

The application is built with:
- **Backend**: Python with COM automation for InDesign
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Communication**: HTTP API between frontend and backend
- **Architecture**: Modular design with separate concerns

## License

Part of the EnneadTab ecosystem - Professional tools for design workflows.
