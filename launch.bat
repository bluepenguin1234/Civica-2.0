@echo off
echo Starting Civica local server...
echo Open your browser to: http://localhost:8080/
echo Press Ctrl+C to stop.
echo.
start "" http://localhost:8080/
python -m http.server 8080
