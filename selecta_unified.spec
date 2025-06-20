# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Get the directory containing this spec file
spec_root = Path(SPECPATH)

block_cipher = None

# Data files to include
datas = [
    # AI Models
    ('hierarchical_*_20250617_155623.pkl', '.'),
    ('hierarchical_*_20250617_155623.json', '.'),
    
    # Python modules that might be needed
    ('library_manager.py', '.'),
    ('audio_player.py', '.'),
    ('selecta_desktop_app_enhanced.py', '.'),
    ('hierarchical_classifier.py', '.'),
]

# Hidden imports for libraries that PyInstaller might miss
hiddenimports = [
    'sklearn',
    'sklearn.ensemble',
    'sklearn.preprocessing',
    'sklearn.model_selection',
    'librosa',
    'librosa.feature',
    'librosa.core',
    'pygame',
    'pygame.mixer',
    'soundfile',
    'numpy',
    'scipy',
    'scipy.signal',
    'joblib',
    'tkinter',
    'tkinter.ttk',
    'sqlite3',
    'threading',
    'queue',
    'json',
    'pathlib',
]

a = Analysis(
    ['selecta_unified_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SelectaUnified',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo/selecta.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SelectaUnified',
)

# macOS App Bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Selecta Unified.app',
        icon='assets/logo/selecta.icns',
        bundle_identifier='com.selecta.unified',
        info_plist={
            'CFBundleName': 'Selecta Unified',
            'CFBundleDisplayName': 'Selecta Unified',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleIdentifier': 'com.selecta.unified',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription': 'Selecta needs microphone access for audio analysis.',
            'NSAppleEventsUsageDescription': 'Selecta needs AppleEvents access for system integration.',
        },
    )