#!/bin/bash
# ============================================================================
# Quick PlatformIO Setup and Test Script for MX5-Telemetry (Linux/Mac)
# ============================================================================

echo "=========================================="
echo "MX5-Telemetry PlatformIO Quick Start"
echo "=========================================="
echo

# Check if PlatformIO CLI is installed
if ! command -v pio &> /dev/null; then
    echo "ERROR: PlatformIO CLI not found!"
    echo
    echo "Please install PlatformIO:"
    echo "  1. In VS Code: Install 'PlatformIO IDE' extension"
    echo "  2. OR install CLI: pip install platformio"
    echo
    exit 1
fi

echo "[✓] PlatformIO CLI found!"
echo

# Menu function
show_menu() {
    echo "What would you like to do?"
    echo
    echo "  1. Install libraries and build project"
    echo "  2. Run unit tests (simulation)"
    echo "  3. Build and upload to Arduino Nano"
    echo "  4. Build for Wokwi simulator"
    echo "  5. Open serial monitor"
    echo "  6. Clean build files"
    echo "  0. Exit"
    echo
}

# Main loop
while true; do
    show_menu
    read -p "Select option (0-6): " choice
    echo
    
    case $choice in
        1)
            echo "=========================================="
            echo "Building MX5-Telemetry for Arduino Nano"
            echo "=========================================="
            echo
            pio lib install
            pio run -e nano_atmega328
            if [ $? -eq 0 ]; then
                echo
                echo "[✓] Build successful!"
            else
                echo
                echo "[✗] Build failed! Check errors above."
            fi
            echo
            read -p "Press Enter to continue..."
            ;;
        2)
            echo "=========================================="
            echo "Running Unit Tests"
            echo "=========================================="
            echo
            pio test -e native_sim -v
            if [ $? -eq 0 ]; then
                echo
                echo "[✓] All tests passed!"
            else
                echo
                echo "[✗] Some tests failed! Check output above."
            fi
            echo
            read -p "Press Enter to continue..."
            ;;
        3)
            echo "=========================================="
            echo "Building and Uploading to Arduino Nano"
            echo "=========================================="
            echo
            echo "Make sure Arduino Nano is connected via USB!"
            echo
            read -p "Press Enter to continue..."
            pio run -e nano_atmega328 --target upload
            if [ $? -eq 0 ]; then
                echo
                echo "[✓] Upload successful!"
                echo
                read -p "Open serial monitor? (y/n): " monitor
                if [ "$monitor" = "y" ] || [ "$monitor" = "Y" ]; then
                    pio device monitor --baud 115200
                fi
            else
                echo
                echo "[✗] Upload failed! Check connection and try again."
                read -p "Press Enter to continue..."
            fi
            ;;
        4)
            echo "=========================================="
            echo "Building for Wokwi Simulator"
            echo "=========================================="
            echo
            pio run -e wokwi_sim
            if [ $? -eq 0 ]; then
                echo
                echo "[✓] Build successful!"
                echo
                echo "To start simulation:"
                echo "  1. Install Wokwi extension in VS Code"
                echo "  2. Press F1 and type 'Wokwi: Start Simulator'"
                echo "  3. OR click 'Start Simulation' in Wokwi panel"
            else
                echo
                echo "[✗] Build failed! Check errors above."
            fi
            echo
            read -p "Press Enter to continue..."
            ;;
        5)
            echo "=========================================="
            echo "Opening Serial Monitor (115200 baud)"
            echo "=========================================="
            echo
            echo "Press Ctrl+C to exit monitor"
            echo
            sleep 2
            pio device monitor --baud 115200
            ;;
        6)
            echo "=========================================="
            echo "Cleaning Build Files"
            echo "=========================================="
            echo
            pio run --target cleanall
            echo "[✓] Clean complete!"
            echo
            read -p "Press Enter to continue..."
            ;;
        0)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            echo
            ;;
    esac
done
