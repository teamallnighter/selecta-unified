#!/usr/bin/env python3
"""
Selecta Unified App - Complete audio library manager with AI learning and full management features
Combines enhanced classification with corrections AND comprehensive library management
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
from selecta_desktop_app_enhanced import (
    CorrectionLearningSystem, 
    CorrectionDialog, 
    AudioLibraryScannerEnhanced
)
from library_manager import LibraryManager, PlaylistManager, ExportManager
from audio_player import AudioPlayerWidget
import warnings
warnings.filterwarnings('ignore')


class BatchCorrectionDialog:
    """Dialog for batch correcting multiple files"""
    
    def __init__(self, parent, files: List[Dict], correction_system=None):
        self.parent = parent
        self.files = files
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
        """Create the batch correction dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Batch Correct {len(self.files)} Files")
        self.dialog.geometry("600x500")  # Taller window
        self.dialog.grab_set()  # Make dialog modal
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Batch Correct Multiple Files", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # File list info
        ttk.Label(main_frame, text=f"Correcting {len(self.files)} selected files:", 
                 font=('Arial', 10)).pack(pady=(0, 10))
        
        # File list (scrollable)
        list_frame = ttk.LabelFrame(main_frame, text="Selected Files", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        file_listbox = tk.Listbox(list_container, height=8)
        list_scroll = ttk.Scrollbar(list_container, orient="vertical", command=file_listbox.yview)
        file_listbox.configure(yscrollcommand=list_scroll.set)
        
        file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add files to listbox
        for file_data in self.files:
            file_listbox.insert(tk.END, f"{file_data['filename']} ({file_data.get('main_category', 'Unknown')})")
        
        # Correction section
        correction_frame = ttk.LabelFrame(main_frame, text="New Classification for All Files", padding="10")
        correction_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Main category correction
        ttk.Label(correction_frame, text="Main Category:").pack(anchor=tk.W)
        self.main_category_var = tk.StringVar(value=self.main_categories[0])
        main_combo = ttk.Combobox(correction_frame, textvariable=self.main_category_var, 
                                 values=self.main_categories, state="readonly")
        main_combo.pack(fill=tk.X, pady=(0, 10))
        main_combo.bind('<<ComboboxSelected>>', self.on_main_category_changed)
        
        # Sub category correction
        ttk.Label(correction_frame, text="Sub Category:").pack(anchor=tk.W)
        
        # Sub category selection frame
        sub_select_frame = ttk.Frame(correction_frame)
        sub_select_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.sub_category_var = tk.StringVar()
        self.sub_combo = ttk.Combobox(sub_select_frame, textvariable=self.sub_category_var, 
                                     state="readonly")
        self.sub_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # New subcategory button
        new_sub_btn = ttk.Button(sub_select_frame, text="+ New", command=self.create_new_subcategory)
        new_sub_btn.pack(side=tk.RIGHT)
        
        # Update sub-categories for current main category
        self.update_sub_categories()
        
        # Notes
        ttk.Label(correction_frame, text="Notes (optional):").pack(anchor=tk.W, pady=(10, 0))
        self.notes_text = tk.Text(correction_frame, height=3)
        self.notes_text.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Create buttons with proper spacing
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        save_btn = ttk.Button(button_frame, text="💾 Apply Batch Correction", command=self.save_correction)
        save_btn.pack(side=tk.RIGHT, padx=(0, 5))
    
    def update_sub_categories(self):
        """Update subcategory options based on main category"""
        main_cat = self.main_category_var.get()
        if main_cat in self.sub_categories:
            self.sub_combo['values'] = self.sub_categories[main_cat]
            if self.sub_categories[main_cat]:
                self.sub_category_var.set(self.sub_categories[main_cat][0])
    
    def on_main_category_changed(self, event=None):
        """Handle main category change"""
        self.update_sub_categories()
    
    def create_new_subcategory(self):
        """Create a new subcategory"""
        main_cat = self.main_category_var.get()
        if not main_cat:
            messagebox.showwarning("No Main Category", "Please select a main category first.")
            return
        
        new_sub = simpledialog.askstring(
            "New Subcategory",
            f"Enter new subcategory for '{main_cat}':"
        )
        
        if new_sub and new_sub.strip():
            new_sub = new_sub.strip().lower().replace(' ', '_')
            
            # Add to local list
            if main_cat not in self.sub_categories:
                self.sub_categories[main_cat] = []
            
            if new_sub not in self.sub_categories[main_cat]:
                self.sub_categories[main_cat].append(new_sub)
                
                # Save to database if correction system available
                if self.correction_system:
                    try:
                        conn = sqlite3.connect(self.correction_system.corrections_db)
                        cursor = conn.cursor()
                        
                        cursor.execute('''
                            INSERT OR IGNORE INTO user_categories (main_category, sub_category)
                            VALUES (?, ?)
                        ''', (main_cat, new_sub))
                        
                        conn.commit()
                        conn.close()
                        
                    except Exception as e:
                        print(f"Error saving new subcategory: {e}")
                
                # Update combobox and select new item
                self.update_sub_categories()
                self.sub_category_var.set(new_sub)
    
    def save_correction(self):
        """Save the batch correction"""
        main_cat = self.main_category_var.get()
        sub_cat = self.sub_category_var.get()
        notes = self.notes_text.get('1.0', tk.END).strip()
        
        if not main_cat:
            messagebox.showwarning("Missing Category", "Please select a main category.")
            return
        
        self.result = {
            'corrected_main_category': main_cat,
            'corrected_sub_category': sub_cat,
            'user_notes': notes
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel the dialog"""
        self.result = None
        self.dialog.destroy()

class UnifiedLibraryView:
    """Unified library view with AI learning, corrections, metadata, and audio preview"""
    
    def __init__(self, parent, scanner: AudioLibraryScannerEnhanced):
        self.parent = parent
        self.scanner = scanner
        self.library_manager = LibraryManager(scanner.db_path)
        self.playlist_manager = PlaylistManager(scanner.db_path)
        self.export_manager = ExportManager(self.library_manager)
        
        # Current view state
        self.current_files = []
        self.selected_file = None
        self.selected_files = []  # For multi-selection
        self.current_filters = {}
        self.sort_column = None
        self.sort_reverse = False
        
        # Variables
        self.search_var = tk.StringVar()
        self.filter_category_var = tk.StringVar(value="All")
        self.filter_subcategory_var = tk.StringVar(value="All") 
        self.filter_rating_var = tk.StringVar(value="All")
        self.filter_verified_var = tk.StringVar(value="All")
        
        self.create_view()
        self.load_library()
    
    def create_view(self):
        """Create the unified library management interface"""
        # Main container
        self.main_frame = ttk.Frame(self.parent)
        
        # Top toolbar with enhanced search and filters
        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # Search and filters
        search_frame = ttk.LabelFrame(toolbar, text="🔍 Search & Filters", padding="5")
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Row 1: Search and main filters
        # Search box
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 15))
        search_entry.bind('<KeyRelease>', self.on_search_changed)
        
        # Category filter
        ttk.Label(search_frame, text="Category:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        category_combo = ttk.Combobox(search_frame, textvariable=self.filter_category_var, 
                                     values=["All", "bass", "vocals", "percussive", "melodic"], 
                                     state="readonly", width=12)
        category_combo.grid(row=0, column=3, sticky=tk.W, padx=(0, 15))
        category_combo.bind('<<ComboboxSelected>>', self.on_filter_changed)
        
        # Subcategory filter
        ttk.Label(search_frame, text="Sub:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.subcategory_combo = ttk.Combobox(search_frame, textvariable=self.filter_subcategory_var,
                                             state="readonly", width=12)
        self.subcategory_combo.grid(row=0, column=5, sticky=tk.W, padx=(0, 15))
        self.subcategory_combo.bind('<<ComboboxSelected>>', self.on_filter_changed)
        
        # Row 2: Additional filters and actions
        # Rating filter
        ttk.Label(search_frame, text="Rating:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        rating_combo = ttk.Combobox(search_frame, textvariable=self.filter_rating_var,
                                   values=["All", "⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                                   state="readonly", width=8)
        rating_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 15))
        rating_combo.bind('<<ComboboxSelected>>', self.on_filter_changed)
        
        # Verified filter
        ttk.Label(search_frame, text="Verified:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        verified_combo = ttk.Combobox(search_frame, textvariable=self.filter_verified_var,
                                     values=["All", "✅ Verified", "❌ Unverified"],
                                     state="readonly", width=12)
        verified_combo.grid(row=1, column=3, sticky=tk.W, padx=(0, 15))
        verified_combo.bind('<<ComboboxSelected>>', self.on_filter_changed)
        
        # Action buttons
        ttk.Button(search_frame, text="🔄 Refresh", command=self.load_library).grid(row=1, column=4, padx=(15, 5))
        ttk.Button(search_frame, text="📊 Export", command=self.show_export_dialog).grid(row=1, column=5, padx=(5, 5))
        ttk.Button(search_frame, text="🧠 AI Learning", command=self.apply_learning).grid(row=1, column=6, padx=(5, 0))
        
        # Main content area
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left panel - Audio player and file list
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Audio player
        self.audio_player = AudioPlayerWidget(left_panel)
        self.audio_player.pack(fill=tk.X, pady=(0, 10))
        
        # Library tree with enhanced columns
        library_frame = ttk.LabelFrame(left_panel, text="🎵 Music Library (Right-click to correct)", padding="5")
        library_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure library tree with comprehensive columns
        columns = ('File', 'Category', 'Sub', 'Conf', 'Rating', 'Tags', 'BPM', 'Plays', 'Corrections', 'Verified')
        self.library_tree = ttk.Treeview(library_frame, columns=columns, show='headings', height=20, selectmode='extended')
        
        # Configure columns with sorting
        self.library_tree.heading('File', text='File Name ↕', command=lambda: self.sort_by_column('File'))
        self.library_tree.heading('Category', text='Category ↕', command=lambda: self.sort_by_column('Category'))
        self.library_tree.heading('Sub', text='Sub Category ↕', command=lambda: self.sort_by_column('Sub'))
        self.library_tree.heading('Conf', text='Confidence ↕', command=lambda: self.sort_by_column('Conf'))
        self.library_tree.heading('Rating', text='Rating ↕', command=lambda: self.sort_by_column('Rating'))
        self.library_tree.heading('Tags', text='Tags ↕', command=lambda: self.sort_by_column('Tags'))
        self.library_tree.heading('BPM', text='BPM ↕', command=lambda: self.sort_by_column('BPM'))
        self.library_tree.heading('Plays', text='Plays ↕', command=lambda: self.sort_by_column('Plays'))
        self.library_tree.heading('Corrections', text='Corrections ↕', command=lambda: self.sort_by_column('Corrections'))
        self.library_tree.heading('Verified', text='Verified ↕', command=lambda: self.sort_by_column('Verified'))
        
        # Column widths
        self.library_tree.column('File', width=180)
        self.library_tree.column('Category', width=80)
        self.library_tree.column('Sub', width=90)
        self.library_tree.column('Conf', width=60)
        self.library_tree.column('Rating', width=50)
        self.library_tree.column('Tags', width=100)
        self.library_tree.column('BPM', width=50)
        self.library_tree.column('Plays', width=40)
        self.library_tree.column('Corrections', width=70)
        self.library_tree.column('Verified', width=60)
        
        # Tree scrollbar
        tree_scroll = ttk.Scrollbar(library_frame, orient="vertical", command=self.library_tree.yview)
        self.library_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.library_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context menu for corrections and actions
        self.context_menu = tk.Menu(self.parent, tearoff=0)
        self.context_menu.add_command(label="✅ Confirm as Correct", command=self.confirm_correct)
        self.context_menu.add_command(label="🔧 Correct Classification", command=self.correct_selected)
        self.context_menu.add_command(label="🔧 Batch Correct Selected", command=self.batch_correct_selected)
        self.context_menu.add_command(label="▶️ Play Audio", command=self.play_selected)
        self.context_menu.add_command(label="📁 Open File Location", command=self.open_file_location)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⭐ Rate File", command=self.rate_selected)
        self.context_menu.add_command(label="🏷️ Edit Tags", command=self.edit_tags_selected)
        
        # Bind events
        self.library_tree.bind('<<TreeviewSelect>>', self.on_file_selected)
        self.library_tree.bind('<Double-1>', self.on_file_double_click)
        self.library_tree.bind("<Button-2>", self.show_context_menu)  # Mac right-click
        self.library_tree.bind("<Button-3>", self.show_context_menu)  # Windows/Linux right-click
        
        # Right panel - File details, metadata editing, and playlists
        right_panel = ttk.Frame(content_frame, width=380)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # File details with AI confidence info
        details_frame = ttk.LabelFrame(right_panel, text="📄 File Details & AI Info", padding="10")
        details_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_info_text = tk.Text(details_frame, height=8, wrap=tk.WORD, state=tk.DISABLED, font=('Courier', 9))
        self.file_info_text.pack(fill=tk.X)
        
        # Metadata editing
        metadata_frame = ttk.LabelFrame(right_panel, text="✏️ Edit Metadata", padding="10")
        metadata_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Rating with stars
        ttk.Label(metadata_frame, text="Rating:").grid(row=0, column=0, sticky=tk.W, pady=2)
        rating_frame = ttk.Frame(metadata_frame)
        rating_frame.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        # Star rating buttons
        self.star_buttons = []
        for i in range(5):
            btn = ttk.Button(rating_frame, text="☆", width=3, 
                           command=lambda r=i+1: self.set_rating(r))
            btn.pack(side=tk.LEFT)
            self.star_buttons.append(btn)
        
        # Tags
        ttk.Label(metadata_frame, text="Tags:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.tags_var = tk.StringVar()
        tags_entry = ttk.Entry(metadata_frame, textvariable=self.tags_var, width=25)
        tags_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        tags_entry.bind('<KeyRelease>', self.on_metadata_changed)
        
        # Notes
        ttk.Label(metadata_frame, text="Notes:").grid(row=2, column=0, sticky=tk.NW, pady=2)
        self.notes_text = tk.Text(metadata_frame, height=3, width=25)
        self.notes_text.grid(row=2, column=1, sticky=tk.W, pady=2)
        self.notes_text.bind('<KeyRelease>', self.on_metadata_changed)
        
        # BPM
        ttk.Label(metadata_frame, text="BPM:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.bpm_var = tk.StringVar()
        bpm_entry = ttk.Entry(metadata_frame, textvariable=self.bpm_var, width=10)
        bpm_entry.grid(row=3, column=1, sticky=tk.W, pady=2)
        bpm_entry.bind('<KeyRelease>', self.on_metadata_changed)
        
        # Metadata buttons
        button_frame = ttk.Frame(metadata_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="💾 Save Metadata", 
                  command=self.save_metadata).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔧 Correct AI", 
                  command=self.correct_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔧 Batch Correct", 
                  command=self.batch_correct_selected).pack(side=tk.LEFT)
        
        # Playlists
        playlist_frame = ttk.LabelFrame(right_panel, text="🎵 Playlists", padding="10")
        playlist_frame.pack(fill=tk.BOTH, expand=True)
        
        # Playlist list
        self.playlist_listbox = tk.Listbox(playlist_frame, height=6)
        self.playlist_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Playlist buttons
        playlist_btn_frame = ttk.Frame(playlist_frame)
        playlist_btn_frame.pack(fill=tk.X)
        
        ttk.Button(playlist_btn_frame, text="➕ New", 
                  command=self.create_playlist).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_btn_frame, text="➕ Add to", 
                  command=self.add_to_playlist).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(playlist_btn_frame, text="▶️ Play List", 
                  command=self.play_playlist).pack(side=tk.LEFT)
        
        # Load playlists
        self.load_playlists()
    
    def pack(self, **kwargs):
        """Pack the main frame"""
        self.main_frame.pack(**kwargs)
    
    def load_library(self, preserve_selection_file_id=None):
        """Load library files with current filters"""
        # Store current selection if not specified
        if preserve_selection_file_id is None and self.selected_file:
            preserve_selection_file_id = self.selected_file['id']
        
        # Build filters
        filters = {}
        
        if self.filter_category_var.get() != "All":
            filters['main_category'] = self.filter_category_var.get()
            
        if self.filter_subcategory_var.get() != "All":
            filters['sub_category'] = self.filter_subcategory_var.get()
            
        if self.filter_rating_var.get() != "All":
            rating_stars = self.filter_rating_var.get().count('⭐')
            filters['min_rating'] = rating_stars
        
        if self.filter_verified_var.get() == "✅ Verified":
            filters['user_verified'] = True
        elif self.filter_verified_var.get() == "❌ Unverified":
            filters['user_verified'] = False
        
        # Get search term
        search_term = self.search_var.get().strip() if self.search_var.get().strip() else None
        
        # Store current filters
        self.current_filters = filters
        
        # Load files
        self.current_files = self.library_manager.get_library_with_metadata(
            filters=filters, search_term=search_term
        )
        
        # Update tree
        self.update_library_tree()
        
        # Update subcategory options
        self.update_subcategory_filter()
        
        # Restore selection if requested
        if preserve_selection_file_id:
            self._restore_selection_by_file_id(preserve_selection_file_id)
    
    def update_library_tree(self):
        """Update the library tree with current files"""
        # Clear existing items
        for item in self.library_tree.get_children():
            self.library_tree.delete(item)
        
        # Add files
        for file_data in self.current_files:
            # Format rating as stars
            rating = file_data.get('user_rating', 0)
            rating_stars = '⭐' * rating if rating > 0 else ''
            
            # Format tags
            tags = file_data.get('user_tags', '') or ''
            if len(tags) > 12:
                tags = tags[:9] + '...'
            
            # Format BPM
            bpm = file_data.get('bpm')
            bpm_str = f"{bpm:.0f}" if bpm else ''
            
            # Format confidence
            conf = file_data.get('main_confidence')
            conf_str = f"{conf:.2f}" if conf else ''
            
            # Format verified status based on verification state
            user_verified = file_data.get('user_verified')
            if user_verified == 'correct':
                verified = "✅"  # Confirmed correct
            elif user_verified == 'incorrect':
                verified = "❌"  # Marked incorrect
            else:
                verified = "⏳"  # Pending/unreviewed
            
            # Get correction count
            corrections = file_data.get('correction_count', 0)
            
            self.library_tree.insert('', 'end', values=(
                file_data['filename'],
                file_data.get('main_category', ''),
                file_data.get('sub_category', ''),
                conf_str,
                rating_stars,
                tags,
                bpm_str,
                file_data.get('play_count', 0),
                corrections,
                verified
            ), tags=(str(file_data['id']),))
    
    def update_subcategory_filter(self):
        """Update subcategory filter options based on selected category"""
        category = self.filter_category_var.get()
        
        if category == "All":
            subcategories = ["All"]
        else:
            # Get unique subcategories for this category
            subcategories = ["All"]
            for file_data in self.current_files:
                if file_data.get('main_category') == category and file_data.get('sub_category'):
                    if file_data['sub_category'] not in subcategories:
                        subcategories.append(file_data['sub_category'])
            subcategories.sort()
        
        self.subcategory_combo['values'] = subcategories
        if self.filter_subcategory_var.get() not in subcategories:
            self.filter_subcategory_var.set("All")
    
    def on_search_changed(self, event=None):
        """Handle search text change"""
        # Debounce search
        if hasattr(self, '_search_timer'):
            self.parent.after_cancel(self._search_timer)
        self._search_timer = self.parent.after(500, self.load_library)
    
    def on_filter_changed(self, event=None):
        """Handle filter change"""
        self.load_library()
    
    def on_file_selected(self, event=None):
        """Handle file selection - supports multi-selection"""
        selection = self.library_tree.selection()
        if not selection:
            self.selected_file = None
            self.selected_files = []
            self.clear_file_details()
            return
        
        # Handle multiple selections
        self.selected_files = []
        for item in selection:
            tags = self.library_tree.item(item, 'tags')
            if tags:
                file_id = int(tags[0])
                file_data = next((f for f in self.current_files if f['id'] == file_id), None)
                if file_data:
                    self.selected_files.append(file_data)
        
        # Set primary selection (first selected item)
        if self.selected_files:
            self.selected_file = self.selected_files[0]
            self.update_file_details()
            self.load_file_metadata()
        else:
            self.selected_file = None
            self.clear_file_details()
    
    def on_file_double_click(self, event=None):
        """Handle file double-click (play audio)"""
        if self.selected_file and os.path.exists(self.selected_file['file_path']):
            # Store current file ID before operations that might lose it
            current_file_id = self.selected_file['id']
            
            if self.audio_player.load_file(self.selected_file['file_path'], self.selected_file['id']):
                self.audio_player.toggle_play()
                
                # Update play stats
                self.library_manager.update_play_stats(self.selected_file['id'])
                
                # Refresh the tree to show updated play count and restore selection
                self.load_library(preserve_selection_file_id=current_file_id)
    
    def show_context_menu(self, event):
        """Show context menu on right-click"""
        item = self.library_tree.selection()[0] if self.library_tree.selection() else None
        if item:
            self.context_menu.post(event.x_root, event.y_root)
    
    def update_file_details(self):
        """Update file details panel with enhanced AI info"""
        if not self.selected_file:
            return
        
        file_data = self.selected_file
        
        # Format enhanced file info with AI details
        info_text = f"""File: {file_data['filename']}
Path: {file_data['file_path']}
Size: {file_data.get('file_size', 0) / (1024*1024):.1f} MB

AI CLASSIFICATION:
Main: {file_data.get('main_category', 'Unknown')}
Sub: {file_data.get('sub_category', 'None')}
Confidence: {file_data.get('main_confidence', 0):.3f}
Sub Conf: {file_data.get('sub_confidence', 0):.3f}

USER DATA:
Verified: {"✅ Yes" if file_data.get('user_verified') else "❌ No"}
Corrections: {file_data.get('correction_count', 0)}
Rating: {'⭐' * file_data.get('user_rating', 0) if file_data.get('user_rating') else 'None'}

METADATA:
Added: {file_data.get('created_at', 'Unknown')[:10]}"""
        
        if file_data.get('duration_seconds'):
            mins = int(file_data['duration_seconds'] // 60)
            secs = int(file_data['duration_seconds'] % 60)
            info_text += f"\nDuration: {mins}:{secs:02d}"
        
        if file_data.get('bpm'):
            info_text += f"\nBPM: {file_data['bpm']:.1f}"
        
        if file_data.get('last_played'):
            info_text += f"\nLast Played: {file_data['last_played'][:10]}"
        
        self.file_info_text.config(state=tk.NORMAL)
        self.file_info_text.delete('1.0', tk.END)
        self.file_info_text.insert('1.0', info_text)
        self.file_info_text.config(state=tk.DISABLED)
    
    def load_file_metadata(self):
        """Load file metadata into editing fields"""
        if not self.selected_file:
            return
        
        file_data = self.selected_file
        
        # Update rating stars
        rating = file_data.get('user_rating', 0)
        self.update_star_display(rating)
        
        # Update other fields
        self.tags_var.set(file_data.get('user_tags', ''))
        
        self.notes_text.delete('1.0', tk.END)
        if file_data.get('user_notes'):
            self.notes_text.insert('1.0', file_data['user_notes'])
        
        bpm = file_data.get('bpm')
        self.bpm_var.set(f"{bpm:.1f}" if bpm else '')
    
    def clear_file_details(self):
        """Clear file details and metadata fields"""
        self.file_info_text.config(state=tk.NORMAL)
        self.file_info_text.delete('1.0', tk.END)
        self.file_info_text.config(state=tk.DISABLED)
        
        self.update_star_display(0)
        self.tags_var.set('')
        self.notes_text.delete('1.0', tk.END)
        self.bpm_var.set('')
    
    def _restore_selection_by_file_id(self, file_id):
        """Restore selection by finding the item with the given file ID"""
        try:
            for item in self.library_tree.get_children():
                tags = self.library_tree.item(item, 'tags')
                if tags and len(tags) > 0 and int(tags[0]) == file_id:
                    self.library_tree.selection_set(item)
                    self.library_tree.focus(item)
                    self.library_tree.see(item)
                    # Trigger selection event to update details panel
                    self.on_file_selected()
                    break
        except (ValueError, tk.TclError) as e:
            # If restoration fails, that's okay - user can reselect
            pass
    
    def set_rating(self, rating: int):
        """Set rating for selected file"""
        if not self.selected_file:
            return
        
        self.update_star_display(rating)
        
        # Store file ID before operations
        current_file_id = self.selected_file['id']
        
        # Save immediately
        self.library_manager.update_metadata(self.selected_file['id'], user_rating=rating)
        self.selected_file['user_rating'] = rating
        
        # Update tree and restore selection
        self.load_library(preserve_selection_file_id=current_file_id)
    
    def update_star_display(self, rating: int):
        """Update star button display"""
        for i, btn in enumerate(self.star_buttons):
            if i < rating:
                btn.config(text="⭐")
            else:
                btn.config(text="☆")
    
    def on_metadata_changed(self, event=None):
        """Handle metadata field changes"""
        # Auto-save could be implemented here
        pass
    
    def save_metadata(self):
        """Save metadata changes"""
        if not self.selected_file:
            messagebox.showwarning("No Selection", "Please select a file first.")
            return
        
        # Store file ID before operations
        current_file_id = self.selected_file['id']
        
        # Collect metadata
        metadata = {
            'user_tags': self.tags_var.get().strip(),
            'user_notes': self.notes_text.get('1.0', tk.END).strip()
        }
        
        # BPM
        try:
            bpm_text = self.bpm_var.get().strip()
            if bpm_text:
                metadata['bpm'] = float(bpm_text)
        except ValueError:
            pass
        
        # Save to database
        if self.library_manager.update_metadata(self.selected_file['id'], **metadata):
            # Update local data
            self.selected_file.update(metadata)
            
            # Update tree and restore selection
            self.load_library(preserve_selection_file_id=current_file_id)
            
            messagebox.showinfo("Saved", "Metadata saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save metadata.")
    
    def confirm_correct(self):
        """Confirm that the selected file's classification is correct"""
        if not self.selected_file:
            messagebox.showwarning("No Selection", "Please select a file to confirm.")
            return
        
        file_data = self.selected_file
        
        # Check if already verified
        if file_data.get('user_verified') == 'correct':
            messagebox.showinfo("Already Confirmed", 
                               f"This file's classification is already confirmed as correct.")
            return
        
        # Show confirmation dialog
        response = messagebox.askyesno(
            "Confirm Classification",
            f"Confirm that this classification is correct?\n\n"
            f"File: {file_data['filename']}\n"
            f"Main Category: {file_data.get('main_category', 'Unknown')}\n"
            f"Sub Category: {file_data.get('sub_category', 'None')}\n"
            f"Confidence: {file_data.get('main_confidence', 0):.3f}\n\n"
            f"This will mark the classification as verified and help improve AI accuracy."
        )
        
        if response:
            try:
                # Store file ID before operations
                current_file_id = file_data['id']
                
                # Update database to mark as verified correct
                conn = sqlite3.connect(self.scanner.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE audio_files 
                    SET user_verified = 'correct'
                    WHERE id = ?
                ''', (file_data['id'],))
                
                conn.commit()
                conn.close()
                
                # Update local data
                file_data['user_verified'] = 'correct'
                
                # Refresh the display and restore selection
                self.load_library(preserve_selection_file_id=current_file_id)
                
                messagebox.showinfo("Confirmed", 
                                   f"Classification confirmed as correct!\n\n"
                                   f"This feedback will help improve the AI's accuracy.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to confirm classification: {e}")
    
    def correct_selected(self):
        """Open correction dialog for selected item"""
        if not self.selected_file:
            messagebox.showwarning("No Selection", "Please select a file to correct.")
            return
        
        # Open correction dialog
        dialog = CorrectionDialog(self.parent.winfo_toplevel(), self.selected_file, 
                                 self.scanner.correction_system)
        self.parent.wait_window(dialog.dialog)
        
        if dialog.result:
            self.apply_correction(self.selected_file, dialog.result)
    
    def apply_correction(self, original_result: Dict, correction: Dict):
        """Apply user correction"""
        try:
            # Store file ID before operations
            current_file_id = original_result['id']
            
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
            
            # Update the main database with correction and mark as incorrect
            self.scanner.update_classification_with_correction(
                original_result['file_path'], correction_data
            )
            
            # Mark the file as verified incorrect in the database
            conn = sqlite3.connect(self.scanner.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE audio_files 
                SET user_verified = 'incorrect'
                WHERE id = ?
            ''', (original_result['id'],))
            
            conn.commit()
            conn.close()
            
            # Refresh the display and restore selection
            self.load_library(preserve_selection_file_id=current_file_id)
            
            # Show success message
            messagebox.showinfo("Correction Applied", 
                               f"Correction saved! The AI will learn from this feedback.\n\n"
                               f"Original: {original_result['main_category']}\n"
                               f"Corrected: {correction['corrected_main_category']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply correction: {e}")
    
    def sort_by_column(self, column):
        """Sort library tree by column"""
        # Toggle sort direction if same column
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        # Update column headers to show sort direction
        columns = {'File': 'File Name', 'Category': 'Category', 'Sub': 'Sub Category', 
                   'Conf': 'Confidence', 'Rating': 'Rating', 'Tags': 'Tags',
                   'BPM': 'BPM', 'Plays': 'Plays', 'Corrections': 'Corrections', 'Verified': 'Verified'}
        
        for col, base_text in columns.items():
            if col == column:
                arrow = ' ↓' if not self.sort_reverse else ' ↑'
            else:
                arrow = ' ↕'
            self.library_tree.heading(col, text=base_text + arrow)
        
        # Sort the data
        self.sort_current_files(column)
        self.update_library_tree()
    
    def sort_current_files(self, column):
        """Sort current files by the specified column"""
        column_map = {
            'File': 'filename',
            'Category': 'main_category', 
            'Sub': 'sub_category',
            'Conf': 'main_confidence',
            'Rating': 'user_rating',
            'Tags': 'user_tags',
            'BPM': 'bpm',
            'Plays': 'play_count',
            'Corrections': 'correction_count',
            'Verified': 'user_verified'
        }
        
        sort_key = column_map.get(column, 'filename')
        
        def get_sort_value(file_data):
            value = file_data.get(sort_key)
            if value is None:
                return '' if isinstance(value, str) else 0
            return value
        
        self.current_files.sort(key=get_sort_value, reverse=self.sort_reverse)
    
    def batch_correct_selected(self):
        """Apply batch correction to multiple selected files"""
        if not self.selected_files:
            messagebox.showwarning("No Selection", "Please select files to correct.")
            return
        
        if len(self.selected_files) == 1:
            # Single file - use regular correction
            self.correct_selected()
            return
        
        # Show batch correction dialog
        dialog = BatchCorrectionDialog(self.parent.winfo_toplevel(), self.selected_files, 
                                     self.scanner.correction_system)
        self.parent.wait_window(dialog.dialog)
        
        if dialog.result:
            self.apply_batch_correction(self.selected_files, dialog.result)
    
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
            
            # Refresh results to show updated verification status
            self.load_library()
            
        except Exception as e:
            messagebox.showerror("Learning Error", f"Failed to complete learning update: {e}")
    
    def play_selected(self):
        """Play selected audio file"""
        # Store current file ID before playing (selection will be lost during refresh)
        current_file_id = self.selected_file['id'] if self.selected_file else None
        
        # Play the audio
        self.on_file_double_click()
        
        # Restore selection by file ID (since tree items get recreated)
        if current_file_id:
            self._restore_selection_by_file_id(current_file_id)
    
    def open_file_location(self):
        """Open file location in system file manager"""
        if self.selected_file and os.path.exists(self.selected_file['file_path']):
            # Open file location (Mac)
            os.system(f'open -R "{self.selected_file["file_path"]}"')
    
    def rate_selected(self):
        """Quick rate selected file"""
        if not self.selected_file:
            return
        
        rating = simpledialog.askinteger("Rate File", "Enter rating (1-5 stars):", 
                                        minvalue=1, maxvalue=5)
        if rating:
            self.set_rating(rating)
    
    def edit_tags_selected(self):
        """Quick edit tags for selected file"""
        if not self.selected_file:
            return
        
        current_tags = self.selected_file.get('user_tags', '')
        new_tags = simpledialog.askstring("Edit Tags", "Enter tags (comma-separated):", 
                                         initialvalue=current_tags)
        if new_tags is not None:
            self.tags_var.set(new_tags)
            self.save_metadata()
    
    def load_playlists(self):
        """Load playlists into listbox"""
        self.playlist_listbox.delete(0, tk.END)
        
        playlists = self.playlist_manager.get_playlists()
        for playlist in playlists:
            self.playlist_listbox.insert(tk.END, f"{playlist['name']} ({playlist['track_count']})")
    
    def create_playlist(self):
        """Create a new playlist"""
        name = simpledialog.askstring("New Playlist", "Enter playlist name:")
        if name:
            playlist_id = self.playlist_manager.create_playlist(name)
            if playlist_id > 0:
                self.load_playlists()
                messagebox.showinfo("Created", f"Playlist '{name}' created!")
            else:
                messagebox.showerror("Error", "Failed to create playlist.")
    
    def add_to_playlist(self):
        """Add selected file to selected playlist"""
        if not self.selected_file:
            messagebox.showwarning("No File", "Please select a file first.")
            return
        
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Playlist", "Please select a playlist first.")
            return
        
        playlist_idx = selection[0]
        playlists = self.playlist_manager.get_playlists()
        
        if playlist_idx < len(playlists):
            playlist = playlists[playlist_idx]
            
            if self.playlist_manager.add_to_playlist(playlist['id'], self.selected_file['id']):
                self.load_playlists()
                messagebox.showinfo("Added", f"Added to playlist '{playlist['name']}'!")
            else:
                messagebox.showerror("Error", "Failed to add to playlist.")
    
    def play_playlist(self):
        """Play selected playlist"""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Playlist", "Please select a playlist first.")
            return
        
        playlist_idx = selection[0]
        playlists = self.playlist_manager.get_playlists()
        
        if playlist_idx < len(playlists):
            playlist = playlists[playlist_idx]
            tracks = self.playlist_manager.get_playlist_tracks(playlist['id'])
            
            if tracks:
                # Load first track
                first_track = tracks[0]
                if os.path.exists(first_track['file_path']):
                    if self.audio_player.load_file(first_track['file_path'], first_track['id']):
                        self.audio_player.toggle_play()
                        messagebox.showinfo("Playing", f"Playing playlist '{playlist['name']}'")
            else:
                messagebox.showinfo("Empty Playlist", "This playlist has no tracks.")
    
    def apply_batch_correction(self, files: List[Dict], correction: Dict):
        """Apply batch correction to multiple files"""
        try:
            success_count = 0
            error_count = 0
            
            for file_data in files:
                try:
                    # Prepare correction data for each file
                    correction_data = {
                        'file_path': file_data['file_path'],
                        'filename': file_data['filename'],
                        'original_main_category': file_data['main_category'],
                        'original_sub_category': file_data.get('sub_category'),
                        'corrected_main_category': correction['corrected_main_category'],
                        'corrected_sub_category': correction['corrected_sub_category'],
                        'original_main_confidence': file_data['main_confidence'],
                        'original_sub_confidence': file_data.get('sub_confidence', 0.0),
                        'user_notes': correction['user_notes']
                    }
                    
                    # Save correction to learning system
                    self.scanner.correction_system.save_correction(correction_data)
                    
                    # Update the main database with correction
                    self.scanner.update_classification_with_correction(
                        file_data['file_path'], correction_data
                    )
                    
                    success_count += 1
                    
                except Exception as e:
                    print(f"Error correcting {file_data['filename']}: {e}")
                    error_count += 1
            
            # Refresh the display
            self.load_library()
            
            # Show summary message
            if error_count == 0:
                messagebox.showinfo("Batch Correction Complete", 
                                   f"Successfully corrected {success_count} files!\n\n"
                                   f"All files changed to: {correction['corrected_main_category']}")
            else:
                messagebox.showwarning("Batch Correction Complete", 
                                     f"Corrected {success_count} files successfully.\n"
                                     f"{error_count} files had errors.")
            
        except Exception as e:
            messagebox.showerror("Batch Correction Error", f"Failed to apply batch correction: {e}")
    
    def show_export_dialog(self):
        """Show export options dialog"""
        from selecta_library_app_final import ExportDialog
        export_dialog = ExportDialog(self.parent.winfo_toplevel(), self.export_manager, self.current_filters)


class UnifiedScannerView:
    """Enhanced scanner view with AI learning capabilities"""
    
    def __init__(self, parent, scanner: AudioLibraryScannerEnhanced):
        self.parent = parent
        self.scanner = scanner
        self.scan_queue = queue.Queue()
        self.scan_thread = None
        self.is_scanning = False
        
        # Variables
        self.selected_directory = tk.StringVar()
        self.scan_progress = tk.StringVar(value="Ready to scan")
        self.files_processed = tk.IntVar()
        self.total_files = tk.IntVar()
        
        self.create_view()
    
    def create_view(self):
        """Create the scanner interface"""
        self.main_frame = ttk.Frame(self.parent)
        
        # Title
        title_label = ttk.Label(self.main_frame, text="🔍 Audio Scanner with AI Learning", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(20, 30))
        
        # Directory selection
        dir_frame = ttk.LabelFrame(self.main_frame, text="📁 Select Music Directory", padding="15")
        dir_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        dir_entry_frame = ttk.Frame(dir_frame)
        dir_entry_frame.pack(fill=tk.X)
        
        ttk.Label(dir_entry_frame, text="Directory:").pack(side=tk.LEFT)
        dir_entry = ttk.Entry(dir_entry_frame, textvariable=self.selected_directory, width=60)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        
        browse_btn = ttk.Button(dir_entry_frame, text="Browse", command=self.browse_directory)
        browse_btn.pack(side=tk.RIGHT)
        
        # Control buttons
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(pady=20)
        
        self.scan_btn = ttk.Button(control_frame, text="🚀 Start Scan", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_scan, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress section
        progress_frame = ttk.LabelFrame(self.main_frame, text="📊 Scan Progress", padding="15")
        progress_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Progress text
        progress_label = ttk.Label(progress_frame, textvariable=self.scan_progress)
        progress_label.pack()
        
        # Results preview
        results_frame = ttk.LabelFrame(self.main_frame, text="🎯 Recent Classifications", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Simple results tree
        columns = ('File', 'Main Category', 'Sub Category', 'Confidence')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=150)
        
        # Scrollbar
        tree_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    def pack(self, **kwargs):
        """Pack the main frame"""
        self.main_frame.pack(**kwargs)
    
    def browse_directory(self):
        """Browse for directory to scan"""
        directory = filedialog.askdirectory(
            title="Select Music Directory to Scan",
            initialdir=os.path.expanduser("~")
        )
        if directory:
            self.selected_directory.set(directory)
    
    def start_scan(self):
        """Start scanning the selected directory"""
        if not self.selected_directory.get():
            messagebox.showwarning("No Directory", "Please select a directory to scan.")
            return
        
        if not os.path.exists(self.selected_directory.get()):
            messagebox.showerror("Invalid Directory", "Selected directory does not exist.")
            return
        
        # Clear previous results display
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
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
            self.parent.after(100, self.check_queue)
    
    def add_result_to_tree(self, result):
        """Add classification result to the tree view"""
        filename = result['filename']
        main_cat = result['main_category']
        sub_cat = result.get('sub_category', '')
        main_conf = f"{result['main_confidence']:.3f}"
        
        self.results_tree.insert('', 'end', values=(
            filename, main_cat, sub_cat, main_conf
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
        
        messagebox.showinfo("Scan Complete", 
                           f"Successfully classified {processed} audio files!\n\n"
                           f"Switch to the Library tab to view, rate, and correct classifications.")
    
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


class SelectaUnifiedApp:
    """Main unified application combining all features"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎵 Selecta Unified - Complete Audio Library Manager with AI Learning")
        self.root.geometry("1500x1000")
        
        # Backend
        self.scanner = AudioLibraryScannerEnhanced()
        
        self.setup_ui()
        self.load_models()
    
    def setup_ui(self):
        """Setup the unified user interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Library Management tab (main interface)
        library_frame = ttk.Frame(self.notebook)
        self.notebook.add(library_frame, text="📚 Library Manager")
        
        self.library_view = UnifiedLibraryView(library_frame, self.scanner)
        self.library_view.pack(fill=tk.BOTH, expand=True)
        
        # Scanner tab for discovering new music
        scanner_frame = ttk.Frame(self.notebook)
        self.notebook.add(scanner_frame, text="🔍 Audio Scanner")
        
        self.scanner_view = UnifiedScannerView(scanner_frame, self.scanner)
        self.scanner_view.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready - Unified Audio Library Manager with AI Learning")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    def load_models(self):
        """Load classification models"""
        self.status_var.set("Loading AI classification models...")
        
        try:
            if self.scanner.load_classifier():
                self.status_var.set("✅ AI models loaded - Full functionality available")
            else:
                self.status_var.set("⚠️ AI models not loaded - Limited functionality")
                messagebox.showwarning("Model Warning", 
                                     "AI classification models could not be loaded.\n"
                                     "You can still manage your library, but classification features will be limited.")
        except Exception as e:
            self.status_var.set(f"❌ Model error: {e}")
            messagebox.showerror("Model Error", f"Error loading models: {e}")
    
    def run(self):
        """Start the application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    print("🎵 Starting Selecta Unified App...")
    print("Features included:")
    print("  ✅ AI Audio Classification with Learning")
    print("  ✅ User Corrections & Feedback System")
    print("  ✅ Comprehensive Library Management")
    print("  ✅ Audio Playback with Cross-platform Support")
    print("  ✅ Metadata Editing & Rating System")
    print("  ✅ Playlist Management")
    print("  ✅ Advanced Search & Filtering")
    print("  ✅ Export & Organization Tools")
    print()
    
    app = SelectaUnifiedApp()
    app.run()


if __name__ == '__main__':
    main()

