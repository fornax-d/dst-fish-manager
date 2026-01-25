#!/usr/bin/env fish

# --- INFO ---
# This script installs the necessary configuration files and scripts for the
# Don't Starve Together server manager into the user's home directory.
#
# It copies:
# - systemd service files to ~/.config/systemd/user/
# - Don't Starve configuration to ~/.config/dontstarve/
# - Executable scripts to ~/.local/bin/
#
# After copying, it makes the scripts executable and reloads the systemd
# user daemon to apply the changes.
# ---

echo "Starting installation..."

# Get the directory where the script is located
set SOURCE_DIR (dirname (status --current-filename))

# Define destination directories
set DEST_SYSTEMD_USER_DIR "$HOME/.config/systemd/user"
set DEST_DONTSTARVE_CONFIG_DIR "$HOME/.config/dontstarve"
set DEST_LOCAL_BIN_DIR "$HOME/.local/bin"

# Create destination directories if they don't exist
echo "Creating destination directories..."
mkdir -p "$DEST_SYSTEMD_USER_DIR"
mkdir -p "$DEST_DONTSTARVE_CONFIG_DIR"
mkdir -p "$DEST_LOCAL_BIN_DIR"

# --- Copy systemd files ---
echo "Installing systemd service files..."
cp -v "$SOURCE_DIR/config/systemd/user/dontstarve.target" "$DEST_SYSTEMD_USER_DIR/"
cp -v "$SOURCE_DIR/config/systemd/user/dontstarve@.service" "$DEST_SYSTEMD_USER_DIR/"

# --- Copy Don't Starve config files ---
echo "Installing Don't Starve configuration files..."
cp -v "$SOURCE_DIR/config/dontstarve/config" "$DEST_DONTSTARVE_CONFIG_DIR/"
cp -v "$SOURCE_DIR/config/dontstarve/shards.conf" "$DEST_DONTSTARVE_CONFIG_DIR/"


# --- Copy executable scripts ---
echo "Installing executable scripts..."
cp -v "$SOURCE_DIR/local/bin/dst-server" "$DEST_LOCAL_BIN_DIR/"
cp -v "$SOURCE_DIR/local/bin/dst-tui" "$DEST_LOCAL_BIN_DIR/"
cp -v "$SOURCE_DIR/local/bin/dst-updater" "$DEST_LOCAL_BIN_DIR/"

# --- Set permissions ---
echo "Setting executable permissions..."
chmod +x "$DEST_LOCAL_BIN_DIR/dst-server"
chmod +x "$DEST_LOCAL_BIN_DIR/dst-tui"
chmod +x "$DEST_LOCAL_BIN_DIR/dst-updater"

# --- Add ~/.local/bin to PATH in config.fish ---
echo "Updating fish PATH configuration..."
set FISH_CONFIG_PATH "$HOME/.config/fish/config.fish"
set LINE_TO_ADD "fish_add_path ~/.local/bin"

# Ensure the config directory and file exist
mkdir -p (dirname "$FISH_CONFIG_PATH")
and touch "$FISH_CONFIG_PATH"

# Check if the line already exists and add it if it doesn't
if not grep -q --fixed-strings "$LINE_TO_ADD" "$FISH_CONFIG_PATH"
    echo "Adding ~/.local/bin to fish path in $FISH_CONFIG_PATH"
    echo "$LINE_TO_ADD" >> "$FISH_CONFIG_PATH"
else
    echo "~/.local/bin already in fish path."
end

# --- Reload systemd ---
echo "Reloading systemd user daemon..."
systemctl --user daemon-reload

echo "\nInstallation complete!"
echo "You can now use the scripts from your terminal."
