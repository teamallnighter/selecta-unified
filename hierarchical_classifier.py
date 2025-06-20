#!/usr/bin/env python3
"""
Hierarchical Audio Classification System for Selecta
Supports main categories and subcategories with multiple classification strategies
"""

import os
import numpy as np
import pandas as pd
import librosa
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class HierarchicalAudioClassifier:
    """Multi-level audio classification system"""
    
    def __init__(self, strategy='cascade'):
        """
        Initialize hierarchical classifier
        
        Strategies:
        - 'cascade': Main category first, then subcategory
        - 'flat': Single model with all subcategories  
        - 'ensemble': Multiple models per main category
        """
        self.strategy = strategy
        self.main_model = None
        self.sub_models = {}
        self.scalers = {}
        self.label_encoders = {}
        self.category_structure = {}
        
    def extract_enhanced_features(self, file_path, sr=22050, n_mfcc=13):
        """Extract comprehensive audio features - same as main classifier"""
        try:
            # Load audio
            y, sr = librosa.load(file_path, sr=sr, duration=30.0)
            
            if len(y) == 0:
                return None
                
            # Basic features
            features = []
            
            # MFCCs (13 coefficients)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
            features.extend([
                np.mean(mfccs, axis=1),
                np.std(mfccs, axis=1),
                np.max(mfccs, axis=1),
                np.min(mfccs, axis=1)
            ])
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            features.extend([
                np.mean(spectral_centroids),
                np.std(spectral_centroids)
            ])
            
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            features.extend([
                np.mean(spectral_rolloff),
                np.std(spectral_rolloff)
            ])
            
            zero_crossings = librosa.feature.zero_crossing_rate(y)[0]
            features.extend([
                np.mean(zero_crossings),
                np.std(zero_crossings)
            ])
            
            # Tempo and rhythm
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            features.append(tempo)
            
            # Chroma features
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            features.extend([
                np.mean(chroma, axis=1),
                np.std(chroma, axis=1)
            ])
            
            # Spectral contrast
            contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
            features.extend([
                np.mean(contrast, axis=1),
                np.std(contrast, axis=1)
            ])
            
            # Flatten all features
            flattened_features = []
            for feature in features:
                if isinstance(feature, np.ndarray):
                    flattened_features.extend(feature.flatten())
                else:
                    flattened_features.append(feature)
            
            return np.array(flattened_features)
            
        except Exception as e:
            print(f"Error extracting features from {file_path}: {e}")
            return None
    
    def load_hierarchical_data(self, data_dir='data/new_sub_categories_large'):
        """Load hierarchical training data"""
        print(f"📂 Loading hierarchical data from {data_dir}...")
        
        features_list = []
        main_labels = []
        sub_labels = []
        full_labels = []  # main_category/sub_category
        
        # Build category structure
        self.category_structure = {}
        
        # Scan directory structure
        data_path = Path(data_dir)
        if not data_path.exists():
            raise ValueError(f"Data directory {data_dir} not found")
        
        total_samples = 0
        processed_samples = 0
        
        for main_cat_dir in data_path.iterdir():
            if not main_cat_dir.is_dir():
                continue
                
            main_category = main_cat_dir.name
            self.category_structure[main_category] = []
            
            print(f"\n🎵 Processing {main_category} category...")
            
            for sub_cat_dir in main_cat_dir.iterdir():
                if not sub_cat_dir.is_dir():
                    continue
                    
                sub_category = sub_cat_dir.name
                self.category_structure[main_category].append(sub_category)
                
                # Count and process wav files
                wav_files = list(sub_cat_dir.glob('*.wav'))
                total_samples += len(wav_files)
                
                print(f"   📁 {sub_category}: {len(wav_files)} samples")
                
                for wav_file in wav_files:
                    features = self.extract_enhanced_features(str(wav_file))
                    if features is not None:
                        features_list.append(features)
                        main_labels.append(main_category)
                        sub_labels.append(sub_category)
                        full_labels.append(f"{main_category}/{sub_category}")
                        processed_samples += 1
                    
                    # Progress update
                    if processed_samples % 100 == 0:
                        print(f"      Processed {processed_samples}/{total_samples} samples")
        
        print(f"\n✅ Successfully processed {processed_samples}/{total_samples} samples")
        print(f"📊 Category structure: {self.category_structure}")
        
        if processed_samples == 0:
            raise ValueError("No samples were successfully processed!")
        
        return np.array(features_list), main_labels, sub_labels, full_labels
    
    def train_cascade_strategy(self, X, main_labels, sub_labels):
        """Train cascade strategy: main category first, then subcategories"""
        print("\n🔄 Training CASCADE strategy...")
        
        # 1. Train main category classifier
        print("\n1️⃣ Training main category classifier...")
        
        # Split data for main categories
        X_train, X_test, y_main_train, y_main_test, y_sub_train, y_sub_test = train_test_split(
            X, main_labels, sub_labels, test_size=0.2, random_state=42, stratify=main_labels
        )
        
        # Scale features for main model
        main_scaler = StandardScaler()
        X_train_scaled = main_scaler.fit_transform(X_train)
        X_test_scaled = main_scaler.transform(X_test)
        
        # Encode main category labels
        main_le = LabelEncoder()
        y_main_train_encoded = main_le.fit_transform(y_main_train)
        y_main_test_encoded = main_le.transform(y_main_test)
        
        # Train main classifier (Random Forest - our best performer)
        self.main_model = RandomForestClassifier(
            n_estimators=200, 
            max_depth=20, 
            min_samples_split=2,
            random_state=42,
            n_jobs=-1
        )
        
        self.main_model.fit(X_train_scaled, y_main_train_encoded)
        
        # Evaluate main model
        main_pred = self.main_model.predict(X_test_scaled)
        main_accuracy = accuracy_score(y_main_test_encoded, main_pred)
        
        print(f"   ✅ Main category accuracy: {main_accuracy:.1%}")
        
        # Store main model components
        self.scalers['main'] = main_scaler
        self.label_encoders['main'] = main_le
        
        # 2. Train subcategory classifiers for each main category
        print("\n2️⃣ Training subcategory classifiers...")
        
        for main_category in self.category_structure.keys():
            # Get samples for this main category
            main_cat_indices = [i for i, label in enumerate(main_labels) if label == main_category]
            
            if len(main_cat_indices) < 10:  # Skip if too few samples
                print(f"   ⚠️ Skipping {main_category}: insufficient samples ({len(main_cat_indices)})")
                continue
                
            # Extract subcategory data
            X_sub = X[main_cat_indices]
            y_sub = [sub_labels[i] for i in main_cat_indices]
            
            # Check if we have multiple subcategories
            unique_subcats = list(set(y_sub))
            if len(unique_subcats) < 2:
                print(f"   ⚠️ Skipping {main_category}: only one subcategory ({unique_subcats})")
                continue
            
            print(f"   🎯 Training {main_category} subcategory classifier...")
            print(f"      Subcategories: {unique_subcats}")
            print(f"      Samples: {len(X_sub)}")
            
            # Split subcategory data
            if len(X_sub) > 10:
                X_sub_train, X_sub_test, y_sub_train, y_sub_test = train_test_split(
                    X_sub, y_sub, test_size=0.2, random_state=42, stratify=y_sub
                )
            else:
                # Use all data for training if very small dataset
                X_sub_train, X_sub_test = X_sub, X_sub
                y_sub_train, y_sub_test = y_sub, y_sub
            
            # Scale subcategory features
            sub_scaler = StandardScaler()
            X_sub_train_scaled = sub_scaler.fit_transform(X_sub_train)
            X_sub_test_scaled = sub_scaler.transform(X_sub_test)
            
            # Encode subcategory labels
            sub_le = LabelEncoder()
            y_sub_train_encoded = sub_le.fit_transform(y_sub_train)
            y_sub_test_encoded = sub_le.transform(y_sub_test)
            
            # Train subcategory classifier
            sub_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                min_samples_split=2,
                random_state=42,
                n_jobs=-1
            )
            
            sub_model.fit(X_sub_train_scaled, y_sub_train_encoded)
            
            # Evaluate subcategory model
            if len(X_sub_test) > 0:
                sub_pred = sub_model.predict(X_sub_test_scaled)
                sub_accuracy = accuracy_score(y_sub_test_encoded, sub_pred)
                print(f"      ✅ {main_category} subcategory accuracy: {sub_accuracy:.1%}")
            
            # Store subcategory model components
            self.sub_models[main_category] = sub_model
            self.scalers[main_category] = sub_scaler
            self.label_encoders[main_category] = sub_le
        
        print(f"\n🎉 Cascade training completed!")
        print(f"   📊 Main categories: {len(self.label_encoders['main'].classes_)}")
        print(f"   🎯 Subcategory models: {len(self.sub_models)}")
        
        return {
            'main_accuracy': main_accuracy,
            'sub_models_trained': len(self.sub_models),
            'strategy': 'cascade'
        }
    
    def predict_cascade(self, audio_file_path):
        """Predict using cascade strategy"""
        if self.main_model is None:
            raise ValueError("Models not trained. Call train() first.")
        
        # Extract features
        features = self.extract_enhanced_features(audio_file_path)
        if features is None:
            raise ValueError("Could not extract features from audio")
        
        feature_array = features.reshape(1, -1)
        
        # 1. Predict main category
        main_features_scaled = self.scalers['main'].transform(feature_array)
        main_pred_encoded = self.main_model.predict(main_features_scaled)[0]
        main_category = self.label_encoders['main'].inverse_transform([main_pred_encoded])[0]
        
        # Get main category confidence
        main_probabilities = self.main_model.predict_proba(main_features_scaled)[0]
        main_confidence = np.max(main_probabilities)
        
        # 2. Predict subcategory if model exists
        sub_category = None
        sub_confidence = 0.0
        sub_probabilities = {}
        
        if main_category in self.sub_models:
            sub_features_scaled = self.scalers[main_category].transform(feature_array)
            sub_pred_encoded = self.sub_models[main_category].predict(sub_features_scaled)[0]
            sub_category = self.label_encoders[main_category].inverse_transform([sub_pred_encoded])[0]
            
            # Get subcategory confidence
            sub_probs = self.sub_models[main_category].predict_proba(sub_features_scaled)[0]
            sub_confidence = np.max(sub_probs)
            
            # Build subcategory probability breakdown
            for i, subcat in enumerate(self.label_encoders[main_category].classes_):
                sub_probabilities[subcat] = float(sub_probs[i])
        
        # Build main category probability breakdown
        main_prob_breakdown = {}
        for i, cat in enumerate(self.label_encoders['main'].classes_):
            main_prob_breakdown[cat] = float(main_probabilities[i])
        
        return {
            'main_category': main_category,
            'sub_category': sub_category,
            'full_prediction': f"{main_category}/{sub_category}" if sub_category else main_category,
            'main_confidence': float(main_confidence),
            'sub_confidence': float(sub_confidence),
            'main_probabilities': main_prob_breakdown,
            'sub_probabilities': sub_probabilities
        }
    
    def save_models(self, timestamp=None):
        """Save all trained models"""
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        model_data = {
            'strategy': self.strategy,
            'category_structure': self.category_structure,
            'timestamp': timestamp
        }
        
        # Save main model
        if self.main_model:
            joblib.dump(self.main_model, f'hierarchical_main_model_{timestamp}.pkl')
            model_data['main_model_file'] = f'hierarchical_main_model_{timestamp}.pkl'
        
        # Save sub models
        for main_cat, sub_model in self.sub_models.items():
            filename = f'hierarchical_sub_{main_cat}_model_{timestamp}.pkl'
            joblib.dump(sub_model, filename)
            model_data[f'sub_model_{main_cat}'] = filename
        
        # Save scalers
        for name, scaler in self.scalers.items():
            filename = f'hierarchical_scaler_{name}_{timestamp}.pkl'
            joblib.dump(scaler, filename)
            model_data[f'scaler_{name}'] = filename
        
        # Save label encoders
        for name, le in self.label_encoders.items():
            filename = f'hierarchical_le_{name}_{timestamp}.pkl'
            joblib.dump(le, filename)
            model_data[f'le_{name}'] = filename
        
        # Save model metadata
        with open(f'hierarchical_models_info_{timestamp}.json', 'w') as f:
            json.dump(model_data, f, indent=2)
        
        print(f"💾 Hierarchical models saved with timestamp: {timestamp}")
        return timestamp
    
    def load_models(self, timestamp):
        """Load all trained models"""
        info_file = f'hierarchical_models_info_{timestamp}.json'
        
        if not os.path.exists(info_file):
            raise ValueError(f"Model info file {info_file} not found")
        
        with open(info_file, 'r') as f:
            model_data = json.load(f)
        
        self.strategy = model_data['strategy']
        self.category_structure = model_data['category_structure']
        
        # Load main model
        if 'main_model_file' in model_data:
            self.main_model = joblib.load(model_data['main_model_file'])
        
        # Load sub models
        for key, filename in model_data.items():
            if key.startswith('sub_model_'):
                main_cat = key.replace('sub_model_', '')
                self.sub_models[main_cat] = joblib.load(filename)
            elif key.startswith('scaler_'):
                name = key.replace('scaler_', '')
                self.scalers[name] = joblib.load(filename)
            elif key.startswith('le_'):
                name = key.replace('le_', '')
                self.label_encoders[name] = joblib.load(filename)
        
        print(f"✅ Hierarchical models loaded from timestamp: {timestamp}")
        print(f"📊 Strategy: {self.strategy}")
        print(f"🎯 Main categories: {list(self.category_structure.keys())}")
        print(f"🔧 Sub models: {list(self.sub_models.keys())}")

def main():
    """Train hierarchical classifier"""
    print("🎵 HIERARCHICAL AUDIO CLASSIFICATION TRAINING")
    print("=" * 60)
    
    # Initialize classifier
    classifier = HierarchicalAudioClassifier(strategy='cascade')
    
    try:
        # Load hierarchical data
        X, main_labels, sub_labels, full_labels = classifier.load_hierarchical_data()
        
        print(f"\n📊 Data Summary:")
        print(f"   Total samples: {len(X)}")
        print(f"   Features per sample: {X.shape[1]}")
        print(f"   Main categories: {len(set(main_labels))}")
        print(f"   Total subcategories: {len(set(sub_labels))}")
        
        # Train cascade strategy
        results = classifier.train_cascade_strategy(X, main_labels, sub_labels)
        
        # Save models
        timestamp = classifier.save_models()
        
        print(f"\n🎉 Hierarchical training completed!")
        print(f"📊 Results: {results}")
        print(f"💾 Models saved with timestamp: {timestamp}")
        
        return classifier, timestamp
        
    except Exception as e:
        print(f"❌ Training failed: {e}")
        raise

if __name__ == '__main__':
    classifier, timestamp = main()

