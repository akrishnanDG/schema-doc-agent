#!/bin/bash
# Install Schema Documentation Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🤖 Installing Schema Documentation Agent..."

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install --user -r "$SCRIPT_DIR/requirements.txt"

# Create symlink in user's local bin
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

# Remove old symlink if exists
rm -f "$INSTALL_DIR/schema-doc-agent"

# Create new symlink
ln -s "$SCRIPT_DIR/schema-doc-agent" "$INSTALL_DIR/schema-doc-agent"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Make sure ~/.local/bin is in your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Then run:"
echo "  schema-doc-agent --help"

