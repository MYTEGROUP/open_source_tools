# VoiceIds.py
import os
import pickle
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
import uuid
from helpers.Manage_Json_files import JSONManager  # Adjust the import based on your project structure
from pathlib import Path


class VoiceManager:
    def __init__(self, profiles_dir='voice_profiles', profiles_file='voice_profiles.pkl'):
        """
        Initializes the VoiceManager with a directory and file to store voice profiles.
        """
        self.encoder = VoiceEncoder()
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(exist_ok=True)
        self.profiles_path = self.profiles_dir / profiles_file
        self.profiles = []
        self.load_profiles()

    def load_profiles(self):
        """
        Loads existing voice profiles from the profiles file.
        """
        if self.profiles_path.exists():
            try:
                with open(self.profiles_path, 'rb') as f:
                    self.profiles = pickle.load(f)
                JSONManager.log_event("VoiceManager", f"Loaded {len(self.profiles)} voice profiles.")
            except Exception as e:
                JSONManager.log_event("VoiceManager Error", f"Error loading voice profiles: {e}")
                self.profiles = []
        else:
            self.profiles = []
            JSONManager.log_event("VoiceManager", "No existing voice profiles found. Starting fresh.")

    def save_profiles(self):
        """
        Saves the current voice profiles to the profiles file.
        """
        try:
            with open(self.profiles_path, 'wb') as f:
                pickle.dump(self.profiles, f)
            JSONManager.log_event("VoiceManager", "Voice profiles saved successfully.")
        except Exception as e:
            JSONManager.log_event("VoiceManager Error", f"Error saving voice profiles: {e}")

    def get_embedding(self, audio_file_path):
        """
        Generates a voice embedding for a given audio file.
        """
        try:
            wav = preprocess_wav(audio_file_path)
            embedding = self.encoder.embed_utterance(wav)
            return embedding
        except Exception as e:
            JSONManager.log_event("VoiceManager Error", f"Error getting embedding for {audio_file_path}: {e}")
            return None

    def match_voice(self, audio_file_path, tolerance=0.6):
        """
        Matches an audio chunk to existing voice profiles or creates a new profile if no match is found.

        Args:
            audio_file_path (str): Path to the audio file.
            tolerance (float): Distance threshold for matching.

        Returns:
            str: The speaker ID.
        """
        embedding = self.get_embedding(audio_file_path)
        if embedding is None:
            return None
        # Compare with existing profiles
        if not self.profiles:
            # No profiles exist, create a new one
            new_id = self.create_new_profile(embedding)
            return new_id
        embeddings = np.array([profile['embedding'] for profile in self.profiles])
        distances = np.linalg.norm(embeddings - embedding, axis=1)
        min_distance = np.min(distances)
        min_index = np.argmin(distances)
        if min_distance < tolerance:
            # Match found
            matched_id = self.profiles[min_index]['id']
            JSONManager.log_event("VoiceManager", f"Voice matched with ID: {matched_id} (distance: {min_distance})")
            return matched_id
        else:
            # No match, create a new profile
            new_id = self.create_new_profile(embedding)
            return new_id

    def create_new_profile(self, embedding):
        """
        Creates a new voice profile with a unique ID.

        Args:
            embedding (np.ndarray): The voice embedding.

        Returns:
            str: The new speaker ID.
        """
        new_id = str(uuid.uuid4())
        self.profiles.append({'id': new_id, 'embedding': embedding})
        self.save_profiles()
        JSONManager.log_event("VoiceManager", f"Created new voice profile with ID: {new_id}")
        return new_id
