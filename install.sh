#!/bin/bash

# Smart Fridge IoT Installation Script
# This script automates the installation process

echo "=========================================="
echo "🧊 Smart Fridge IoT Installation"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then 
    echo "✓ Python $python_version found"
else
    echo "✗ Python 3.8+ required. Current version: $python_version"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip
echo "✓ pip upgraded"

# Install requirements
echo ""
echo "Installing Python packages..."
pip install -r requirements.txt
echo "✓ Python packages installed"

# Download YOLO model
echo ""
echo "Downloading YOLO model..."
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
echo "✓ YOLO model downloaded"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p uploads
mkdir -p models
mkdir -p logs
echo "✓ Directories created"

# Test installation
echo ""
echo "Testing installation..."
python test_yolo.py

# Ask about Raspberry Pi setup
echo ""
read -p "Are you installing on Raspberry Pi? (y/n): " is_rpi

if [ "$is_rpi" = "y" ]; then
    echo ""
    echo "Raspberry Pi detected. Installing GPIO packages..."
    
    # Install RPi.GPIO
    pip install RPi.GPIO
    
    # Install DHT sensor library
    pip install Adafruit_DHT
    
    # Install OLED library
    pip install luma.oled
    
    echo "✓ Raspberry Pi packages installed"
    
    # Enable I2C and SPI
    echo ""
    echo "Enabling I2C interface..."
    sudo raspi-config nonint do_i2c 0
    
    echo "Enabling SPI interface..."
    sudo raspi-config nonint do_spi 0
    
    echo "✓ Interfaces enabled"
    
    # Ask about systemd service
    echo ""
    read -p "Install as systemd service (auto-start on boot)? (y/n): " install_service
    
    if [ "$install_service" = "y" ]; then
        # Update service file with correct paths
        sed -i "s|/home/pi/smart-fridge-iot|$(pwd)|g" smart-fridge.service
        sed -i "s|User=pi|User=$USER|g" smart-fridge.service
        
        # Install service
        sudo cp smart-fridge.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable smart-fridge
        
        echo "✓ Systemd service installed"
        echo ""
        echo "Service commands:"
        echo "  Start:   sudo systemctl start smart-fridge"
        echo "  Stop:    sudo systemctl stop smart-fridge"
        echo "  Status:  sudo systemctl status smart-fridge"
        echo "  Logs:    sudo journalctl -u smart-fridge -f"
    fi
fi

# Create startup script
echo ""
echo "Creating startup script..."
cat > start.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python app.py
EOF
chmod +x start.sh
echo "✓ Startup script created (./start.sh)"

# Installation complete
echo ""
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review the configuration in app.py"
echo "2. Start the server:"
echo "   ./start.sh"
echo "   or: source venv/bin/activate && python app.py"
echo ""
echo "3. Open browser: http://localhost:5000"
echo ""
echo "For Raspberry Pi:"
echo "- Test hardware: python raspberry_pi_config.py test"
echo "- Run IoT loop: python raspberry_pi_config.py"
echo ""
echo "Documentation: See README.md for details"
echo "=========================================="
