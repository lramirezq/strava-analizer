#!/bin/bash
# Build script for Strava Analyzer desktop app
# Produces: desktop/src-tauri/target/release/bundle/dmg/Strava Analyzer.dmg

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚴 Building Strava Analyzer Desktop App"
echo "========================================="
echo ""

# Step 1: Build Python sidecar with PyInstaller
echo "📦 Step 1: Building Python sidecar..."
cd "$PROJECT_DIR"
source .venv/bin/activate
pyinstaller strava_analyzer.spec --noconfirm --clean
echo "   ✅ Sidecar built: dist/StravaAnalyzer/"
echo ""

# Step 2: Copy sidecar to Tauri bundle location
echo "📋 Step 2: Copying sidecar to Tauri..."
rm -rf "$SCRIPT_DIR/src-tauri/sidecar"
cp -R "$PROJECT_DIR/dist/StravaAnalyzer" "$SCRIPT_DIR/src-tauri/sidecar"
echo "   ✅ Sidecar copied"
echo ""

# Step 3: Install npm dependencies
echo "📦 Step 3: Installing npm dependencies..."
cd "$SCRIPT_DIR"
npm install
echo "   ✅ Dependencies installed"
echo ""

# Step 4: Build Tauri app
echo "🔨 Step 4: Building Tauri app..."
npm run build
echo ""
echo "========================================="
echo "✅ Build complete!"
echo ""
echo "Output:"
ls -lh src-tauri/target/release/bundle/dmg/*.dmg 2>/dev/null || echo "   DMG: check src-tauri/target/release/bundle/"
ls -lh src-tauri/target/release/bundle/macos/*.app 2>/dev/null || echo "   APP: check src-tauri/target/release/bundle/"
