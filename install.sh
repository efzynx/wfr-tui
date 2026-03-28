#!/bin/bash
set -e

# Define project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting wfr-tui installation..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3 first."
    exit 1
fi

# Go to project directory
cd "$PROJECT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "Virtual environment (.venv) already exists."
fi

# Activate venv and install/update dependencies
echo "Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install textual rich
fi

# Create executable wrapper in ~/.local/bin
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

WRAPPER_PATH="$BIN_DIR/wfr-tui"

echo "Creating wfr-tui command in $BIN_DIR..."

cat > "$WRAPPER_PATH" << 'EOF'
#!/bin/bash
# Auto-generated wrapper for wfr-tui
PROJECT_DIR="LOCAL_PROJECT_DIR"
cd "$PROJECT_DIR"
source .venv/bin/activate
exec python app.py "$@"
EOF

# Replace LOCAL_PROJECT_DIR placeholder with actual path
sed -i "s|LOCAL_PROJECT_DIR|$PROJECT_DIR|g" "$WRAPPER_PATH"

chmod +x "$WRAPPER_PATH"

# Automatically add ~/.local/bin to PATH
echo "Checking shell configuration (bash/zsh/fish)..."

# Detect current shell if possible
SHELL_NAME=$(basename "$SHELL")

update_path() {
    local rc_file="$1"
    local path_cmd="$2"
    if [ -f "$rc_file" ]; then
        if ! grep -q "\$HOME/.local/bin" "$rc_file" && ! grep -q "~/.local/bin" "$rc_file"; then
            echo "" >> "$rc_file"
            echo "# Add ~/.local/bin for wfr-tui executable" >> "$rc_file"
            echo "$path_cmd" >> "$rc_file"
            echo "✅ Added ~/.local/bin to $rc_file"
        fi
    fi
}

# Update for bash
update_path "$HOME/.bashrc" 'export PATH="$HOME/.local/bin:$PATH"'

# Update for zsh
update_path "$HOME/.zshrc" 'export PATH="$HOME/.local/bin:$PATH"'

# Update for fish
if [ -d "$HOME/.config/fish" ] || command -v fish &> /dev/null; then
    mkdir -p "$HOME/.config/fish"
    update_path "$HOME/.config/fish/config.fish" 'fish_add_path ~/.local/bin'
fi

echo ""
echo "=========================================================="
echo "Installation complete!"
echo "You can now run the application with the command:"
echo "    wfr-tui"
echo "from any directory."
echo "=========================================================="
echo "If the 'wfr-tui' command is still not recognized,"
echo "please reload your shell or open a new terminal. For example:"
echo "    source ~/.bashrc  (if using bash)"
echo "    source ~/.zshrc   (if using zsh)"
echo "Or if it's still not recognized, you can add it manually."
