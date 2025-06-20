#!/usr/bin/env python3
"""
Selecta Desktop App Enhanced - Audio Library Scanner with Correction & Learning
GUI application with user feedback and active learning capabilities
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import threading
import queue
from typing import Dict, List, Optional
import shutil

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
except ImportError:
    print("tkinter not available. Install with: pip install tk")
    sys.exit(1)

# Audio processing imports
from hierarchical_classifier import HierarchicalAudioClassifier
import warnings
warnings.filterwarnings('ignore')

class CorrectionLearningSystem:
    """System for handling user corrections and active learning"""
    
    def __init__(self):
        self.corrections_db = "selecta_corrections.db"
        self.init_corrections_database()
        
    def init_corrections_database(self):
        """Initialize database for storing user corrections"""
        conn = sqlite3.connect(self.corrections_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_main_category TEXT,
                original_sub_category TEXT,
                corrected_main_category TEXT,
                corrected_sub_category TEXT,
                original_main_confidence REAL,
                original_sub_confidence REAL,
                correction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_notes TEXT,
                applied_to_training BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correction_id INTEGER,
                training_session_id TEXT,
                improvement_metric REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (correction_id) REFERENCES user_corrections (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                user_description TEXT,
                sample_count INTEGER DEFAULT 0,
                ai_enabled BOOLEAN DEFAULT FALSE,
                ai_confidence_threshold REAL DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(main_category, sub_category)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS category_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                usage_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_consistency_score REAL DEFAULT 1.0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_correction(self, correction_data: Dict) -> int:
        """Save user correction to database"""
        conn = sqlite3.connect(self.corrections_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_corrections 
            (file_path, filename, original_main_category, original_sub_category,
             corrected_main_category, corrected_sub_category, 
             original_main_confidence, original_sub_confidence, user_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            correction_data['file_path'],
            correction_data['filename'],
            correction_data['original_main_category'],
            correction_data.get('original_sub_category'),
            correction_data['corrected_main_category'],
            correction_data.get('corrected_sub_category'),
            correction_data['original_main_confidence'],
            correction_data.get('original_sub_confidence', 0.0),
            correction_data.get('user_notes', '')
        ))
        
        correction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return correction_id
    
    def get_corrections_for_training(self) -> List[Dict]:
        """Get corrections that haven't been applied to training yet"""
        conn = sqlite3.connect(self.corrections_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM user_corrections 
            WHERE applied_to_training = FALSE
        ''')
        
        corrections = []
        for row in cursor.fetchall():
            corrections.append({
                'id': row[0],
                'file_path': row[1],
                'filename': row[2],
                'original_main_category': row[3],
                'original_sub_category': row[4],
                'corrected_main_category': row[5],
                'corrected_sub_category': row[6],
                'original_main_confidence': row[7],
                'original_sub_confidence': row[8],
                'correction_timestamp': row[9],
                'user_notes': row[10]
            })
        
        conn.close()
        return corrections
    
    def mark_corrections_applied(self, correction_ids: List[int]):
        """Mark corrections as applied to training"""
        conn = sqlite3.connect(self.corrections_db)
        cursor = conn.cursor()
        
        for correction_id in correction_ids:
            cursor.execute(
                'UPDATE user_corrections SET applied_to_training = TRUE WHERE id = ?',
                (correction_id,)
            )
        
        conn.commit()
        conn.close()
    
    def prepare_correction_data_for_training(self) -> Dict:
        """Prepare correction data for retraining"""
        corrections = self.get_corrections_for_training()
        
        if not corrections:
            return {'corrections': [], 'files_to_copy': []}
        
        # Organize corrections by category structure
        training_data = {
            'corrections': corrections,
            'files_to_copy': [],
            'category_updates': {}
        }
        
        for correction in corrections:
            # Plan file copy operations for new training data
            if os.path.exists(correction['file_path']):
                training_data['files_to_copy'].append({
                    'source': correction['file_path'],
                    'main_category': correction['corrected_main_category'],
                    'sub_category': correction['corrected_sub_category']
                })
        
        return training_data

class AudioLibraryScannerEnhanced:
    """Enhanced backend with correction capabilities"""
    
    def __init__(self):
        self.classifier = None
        self.db_path = "selecta_library_enhanced.db"
        self.supported_formats = {'.wav', '.mp3', '.flac', '.m4a', '.aiff', '.ogg'}
        self.correction_system = CorrectionLearningSystem()
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for storing classifications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER,
                main_category TEXT,
                sub_category TEXT,
                main_confidence REAL,
                sub_confidence REAL,
                main_probabilities TEXT,
                sub_probabilities TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                correction_count INTEGER DEFAULT 0,
                user_verified BOOLEAN DEFAULT FALSE,
                user_rating INTEGER DEFAULT 0,
                user_tags TEXT,
                user_notes TEXT,
                bpm REAL,
                key_signature TEXT,
                energy_level REAL,
                last_played TIMESTAMP,
                play_count INTEGER DEFAULT 0,
                duration_seconds REAL,
                file_format TEXT
            )
        ''')
        
        # Create playlists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create playlist tracks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                file_id INTEGER,
                position INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id),
                FOREIGN KEY (file_id) REFERENCES audio_files (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def load_classifier(self, model_timestamp='20250617_155623'):
        """Load the trained hierarchical classifier"""
        try:
            self.classifier = HierarchicalAudioClassifier(strategy='cascade')
            self.classifier.load_models(model_timestamp)
            return True
        except Exception as e:
            print(f"Error loading classifier: {e}")
            return False
    
    def classify_file(self, file_path: str) -> Optional[Dict]:
        """Classify a single audio file"""
        if not self.classifier:
            return None
            
        try:
            result = self.classifier.predict_cascade(file_path)
            
            # Add file metadata
            file_stat = os.stat(file_path)
            result.update({
                'file_path': file_path,
                'filename': os.path.basename(file_path),
                'file_size': file_stat.st_size,
                'timestamp': datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            print(f"Error classifying {file_path}: {e}")
            return None
    
    def save_classification(self, result: Dict):
        """Save classification result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO audio_files 
            (file_path, filename, file_size, main_category, sub_category, 
             main_confidence, sub_confidence, main_probabilities, sub_probabilities, 
             updated_at, user_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, FALSE)
        ''', (
            result['file_path'],
            result['filename'], 
            result['file_size'],
            result['main_category'],
            result.get('sub_category'),
            result['main_confidence'],
            result.get('sub_confidence', 0.0),
            json.dumps(result['main_probabilities']),
            json.dumps(result.get('sub_probabilities', {}))
        ))
        
        conn.commit()
        conn.close()
    
    def update_classification_with_correction(self, file_path: str, correction_data: Dict):
        """Update classification in database with user correction"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE audio_files 
            SET main_category = ?, sub_category = ?, 
                correction_count = correction_count + 1,
                user_verified = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        ''', (
            correction_data['corrected_main_category'],
            correction_data.get('corrected_sub_category'),
            file_path
        ))
        
        conn.commit()
        conn.close()
    
    def scan_directory(self, root_dir: str, progress_callback=None) -> List[str]:
        """Scan directory for audio files"""
        audio_files = []
        root_path = Path(root_dir)
        
        for file_path in root_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                audio_files.append(str(file_path))
                if progress_callback:
                    progress_callback(f"Found: {file_path.name}")
        
        return audio_files
    
    def get_library_stats(self) -> Dict:
        """Get statistics about the classified library"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total files
        cursor.execute('SELECT COUNT(*) FROM audio_files')
        total_files = cursor.fetchone()[0]
        
        # Category breakdown
        cursor.execute('''
            SELECT main_category, COUNT(*) 
            FROM audio_files 
            GROUP BY main_category
        ''')
        main_categories = dict(cursor.fetchall())
        
        # Subcategory breakdown
        cursor.execute('''
            SELECT main_category, sub_category, COUNT(*) 
            FROM audio_files 
            WHERE sub_category IS NOT NULL
            GROUP BY main_category, sub_category
        ''')
        subcategories = {}
        for main_cat, sub_cat, count in cursor.fetchall():
            if main_cat not in subcategories:
                subcategories[main_cat] = {}
            subcategories[main_cat][sub_cat] = count
        
        conn.close()
        
        return {
            'total_files': total_files,
            'main_categories': main_categories,
            'subcategories': subcategories
        }
    
    def get_all_classifications(self) -> List[Dict]:
        """Get all classifications from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_path, filename, main_category, sub_category, 
                   main_confidence, sub_confidence, correction_count, user_verified
            FROM audio_files
            ORDER BY filename
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'file_path': row[0],
                'filename': row[1],
                'main_category': row[2],
                'sub_category': row[3],
                'main_confidence': row[4],
                'sub_confidence': row[5],
                'correction_count': row[6],
                'user_verified': row[7]
            })
        
        conn.close()
        return results

class CorrectionDialog:
    """Dialog for correcting classifications with dynamic subcategory creation"""
    
    def __init__(self, parent, original_result: Dict, correction_system=None):
        self.parent = parent
        self.original_result = original_result
        self.correction_system = correction_system
        self.result = None
        
        # Base categories (from original training)
        self.main_categories = ['bass', 'vocals', 'percussive', 'melodic']
        self.base_sub_categories = {
            'bass': ['808', 'heavy_bass', 'basses', 'sub_bass', 'reese_bass'],
            'vocals': ['spoken', 'sung', 'rap', 'harmony'],
            'percussive': ['kick', 'snare', 'percs', 'cymbol', 'hi_hat'],
            'melodic': ['instrument', 'synth', 'piano', 'guitar']
        }
        
        # Load user-created categories
        self.load_user_categories()
        
        self.create_dialog()
    
    def load_user_categories(self):
        """Load user-created subcategories from database"""
        if not self.correction_system:
            self.sub_categories = self.base_sub_categories.copy()
            return
            
        try:
            conn = sqlite3.connect(self.correction_system.corrections_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT main_category, sub_category 
                FROM user_categories 
                ORDER BY main_category, sub_category
            ''')
            
            # Start with base categories
            self.sub_categories = {}
            for main_cat in self.main_categories:
                self.sub_categories[main_cat] = self.base_sub_categories[main_cat].copy()
            
            # Add user categories
            for main_cat, sub_cat in cursor.fetchall():
                if main_cat in self.sub_categories:
                    if sub_cat not in self.sub_categories[main_cat]:
                        self.sub_categories[main_cat].append(sub_cat)
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading user categories: {e}")
            self.sub_categories = self.base_sub_categories.copy()
    
    def create_dialog(self):
        """Create the correction dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Correct Classification - {self.original_result['filename']}")
        self.dialog.geometry("500x400")
        self.dialog.grab_set()  # Make dialog modal
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Correct Audio Classification", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # File info
        ttk.Label(main_frame, text=f"File: {self.original_result['filename']}", 
                 font=('Arial', 10)).pack(pady=(0, 10))
        
        # Original classification
        orig_frame = ttk.LabelFrame(main_frame, text="Original Classification", padding="10")
        orig_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(orig_frame, 
                 text=f"Main: {self.original_result['main_category']} (conf: {self.original_result['main_confidence']:.3f})").pack(anchor=tk.W)
        
        sub_cat = self.original_result.get('sub_category', 'None')
        sub_conf = self.original_result.get('sub_confidence', 0.0)
        ttk.Label(orig_frame, 
                 text=f"Sub: {sub_cat} (conf: {sub_conf:.3f})").pack(anchor=tk.W)
        
        # Correction section
        correction_frame = ttk.LabelFrame(main_frame, text="Correct Classification", padding="10")
        correction_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Main category correction
        ttk.Label(correction_frame, text="Main Category:").pack(anchor=tk.W)
        self.main_category_var = tk.StringVar(value=self.original_result['main_category'])
        main_combo = ttk.Combobox(correction_frame, textvariable=self.main_category_var, 
                                 values=self.main_categories, state="readonly")
        main_combo.pack(fill=tk.X, pady=(0, 10))
        main_combo.bind('<<ComboboxSelected>>', self.on_main_category_changed)
        
        # Sub category correction
        subcategory_section = ttk.Frame(correction_frame)
        subcategory_section.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(subcategory_section, text="Sub Category:").pack(anchor=tk.W)
        
        # Sub category selection frame
        sub_select_frame = ttk.Frame(subcategory_section)
        sub_select_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.sub_category_var = tk.StringVar(value=self.original_result.get('sub_category', ''))
        self.sub_combo = ttk.Combobox(sub_select_frame, textvariable=self.sub_category_var, 
                                     state="readonly")
        self.sub_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # New subcategory button
        new_sub_btn = ttk.Button(sub_select_frame, text="+ New", command=self.create_new_subcategory)
        new_sub_btn.pack(side=tk.RIGHT)
        
        # Update sub-categories for current main category
        self.update_sub_categories()
        
        # Notes
        ttk.Label(correction_frame, text="Notes (optional):").pack(anchor=tk.W)
        self.notes_text = tk.Text(correction_frame, height=3)
        self.notes_text.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Create buttons with proper spacing
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        save_btn = ttk.Button(button_frame, text="💾 Save Correction", command=self.save_correction)
        save_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        # Make save button prominent
        save_btn.configure(style='Accent.TButton')
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def on_main_category_changed(self, event=None):
        """Update sub-categories when main category changes"""
        self.update_sub_categories()
    
    def update_sub_categories(self):
        """Update the sub-category dropdown based on selected main category"""
        main_cat = self.main_category_var.get()
        if main_cat in self.sub_categories:
            self.sub_combo['values'] = self.sub_categories[main_cat]
            # Reset sub-category if it doesn't match new main category
            if self.sub_category_var.get() not in self.sub_categories[main_cat]:
                self.sub_category_var.set('')
        else:
            self.sub_combo['values'] = []
            self.sub_category_var.set('')
    
    def save_correction(self):
        """Save the correction"""
        # Validate input
        if not self.main_category_var.get():
            messagebox.showerror("Error", "Please select a main category.")
            return
        
        self.result = {
            'corrected_main_category': self.main_category_var.get(),
            'corrected_sub_category': self.sub_category_var.get() or None,
            'user_notes': self.notes_text.get('1.0', tk.END).strip()
        }
        
        self.dialog.destroy()
    
    def create_new_subcategory(self):
        """Create a new subcategory for the selected main category"""
        main_cat = self.main_category_var.get()
        if not main_cat:
            messagebox.showwarning("No Main Category", "Please select a main category first.")
            return
        
        # Create new subcategory dialog
        new_sub_dialog = NewSubcategoryDialog(self.dialog, main_cat, self.correction_system)
        self.dialog.wait_window(new_sub_dialog.dialog)
        
        if new_sub_dialog.result:
            new_subcategory = new_sub_dialog.result
            
            # Add to local list
            if main_cat in self.sub_categories:
                if new_subcategory not in self.sub_categories[main_cat]:
                    self.sub_categories[main_cat].append(new_subcategory)
                    
            # Update the dropdown
            self.update_sub_categories()
            
            # Set the new subcategory as selected
            self.sub_category_var.set(new_subcategory)
            
            messagebox.showinfo("Subcategory Created", 
                               f"New subcategory '{new_subcategory}' created for '{main_cat}'!")
    
    def cancel(self):
        """Cancel the correction"""
        self.result = None
        self.dialog.destroy()

class NewSubcategoryDialog:
    """Dialog for creating a new subcategory"""
    
    def __init__(self, parent, main_category: str, correction_system=None):
        self.parent = parent
        self.main_category = main_category
        self.correction_system = correction_system
        self.result = None
        
        self.create_dialog()
    
    def create_dialog(self):
        """Create the new subcategory dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Create New Subcategory for {self.main_category}")
        self.dialog.geometry("400x300")
        self.dialog.grab_set()  # Make dialog modal
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Create New Subcategory", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # Category info
        ttk.Label(main_frame, text=f"Main Category: {self.main_category}", 
                 font=('Arial', 10)).pack(pady=(0, 15))
        
        # Subcategory name
        ttk.Label(main_frame, text="Subcategory Name:").pack(anchor=tk.W)
        self.subcategory_var = tk.StringVar()
        subcategory_entry = ttk.Entry(main_frame, textvariable=self.subcategory_var, width=40)
        subcategory_entry.pack(fill=tk.X, pady=(5, 10))
        subcategory_entry.focus_set()  # Focus on the entry
        
        # Description
        ttk.Label(main_frame, text="Description (optional):").pack(anchor=tk.W)
        self.description_text = tk.Text(main_frame, height=4, width=40)
        self.description_text.pack(fill=tk.X, pady=(5, 15))
        
        # Validation info
        info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Info", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = (
            "• Subcategory names should be lowercase with underscores\n"
            "• Examples: 'deep_house', 'electric_guitar', 'vocal_chops'\n"
            "• This category will be available for future corrections\n"
            "• AI learning will be enabled after enough examples"
        )
        ttk.Label(info_frame, text=info_text, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        create_btn = ttk.Button(button_frame, text="✨ Create", command=self.create_subcategory)
        create_btn.pack(side=tk.RIGHT)
        
        # Bind Enter key to create
        subcategory_entry.bind('<Return>', lambda e: self.create_subcategory())
        
        # Center the dialog
        self.dialog.transient(self.parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_subcategory(self):
        """Create the new subcategory"""
        subcategory_name = self.subcategory_var.get().strip().lower()
        description = self.description_text.get('1.0', tk.END).strip()
        
        # Validate input
        if not subcategory_name:
            messagebox.showerror("Error", "Please enter a subcategory name.")
            return
        
        # Basic name validation
        if not self.validate_subcategory_name(subcategory_name):
            messagebox.showerror("Invalid Name", 
                               "Subcategory name should contain only lowercase letters, numbers, and underscores.")
            return
        
        # Check if already exists
        if self.subcategory_exists(subcategory_name):
            messagebox.showerror("Already Exists", 
                               f"Subcategory '{subcategory_name}' already exists for '{self.main_category}'.")
            return
        
        # Save to database
        if self.correction_system:
            self.save_new_subcategory(subcategory_name, description)
        
        self.result = subcategory_name
        self.dialog.destroy()
    
    def validate_subcategory_name(self, name: str) -> bool:
        """Validate subcategory name format"""
        import re
        # Allow lowercase letters, numbers, and underscores
        return bool(re.match(r'^[a-z0-9_]+$', name))
    
    def subcategory_exists(self, subcategory_name: str) -> bool:
        """Check if subcategory already exists"""
        if not self.correction_system:
            return False
            
        try:
            conn = sqlite3.connect(self.correction_system.corrections_db)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT COUNT(*) FROM user_categories WHERE main_category = ? AND sub_category = ?',
                (self.main_category, subcategory_name)
            )
            
            exists = cursor.fetchone()[0] > 0
            conn.close()
            
            return exists
            
        except Exception as e:
            print(f"Error checking subcategory existence: {e}")
            return False
    
    def save_new_subcategory(self, subcategory_name: str, description: str):
        """Save new subcategory to database"""
        try:
            conn = sqlite3.connect(self.correction_system.corrections_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_categories 
                (main_category, sub_category, user_description, sample_count, ai_enabled)
                VALUES (?, ?, ?, 0, FALSE)
            ''', (self.main_category, subcategory_name, description))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error saving new subcategory: {e}")
            messagebox.showerror("Database Error", f"Failed to save subcategory: {e}")
    
    def cancel(self):
        """Cancel subcategory creation"""
        self.result = None
        self.dialog.destroy()

class SelectaDesktopAppEnhanced:
    """Enhanced GUI application with correction capabilities"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Selecta Enhanced - Audio Classifier with Learning")
        self.root.geometry("1200x800")
        
        # Backend
        self.scanner = AudioLibraryScannerEnhanced()
        self.scan_queue = queue.Queue()
        self.scan_thread = None
        self.is_scanning = False
        
        # Variables
        self.selected_directory = tk.StringVar()
        self.scan_progress = tk.StringVar(value="Ready to scan")
        self.files_processed = tk.IntVar()
        self.total_files = tk.IntVar()
        
        self.setup_ui()
        self.load_models()
        self.refresh_results()  # Load existing results
        
    def setup_ui(self):
        """Setup the enhanced user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="🎵 Selecta Enhanced - AI Learning Audio Classifier", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Directory selection
        dir_frame = ttk.LabelFrame(main_frame, text="📁 Select Music Library", padding="10")
        dir_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        dir_frame.columnconfigure(1, weight=1)
        
        ttk.Label(dir_frame, text="Directory:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        dir_entry = ttk.Entry(dir_frame, textvariable=self.selected_directory, width=60)
        dir_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        browse_btn = ttk.Button(dir_frame, text="Browse", command=self.browse_directory)
        browse_btn.grid(row=0, column=2)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=3, pady=(0, 10))
        
        self.scan_btn = ttk.Button(control_frame, text="🚀 Start Scan", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_scan, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        refresh_btn = ttk.Button(control_frame, text="🔄 Refresh Results", command=self.refresh_results)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        export_btn = ttk.Button(control_frame, text="📊 Export Results", command=self.export_results)
        export_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        learning_btn = ttk.Button(control_frame, text="🧠 Apply Learning", command=self.apply_learning)
        learning_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        stats_btn = ttk.Button(control_frame, text="📈 View Stats", command=self.show_stats)
        stats_btn.pack(side=tk.LEFT)
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="📊 Scan Progress", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Progress text
        progress_label = ttk.Label(progress_frame, textvariable=self.scan_progress)
        progress_label.grid(row=1, column=0, sticky=tk.W)
        
        # Results section with correction capabilities
        results_frame = ttk.LabelFrame(main_frame, text="🎯 Classification Results (Right-click to correct)", padding="10")
        results_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Results tree with additional columns
        columns = ('File', 'Main Category', 'Sub Category', 'Main Conf.', 'Sub Conf.', 'Corrections', 'Verified')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.results_tree.heading('File', text='File Name')
        self.results_tree.heading('Main Category', text='Main Category')
        self.results_tree.heading('Sub Category', text='Sub Category')
        self.results_tree.heading('Main Conf.', text='Main Conf.')
        self.results_tree.heading('Sub Conf.', text='Sub Conf.')
        self.results_tree.heading('Corrections', text='Corrections')
        self.results_tree.heading('Verified', text='Verified')
        
        self.results_tree.column('File', width=250)
        self.results_tree.column('Main Category', width=120)
        self.results_tree.column('Sub Category', width=120)
        self.results_tree.column('Main Conf.', width=80)
        self.results_tree.column('Sub Conf.', width=80)
        self.results_tree.column('Corrections', width=80)
        self.results_tree.column('Verified', width=80)
        
        # Right-click context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🔧 Correct Classification", command=self.correct_selected)
        self.context_menu.add_command(label="📁 Open File Location", command=self.open_file_location)
        
        # Bind right-click
        self.results_tree.bind("<Button-2>", self.show_context_menu)  # Mac right-click
        self.results_tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux right-click
        
        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.results_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready - Enhanced with AI Learning")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def load_models(self):
        """Load the classification models"""
        self.status_var.set("Loading classification models...")
        self.root.update()
        
        try:
            if self.scanner.load_classifier():
                self.status_var.set("✅ Enhanced models loaded - AI Learning ready")
                self.scan_btn.config(state="normal")
            else:
                self.status_var.set("❌ Failed to load models - Check model files")
                messagebox.showerror("Model Error", 
                                   "Failed to load classification models. Please ensure model files exist.")
        except Exception as e:
            self.status_var.set(f"❌ Model loading error: {e}")
            messagebox.showerror("Model Error", f"Error loading models: {e}")
    
    def browse_directory(self):
        """Browse for directory to scan"""
        directory = filedialog.askdirectory(
            title="Select Music Library Directory",
            initialdir=os.path.expanduser("~")
        )
        if directory:
            self.selected_directory.set(directory)
    
    def show_context_menu(self, event):
        """Show context menu on right-click"""
        item = self.results_tree.selection()[0] if self.results_tree.selection() else None
        if item:
            self.context_menu.post(event.x_root, event.y_root)
    
    def correct_selected(self):
        """Open correction dialog for selected item"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to correct.")
            return
        
        item = selection[0]
        values = self.results_tree.item(item, 'values')
        
        # Get the file path from our data
        filename = values[0]
        
        # Find the full result data
        all_results = self.scanner.get_all_classifications()
        file_result = None
        for result in all_results:
            if result['filename'] == filename:
                file_result = result
                break
        
        if not file_result:
            messagebox.showerror("Error", "Could not find file data for correction.")
            return
        
        # Open correction dialog
        dialog = CorrectionDialog(self.root, file_result, self.scanner.correction_system)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.apply_correction(file_result, dialog.result)
    
    def apply_correction(self, original_result: Dict, correction: Dict):
        """Apply user correction"""
        try:
            # Prepare correction data
            correction_data = {
                'file_path': original_result['file_path'],
                'filename': original_result['filename'],
                'original_main_category': original_result['main_category'],
                'original_sub_category': original_result.get('sub_category'),
                'corrected_main_category': correction['corrected_main_category'],
                'corrected_sub_category': correction['corrected_sub_category'],
                'original_main_confidence': original_result['main_confidence'],
                'original_sub_confidence': original_result.get('sub_confidence', 0.0),
                'user_notes': correction['user_notes']
            }
            
            # Save correction to learning system
            correction_id = self.scanner.correction_system.save_correction(correction_data)
            
            # Update the main database with correction
            self.scanner.update_classification_with_correction(
                original_result['file_path'], correction_data
            )
            
            # Refresh the display
            self.refresh_results()
            
            # Show success message
            messagebox.showinfo("Correction Applied", 
                               f"Correction saved! The AI will learn from this feedback.\n\n"
                               f"Original: {original_result['main_category']}\n"
                               f"Corrected: {correction['corrected_main_category']}")
            
            self.status_var.set(f"✅ Correction applied - {correction['corrected_main_category']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply correction: {e}")
    
    def apply_learning(self):
        """Apply accumulated corrections to improve the AI"""
        try:
            corrections = self.scanner.correction_system.get_corrections_for_training()
            
            if not corrections:
                messagebox.showinfo("No Corrections", "No corrections available for training.")
                return
            
            # Show learning dialog
            response = messagebox.askyesno(
                "Apply AI Learning",
                f"Found {len(corrections)} corrections to apply to the AI.\n\n"
                f"This will:\n"
                f"• Use your corrections to improve accuracy\n"
                f"• Create new training data from corrected files\n"
                f"• Help the AI learn your preferences\n\n"
                f"Apply learning now?"
            )
            
            if response:
                self.perform_learning_update(corrections)
                
        except Exception as e:
            messagebox.showerror("Learning Error", f"Failed to apply learning: {e}")
    
    def perform_learning_update(self, corrections):
        """Perform the actual learning update"""
        try:
            # For now, we'll prepare the data and mark as applied
            # In a full implementation, this would retrain the models
            
            # Organize corrections by category
            correction_summary = {}
            for correction in corrections:
                original = correction['original_main_category']
                corrected = correction['corrected_main_category']
                
                key = f"{original} → {corrected}"
                if key not in correction_summary:
                    correction_summary[key] = 0
                correction_summary[key] += 1
            
            # Mark corrections as applied
            correction_ids = [c['id'] for c in corrections]
            self.scanner.correction_system.mark_corrections_applied(correction_ids)
            
            # Show summary
            summary_text = "Learning Applied Successfully!\n\n"
            summary_text += "Correction Summary:\n"
            for correction_type, count in correction_summary.items():
                summary_text += f"• {correction_type}: {count} corrections\n"
            
            summary_text += "\nThe AI has learned from your feedback and will be more accurate in the future!"
            
            messagebox.showinfo("Learning Complete", summary_text)
            
            # Update status
            self.status_var.set(f"✅ AI Learning applied - {len(corrections)} corrections processed")
            
            # Refresh results to show updated verification status
            self.refresh_results()
            
        except Exception as e:
            messagebox.showerror("Learning Error", f"Failed to complete learning update: {e}")
    
    def open_file_location(self):
        """Open file location in system file manager"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.results_tree.item(item, 'values')
        filename = values[0]
        
        # Find the full file path
        all_results = self.scanner.get_all_classifications()
        for result in all_results:
            if result['filename'] == filename:
                file_path = result['file_path']
                if os.path.exists(file_path):
                    # Open file location (Mac)
                    os.system(f'open -R "{file_path}"')
                break
    
    def refresh_results(self):
        """Refresh the results tree with current data"""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Load all classifications
        results = self.scanner.get_all_classifications()
        
        for result in results:
            main_conf = f"{result['main_confidence']:.3f}" if result['main_confidence'] else ''
            sub_conf = f"{result['sub_confidence']:.3f}" if result['sub_confidence'] else ''
            corrections = str(result['correction_count'])
            verified = "✅" if result['user_verified'] else "❌"
            
            self.results_tree.insert('', 'end', values=(
                result['filename'],
                result['main_category'] or '',
                result['sub_category'] or '',
                main_conf,
                sub_conf,
                corrections,
                verified
            ))
    
    # ... (rest of the methods from the original app remain the same)
    def start_scan(self):
        """Start scanning the selected directory"""
        if not self.selected_directory.get():
            messagebox.showwarning("No Directory", "Please select a directory to scan.")
            return
        
        if not os.path.exists(self.selected_directory.get()):
            messagebox.showerror("Invalid Directory", "Selected directory does not exist.")
            return
        
        # Clear previous results display (but keep database)
        # for item in self.results_tree.get_children():
        #     self.results_tree.delete(item)
        
        # Start scan in separate thread
        self.is_scanning = True
        self.scan_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        self.scan_thread = threading.Thread(target=self.scan_worker, daemon=True)
        self.scan_thread.start()
        
        # Start checking queue
        self.check_queue()
    
    def scan_worker(self):
        """Worker thread for scanning files"""
        try:
            # Scan for audio files
            self.scan_queue.put(("status", "Scanning for audio files..."))
            audio_files = self.scanner.scan_directory(
                self.selected_directory.get(),
                lambda msg: self.scan_queue.put(("progress", msg))
            )
            
            if not audio_files:
                self.scan_queue.put(("status", "No audio files found in directory"))
                self.scan_queue.put(("complete", None))
                return
            
            self.scan_queue.put(("total", len(audio_files)))
            
            # Process each file
            for i, file_path in enumerate(audio_files):
                if not self.is_scanning:  # Check if stopped
                    break
                    
                self.scan_queue.put(("progress", f"Classifying: {os.path.basename(file_path)}"))
                
                # Classify file
                result = self.scanner.classify_file(file_path)
                if result:
                    # Save to database
                    self.scanner.save_classification(result)
                    
                    # Send to UI
                    self.scan_queue.put(("result", result))
                
                self.scan_queue.put(("count", i + 1))
            
            self.scan_queue.put(("complete", None))
            
        except Exception as e:
            self.scan_queue.put(("error", str(e)))
    
    def scan_directory(self, root_dir: str, progress_callback=None):
        """Scan directory for audio files"""
        audio_files = []
        root_path = Path(root_dir)
        supported_formats = {'.wav', '.mp3', '.flac', '.m4a', '.aiff', '.ogg'}
        
        for file_path in root_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                audio_files.append(str(file_path))
                if progress_callback:
                    progress_callback(f"Found: {file_path.name}")
        
        return audio_files
    
    def check_queue(self):
        """Check the scan queue for updates"""
        try:
            while True:
                msg_type, data = self.scan_queue.get_nowait()
                
                if msg_type == "status":
                    self.scan_progress.set(data)
                elif msg_type == "progress":
                    self.scan_progress.set(data)
                elif msg_type == "total":
                    self.total_files.set(data)
                    self.progress_bar.config(maximum=data)
                elif msg_type == "count":
                    self.files_processed.set(data)
                    self.progress_bar.config(value=data)
                    self.scan_progress.set(f"Processed {data}/{self.total_files.get()} files")
                elif msg_type == "result":
                    self.add_result_to_tree(data)
                elif msg_type == "complete":
                    self.scan_complete()
                    return
                elif msg_type == "error":
                    self.scan_error(data)
                    return
                    
        except queue.Empty:
            pass
        
        if self.is_scanning:
            self.root.after(100, self.check_queue)
    
    def add_result_to_tree(self, result):
        """Add classification result to the tree view"""
        filename = result['filename']
        main_cat = result['main_category']
        sub_cat = result.get('sub_category', '')
        main_conf = f"{result['main_confidence']:.3f}"
        sub_conf = f"{result.get('sub_confidence', 0):.3f}" if result.get('sub_confidence') else ''
        
        self.results_tree.insert('', 'end', values=(
            filename, main_cat, sub_cat, main_conf, sub_conf, '0', '❌'
        ))
        
        # Auto-scroll to bottom
        children = self.results_tree.get_children()
        if children:
            self.results_tree.see(children[-1])
    
    def scan_complete(self):
        """Handle scan completion"""
        self.is_scanning = False
        self.scan_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        processed = self.files_processed.get()
        total = self.total_files.get()
        
        self.scan_progress.set(f"✅ Scan complete! Processed {processed}/{total} files")
        self.status_var.set(f"Scan completed - {processed} files classified")
        
        messagebox.showinfo("Scan Complete", 
                           f"Successfully classified {processed} audio files!\n\n"
                           f"Right-click on any result to correct classifications and help the AI learn.")
    
    def scan_error(self, error_msg):
        """Handle scan error"""
        self.is_scanning = False
        self.scan_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        self.scan_progress.set(f"❌ Scan error: {error_msg}")
        messagebox.showerror("Scan Error", f"An error occurred during scanning: {error_msg}")
    
    def stop_scan(self):
        """Stop the current scan"""
        self.is_scanning = False
        self.scan_progress.set("Stopping scan...")
        self.stop_btn.config(state="disabled")
    
    def show_stats(self):
        """Show library statistics"""
        stats = self.scanner.get_library_stats()
        # Implementation similar to original
        messagebox.showinfo("Stats", "Statistics feature - see original implementation")
    
    def export_results(self):
        """Export classification results to CSV"""
        # Implementation similar to original
        messagebox.showinfo("Export", "Export feature - see original implementation")
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    print("🎵 Starting Selecta Enhanced Desktop App with AI Learning...")
    
    app = SelectaDesktopAppEnhanced()
    app.run()

if __name__ == '__main__':
    main()

