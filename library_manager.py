#!/usr/bin/env python3
"""
Selecta Library Manager - Enhanced music library management with metadata
"""

import os
import sqlite3
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

class LibraryManager:
    """Enhanced library management with metadata, ratings, tags, and playlists"""
    
    def __init__(self, db_path: str = "selecta_library_enhanced.db"):
        self.db_path = db_path
        self.current_filter = {}
        
    def update_metadata(self, file_id: int, **metadata) -> bool:
        """Update metadata for a file"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build dynamic update query
            update_fields = []
            values = []
            
            for field, value in metadata.items():
                if field in ['user_rating', 'user_tags', 'user_notes', 'bpm', 
                           'key_signature', 'energy_level', 'duration_seconds']:
                    update_fields.append(f"{field} = ?")
                    values.append(value)
            
            if update_fields:
                values.append(file_id)
                query = f"UPDATE audio_files SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, values)
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error updating metadata: {e}")
            return False
    
    def get_library_with_metadata(self, filters: Dict = None, search_term: str = None, 
                                 limit: int = None, offset: int = 0) -> List[Dict]:
        """Get library files with metadata and optional filtering"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Base query
            query = '''
                SELECT id, file_path, filename, file_size, main_category, sub_category, 
                       main_confidence, sub_confidence, user_rating, user_tags, user_notes,
                       bpm, key_signature, energy_level, last_played, play_count,
                       duration_seconds, file_format, correction_count, user_verified,
                       created_at, updated_at
                FROM audio_files
                WHERE 1=1
            '''
            
            params = []
            
            # Add filters
            if filters:
                if filters.get('main_category'):
                    query += " AND main_category = ?"
                    params.append(filters['main_category'])
                
                if filters.get('sub_category'):
                    query += " AND sub_category = ?"
                    params.append(filters['sub_category'])
                
                if filters.get('min_rating'):
                    query += " AND user_rating >= ?"
                    params.append(filters['min_rating'])
                
                if filters.get('verified_only'):
                    query += " AND user_verified = TRUE"
                
                if filters.get('has_tags'):
                    query += " AND user_tags IS NOT NULL AND user_tags != ''"
            
            # Add search
            if search_term:
                query += " AND (filename LIKE ? OR user_tags LIKE ? OR user_notes LIKE ?)"
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern, search_pattern])
            
            # Add ordering
            query += " ORDER BY filename"
            
            # Add pagination
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'file_path': row[1],
                    'filename': row[2],
                    'file_size': row[3],
                    'main_category': row[4],
                    'sub_category': row[5],
                    'main_confidence': row[6],
                    'sub_confidence': row[7],
                    'user_rating': row[8],
                    'user_tags': row[9],
                    'user_notes': row[10],
                    'bpm': row[11],
                    'key_signature': row[12],
                    'energy_level': row[13],
                    'last_played': row[14],
                    'play_count': row[15],
                    'duration_seconds': row[16],
                    'file_format': row[17],
                    'correction_count': row[18],
                    'user_verified': row[19],
                    'created_at': row[20],
                    'updated_at': row[21]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Error getting library: {e}")
            return []
    
    def get_file_by_id(self, file_id: int) -> Optional[Dict]:
        """Get a single file by ID"""
        files = self.get_library_with_metadata()
        for file in files:
            if file['id'] == file_id:
                return file
        return None
    
    def update_play_stats(self, file_id: int):
        """Update play count and last played timestamp"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE audio_files 
                SET play_count = play_count + 1, 
                    last_played = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (file_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error updating play stats: {e}")
            return False
    
    def get_library_stats(self) -> Dict:
        """Get comprehensive library statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM audio_files")
            stats['total_files'] = cursor.fetchone()[0]
            
            # Category breakdown
            cursor.execute('''
                SELECT main_category, COUNT(*) 
                FROM audio_files 
                WHERE main_category IS NOT NULL
                GROUP BY main_category
            ''')
            stats['main_categories'] = dict(cursor.fetchall())
            
            # Rating distribution
            cursor.execute('''
                SELECT user_rating, COUNT(*) 
                FROM audio_files 
                WHERE user_rating > 0
                GROUP BY user_rating
            ''')
            stats['rating_distribution'] = dict(cursor.fetchall())
            
            # Verified vs unverified
            cursor.execute("SELECT user_verified, COUNT(*) FROM audio_files GROUP BY user_verified")
            verification_data = dict(cursor.fetchall())
            stats['verified_count'] = verification_data.get(True, 0)
            stats['unverified_count'] = verification_data.get(False, 0)
            
            # Files with tags
            cursor.execute("SELECT COUNT(*) FROM audio_files WHERE user_tags IS NOT NULL AND user_tags != ''")
            stats['tagged_files'] = cursor.fetchone()[0]
            
            # Total playtime
            cursor.execute("SELECT SUM(duration_seconds) FROM audio_files WHERE duration_seconds IS NOT NULL")
            total_seconds = cursor.fetchone()[0] or 0
            stats['total_duration_hours'] = total_seconds / 3600
            
            # Average rating
            cursor.execute("SELECT AVG(user_rating) FROM audio_files WHERE user_rating > 0")
            stats['average_rating'] = cursor.fetchone()[0] or 0
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"Error getting library stats: {e}")
            return {}
    
    def search_tags(self, tag_query: str) -> List[str]:
        """Search for existing tags (for autocomplete)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT user_tags 
                FROM audio_files 
                WHERE user_tags IS NOT NULL AND user_tags != '' AND user_tags LIKE ?
            ''', (f"%{tag_query}%",))
            
            all_tags = set()
            for row in cursor.fetchall():
                tags = row[0].split(',')
                for tag in tags:
                    tag = tag.strip().lower()
                    if tag_query.lower() in tag:
                        all_tags.add(tag)
            
            conn.close()
            return sorted(list(all_tags))
            
        except Exception as e:
            print(f"Error searching tags: {e}")
            return []
    
    def get_similar_files(self, file_id: int, limit: int = 10) -> List[Dict]:
        """Find similar files based on category, tags, and rating"""
        file_data = self.get_file_by_id(file_id)
        if not file_data:
            return []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find files with similar attributes
            query = '''
                SELECT id, filename, main_category, sub_category, user_rating, user_tags,
                       main_confidence, sub_confidence
                FROM audio_files 
                WHERE id != ? AND (
                    (main_category = ? AND sub_category = ?) OR
                    (user_rating = ? AND user_rating > 0) OR
                    (user_tags LIKE ? AND user_tags IS NOT NULL)
                )
                ORDER BY 
                    CASE WHEN main_category = ? AND sub_category = ? THEN 3 ELSE 0 END +
                    CASE WHEN user_rating = ? THEN 2 ELSE 0 END +
                    CASE WHEN user_tags LIKE ? THEN 1 ELSE 0 END DESC,
                    main_confidence DESC
                LIMIT ?
            '''
            
            tag_pattern = f"%{file_data.get('user_tags', '')}%" if file_data.get('user_tags') else "%"
            
            cursor.execute(query, (
                file_id,
                file_data['main_category'],
                file_data['sub_category'],
                file_data['user_rating'],
                tag_pattern,
                file_data['main_category'],
                file_data['sub_category'],
                file_data['user_rating'],
                tag_pattern,
                limit
            ))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'filename': row[1],
                    'main_category': row[2],
                    'sub_category': row[3],
                    'user_rating': row[4],
                    'user_tags': row[5],
                    'main_confidence': row[6],
                    'sub_confidence': row[7]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Error finding similar files: {e}")
            return []

class PlaylistManager:
    """Playlist management system"""
    
    def __init__(self, db_path: str = "selecta_library_enhanced.db"):
        self.db_path = db_path
    
    def create_playlist(self, name: str, description: str = "") -> int:
        """Create a new playlist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO playlists (name, description)
                VALUES (?, ?)
            ''', (name, description))
            
            playlist_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return playlist_id
            
        except Exception as e:
            print(f"Error creating playlist: {e}")
            return -1
    
    def get_playlists(self) -> List[Dict]:
        """Get all playlists"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT p.id, p.name, p.description, p.created_at, 
                       COUNT(pt.file_id) as track_count
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                GROUP BY p.id, p.name, p.description, p.created_at
                ORDER BY p.name
            ''')
            
            playlists = []
            for row in cursor.fetchall():
                playlists.append({
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'created_at': row[3],
                    'track_count': row[4]
                })
            
            conn.close()
            return playlists
            
        except Exception as e:
            print(f"Error getting playlists: {e}")
            return []
    
    def add_to_playlist(self, playlist_id: int, file_id: int) -> bool:
        """Add a file to a playlist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get next position
            cursor.execute('''
                SELECT COALESCE(MAX(position), 0) + 1 
                FROM playlist_tracks 
                WHERE playlist_id = ?
            ''', (playlist_id,))
            
            position = cursor.fetchone()[0]
            
            # Add track
            cursor.execute('''
                INSERT INTO playlist_tracks (playlist_id, file_id, position)
                VALUES (?, ?, ?)
            ''', (playlist_id, file_id, position))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error adding to playlist: {e}")
            return False
    
    def get_playlist_tracks(self, playlist_id: int) -> List[Dict]:
        """Get tracks in a playlist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT af.id, af.filename, af.main_category, af.sub_category,
                       af.user_rating, af.duration_seconds, pt.position
                FROM playlist_tracks pt
                JOIN audio_files af ON pt.file_id = af.id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            ''', (playlist_id,))
            
            tracks = []
            for row in cursor.fetchall():
                tracks.append({
                    'file_id': row[0],
                    'filename': row[1],
                    'main_category': row[2],
                    'sub_category': row[3],
                    'user_rating': row[4],
                    'duration_seconds': row[5],
                    'position': row[6]
                })
            
            conn.close()
            return tracks
            
        except Exception as e:
            print(f"Error getting playlist tracks: {e}")
            return []

class ExportManager:
    """Export system for organized directories and playlists"""
    
    def __init__(self, library_manager: LibraryManager):
        self.library_manager = library_manager
    
    def export_organized_structure(self, destination: str, filters: Dict = None, 
                                 copy_files: bool = True, create_symlinks: bool = False) -> Dict:
        """Export files in organized directory structure"""
        try:
            destination_path = Path(destination)
            destination_path.mkdir(parents=True, exist_ok=True)
            
            # Get filtered files
            files = self.library_manager.get_library_with_metadata(filters)
            
            export_stats = {
                'total_files': len(files),
                'copied_files': 0,
                'skipped_files': 0,
                'errors': []
            }
            
            for file_data in files:
                try:
                    source_path = Path(file_data['file_path'])
                    
                    # Create category structure
                    category_dir = destination_path / file_data['main_category']
                    if file_data['sub_category']:
                        category_dir = category_dir / file_data['sub_category']
                    
                    category_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Destination file path
                    dest_file_path = category_dir / file_data['filename']
                    
                    # Copy or link file
                    if copy_files and source_path.exists():
                        if not dest_file_path.exists():
                            import shutil
                            shutil.copy2(source_path, dest_file_path)
                            export_stats['copied_files'] += 1
                        else:
                            export_stats['skipped_files'] += 1
                    
                    elif create_symlinks and source_path.exists():
                        if not dest_file_path.exists():
                            dest_file_path.symlink_to(source_path)
                            export_stats['copied_files'] += 1
                        else:
                            export_stats['skipped_files'] += 1
                            
                except Exception as e:
                    export_stats['errors'].append(f"Error with {file_data['filename']}: {e}")
            
            # Create metadata file
            metadata_file = destination_path / "selecta_export_info.json"
            export_info = {
                'export_date': datetime.now().isoformat(),
                'export_stats': export_stats,
                'filters_applied': filters or {},
                'source_database': self.library_manager.db_path
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(export_info, f, indent=2)
            
            return export_stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def export_playlist_m3u(self, playlist_id: int, destination: str, playlist_manager: PlaylistManager) -> bool:
        """Export playlist as M3U file"""
        try:
            tracks = playlist_manager.get_playlist_tracks(playlist_id)
            playlist_info = next((p for p in playlist_manager.get_playlists() if p['id'] == playlist_id), None)
            
            if not playlist_info:
                return False
            
            m3u_path = Path(destination) / f"{playlist_info['name']}.m3u"
            
            with open(m3u_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                f.write(f"#PLAYLIST:{playlist_info['name']}\n\n")
                
                for track in tracks:
                    # Get full file data
                    file_data = self.library_manager.get_file_by_id(track['file_id'])
                    if file_data and os.path.exists(file_data['file_path']):
                        duration = int(file_data.get('duration_seconds', 0))
                        f.write(f"#EXTINF:{duration},{track['filename']}\n")
                        f.write(f"{file_data['file_path']}\n")
            
            return True
            
        except Exception as e:
            print(f"Error exporting M3U: {e}")
            return False

