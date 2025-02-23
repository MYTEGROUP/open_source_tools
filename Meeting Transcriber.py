# Meeting Transcriber.py
import tkinter as tk
from tkinter import ttk
import threading
import pyaudio
import wave
import time
import os
import uuid
from queue import Queue, Empty
from tkinter import scrolledtext, messagebox
from concurrent.futures import ThreadPoolExecutor
from LLMs.AI_models_clients import transcribe_voice_to_text, generate_text
from helpers.Manage_Json_files import JSONManager
from mongodatabase.mango_connection import save_meeting_data_to_mongo
from bson.son import SON
from helpers.voice_profiler import VoiceManager
from datetime import datetime

# -- NEW IMPORTS FOR PHASE 1 --
from analysis import theme_analysis
from analysis import insights_analysis
from analysis import summary_analysis
from analysis import questions_analysis
from analysis import action_items_analysis
# -----------------------------

# Audio Configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Whisper works well with 16000 Hz

# Transcription and Summarization Configuration
TRANSCRIPTION_INTERVAL = 5  # seconds
OVERLAP_DURATION = 0.5  # seconds

# Maximum number of concurrent threads
MAX_THREADS = 15


class MeetingTranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Meeting Transcriber")
        self.root.state('zoomed')
        self.set_window_icon()
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Main Frame with Notebook for Tabs
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Initialize variables and other UI elements
        self.init_variables()
        self.create_input_frame()
        self.create_tabs()
        self.create_status_bar()

        # Initialize other components (Thread pools, events)
        self.initialize_threads_and_events()

        # Log initialization
        JSONManager.log_event("Initialization", "MeetingTranscriberApp initialized successfully.")

    def init_variables(self):
        # Initialize variables
        self.audio_queue = Queue()
        self.transcript_queue = Queue()
        self.unprocessed_transcriptions = []
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.recorder = None
        self.transcription_thread = None
        self.summarization_thread = None
        self.full_transcript = []
        self.meeting_name = ""
        self.meeting_objective = ""
        self.start_time = None
        self.end_time = None
        self.last_summary_time = time.time()
        self.is_recording = False
        self.is_paused = False
        self.summary = ""
        self.summary_json = {}
        self.insights = {}
        self.gui_update_interval = 1000  # milliseconds
        self.total_tokens = 0
        self.voice_manager = VoiceManager()

        # -- NEW FOR PHASE 1: Parallel analysis structures --
        self.analysis_data = {
            'themes': [],         # from theme_analysis
            'insights': [],       # from insights_analysis
            'summary': "",        # from summary_analysis
            'questions': [],      # from questions_analysis
            'action_items': []    # from action_items_analysis
        }
        # ----------------------------------------------------

    def create_input_frame(self):
        # Input Frame
        self.input_frame = ttk.LabelFrame(self.root, text="Meeting Setup", padding="10")
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)

        # Meeting Name
        self.meeting_name_label = ttk.Label(self.input_frame, text="Meeting Name:")
        self.meeting_name_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.meeting_name_entry = ttk.Entry(self.input_frame, width=50)
        self.meeting_name_entry.grid(row=0, column=1, pady=5, padx=5)

        # Meeting Objective
        self.meeting_objective_label = ttk.Label(self.input_frame, text="Meeting Objective:")
        self.meeting_objective_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.meeting_objective_entry = ttk.Entry(self.input_frame, width=50)
        self.meeting_objective_entry.grid(row=1, column=1, pady=5, padx=5)

        # Control Buttons Frame
        self.controls_frame = ttk.Frame(self.input_frame, padding="10")
        self.controls_frame.grid(row=2, column=0, columnspan=2)

        # Start Recording Button
        self.start_button = ttk.Button(self.controls_frame, text="Start Recording", command=self.start_recording)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        # Stop Recording Button
        self.stop_button = ttk.Button(
            self.controls_frame, text="Stop Recording", command=self.stop_recording_threaded, state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Pause Recording Button
        self.pause_button = ttk.Button(
            self.controls_frame, text="Pause", command=self.pause_recording, state=tk.DISABLED
        )
        self.pause_button.grid(row=0, column=2, padx=5, pady=5)

        # Resume Recording Button
        self.resume_button = ttk.Button(
            self.controls_frame, text="Resume", command=self.resume_recording, state=tk.DISABLED
        )
        self.resume_button.grid(row=0, column=3, padx=5, pady=5)

    def create_tabs(self):
        # Create frames for each tab
        self.tab_meeting_details = ttk.Frame(self.notebook)
        self.tab_transcription = ttk.Frame(self.notebook)
        self.tab_summary = ttk.Frame(self.notebook)
        self.tab_insights = ttk.Frame(self.notebook)
        self.tab_themes = ttk.Frame(self.notebook)
        self.tab_questions = ttk.Frame(self.notebook)
        self.tab_action_items = ttk.Frame(self.notebook)

        # Add tabs to the notebook
        self.notebook.add(self.tab_meeting_details, text="Meeting Details")
        self.notebook.add(self.tab_transcription, text="Transcription")
        self.notebook.add(self.tab_summary, text="Summary")
        self.notebook.add(self.tab_insights, text="Insights")
        self.notebook.add(self.tab_themes, text="Themes")
        self.notebook.add(self.tab_questions, text="Questions")
        self.notebook.add(self.tab_action_items, text="Action Items")

        # Populate each tab with appropriate UI elements
        self.create_meeting_details_tab()
        self.create_transcription_tab()
        self.create_summary_tab()
        self.create_insights_tab()
        self.create_themes_tab()
        self.create_questions_tab()
        self.create_action_items_tab()

    def create_meeting_details_tab(self):
        # Labels to display meeting details
        self.details_text = tk.Text(self.tab_meeting_details, wrap=tk.WORD, state='disabled', font=("Arial", 12))
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_transcription_tab(self):
        # ScrolledText widget to display real-time transcription
        self.transcription_text = scrolledtext.ScrolledText(
            self.tab_transcription, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.transcription_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_summary_tab(self):
        # ScrolledText widget to display the summary
        self.summary_text = scrolledtext.ScrolledText(
            self.tab_summary, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_insights_tab(self):
        self.insights_text = scrolledtext.ScrolledText(
            self.tab_insights, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.insights_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_themes_tab(self):
        self.themes_text = scrolledtext.ScrolledText(
            self.tab_themes, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.themes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_questions_tab(self):
        self.questions_text = scrolledtext.ScrolledText(
            self.tab_questions, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.questions_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_action_items_tab(self):
        self.action_items_text = scrolledtext.ScrolledText(
            self.tab_action_items, wrap=tk.WORD, state='disabled', font=("Arial", 12)
        )
        self.action_items_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_status_bar(self):
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Idle")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def initialize_threads_and_events(self):
        # Thread Pool Executor
        self.executor = ThreadPoolExecutor(max_workers=MAX_THREADS)
        # Directory for saving Meetings.json
        self.storage_dir = JSONManager.get_storage_dir()
        os.makedirs(self.storage_dir, exist_ok=True)
        self.meetings_file = JSONManager.get_json_path('Meetings.json')

    def set_window_icon(self):
        """Set the window icon using LogoIcon.ico from the static directory."""
        try:
            logo_path = os.path.join(JSONManager.get_static_dir(), 'LogoIcon.ico')
            if os.path.exists(logo_path):
                self.root.iconbitmap(logo_path)
                JSONManager.log_event("UI Branding", f"Window icon set to {logo_path}")
            else:
                JSONManager.log_event("UI Branding Error", f"LogoIcon.ico not found at {logo_path}")
        except Exception as e:
            JSONManager.log_event("UI Branding Exception", f"Error setting window icon: {e}")

    def start_recording(self):
        """
        Starts the audio recording, transcription, and summarization processes.
        """
        self.meeting_name = self.meeting_name_entry.get().strip()
        self.meeting_objective = self.meeting_objective_entry.get().strip()
        if not self.meeting_name or not self.meeting_objective:
            messagebox.showwarning(
                "Meeting Information Required", "Please enter a meeting name and objective before starting recording."
            )
            JSONManager.log_event(
                "Start Recording", "Attempted to start recording without a meeting name or objective."
            )
            return

        # Reset variables
        self.full_transcript = []
        self.summary = ""
        self.summary_json = {}
        self.total_tokens = 0
        self.start_time = time.time()
        self.last_summary_time = time.time()
        self.is_recording = True
        self.is_paused = False

        self.stop_event.clear()
        self.pause_event.clear()
        self.audio_queue = Queue()
        self.transcript_queue = Queue()
        self.unprocessed_transcriptions = []

        # -- Reset our parallel analysis data --
        self.analysis_data['themes'] = []
        self.analysis_data['insights'] = []
        self.analysis_data['summary'] = ""
        self.analysis_data['questions'] = []
        self.analysis_data['action_items'] = []
        # --------------------------------------

        # Start the audio recorder
        self.recorder = AudioRecorder(self.audio_queue, self.stop_event, self.pause_event)
        self.recorder.start()
        JSONManager.log_event(
            "Start Recording",
            f"Recording started for meeting: {self.meeting_name}, Objective: {self.meeting_objective}"
        )

        # Start the transcription and summarization threads
        self.transcription_thread = threading.Thread(
            target=self.process_audio_chunks, daemon=True
        )
        self.transcription_thread.start()
        JSONManager.log_event("Start Recording", "Transcription thread started.")

        self.summarization_thread = threading.Thread(
            target=self.process_transcriptions, daemon=True
        )
        self.summarization_thread.start()
        JSONManager.log_event("Start Recording", "Summarization thread started.")

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL)
        self.resume_button.config(state=tk.DISABLED)

        # Start updating the text areas
        self.update_meeting_details_tab()

        self.status_var.set("Recording...")

    def pause_recording(self):
        """
        Pauses the audio recording.
        """
        if self.is_recording and not self.is_paused:
            self.pause_event.set()
            self.is_paused = True
            self.pause_button.config(state=tk.DISABLED)
            self.resume_button.config(state=tk.NORMAL)
            self.status_var.set("Paused")
            JSONManager.log_event("Pause Recording", "Recording paused.")

    def resume_recording(self):
        """
        Resumes the audio recording.
        """
        if self.is_recording and self.is_paused:
            self.pause_event.clear()
            self.is_paused = False
            self.pause_button.config(state=tk.NORMAL)
            self.resume_button.config(state=tk.DISABLED)
            self.status_var.set("Recording...")
            JSONManager.log_event("Resume Recording", "Recording resumed.")

    def stop_recording_and_close(self):
        """
        Stops the recording if active, then closes the application.
        """
        if self.is_recording:
            self.stop_recording_threaded()
        else:
            self.root.destroy()

    def stop_recording_threaded(self):
        """
        Initiates the stop recording process in a separate thread.
        """
        if not self.is_recording:
            return
        self.stop_button.config(state=tk.DISABLED)
        threading.Thread(target=self.stop_recording, daemon=True).start()

    def stop_recording(self):
        """
        Stops the audio recording, processes remaining audio, generates the final summary, and saves data.
        """
        JSONManager.log_event("Stop Recording", "Stop recording initiated.")
        self.is_recording = False
        self.stop_event.set()

        self.status_var.set("Finalizing Summary...")

        # Record end time
        self.end_time = time.time()

        # Process remaining audio in the queue
        while not self.audio_queue.empty():
            audio_data = self.audio_queue.get()
            self.process_audio_data(audio_data)

        if self.transcription_thread:
            self.transcription_thread.join()
        if self.summarization_thread:
            self.summarization_thread.join()

        # Process any unprocessed transcriptions before final summary
        self.process_remaining_transcriptions()

        # -- PHASE 1: We do NOT do any final polishing here yet --
        # We will keep your existing final summary generation, plus we can expand it later.

        # Final summary and save
        final_thread = threading.Thread(target=self.generate_final_summary_and_save, daemon=True)
        final_thread.start()

    def process_audio_chunks(self):
        """
        Processes audio chunks from the audio queue by transcribing and associating with speaker IDs.
        """
        JSONManager.log_event("Transcription", "Audio chunk processing started.")
        while self.is_recording or not self.audio_queue.empty():
            try:
                audio_data = self.audio_queue.get(timeout=1)
                self.executor.submit(self.process_audio_data, audio_data)
            except Empty:
                continue
            except Exception as e:
                JSONManager.log_event(
                    "Transcription Exception", f"Error in process_audio_chunks: {e}"
                )
                continue
        JSONManager.log_event("Transcription", "Audio chunk processing stopped.")

    def process_audio_data(self, audio_data):
        """
        Processes a single audio chunk: saves it, identifies the speaker, transcribes, and associates the transcription with the speaker ID.
        """
        audio_file_path = self.save_audio_to_wav(audio_data)
        if audio_file_path:
            # Identify speaker
            speaker_id = self.voice_manager.match_voice(audio_file_path)
            if not speaker_id:
                speaker_id = "Unknown"

            # Transcribe audio
            transcription = transcribe_voice_to_text(audio_file_path)
            if transcription:
                timestamp = datetime.now().strftime("%H:%M:%S")
                entry = {
                    'timestamp': timestamp,
                    'speaker_id': speaker_id,
                    'text': transcription
                }
                self.full_transcript.append(entry)
                self.transcript_queue.put(transcription)
                self.root.after(0, self.update_transcription_tab, entry)
            # Delete the audio file after transcription
            try:
                os.remove(audio_file_path)
                JSONManager.log_event("Delete Audio File", f"Deleted audio file {audio_file_path}")
            except Exception as e:
                JSONManager.log_event("Delete Audio File Error", f"Error deleting audio file {audio_file_path}: {e}")

    def process_transcriptions(self):
        """
        Processes transcriptions by updating the summary at regular intervals (every 5 seconds).
        Also fans out updates to parallel analysis modules (Phase 1).
        """
        JSONManager.log_event(
            "Summarization", "Transcription processing for summarization started."
        )
        while self.is_recording or not self.transcript_queue.empty():
            try:
                transcription = self.transcript_queue.get(timeout=1)
                if transcription:
                    self.unprocessed_transcriptions.append(transcription)
                    current_time = time.time()
                    if current_time - self.last_summary_time >= TRANSCRIPTION_INTERVAL:
                        combined_text = " ".join(self.unprocessed_transcriptions).strip()
                        self.unprocessed_transcriptions = []  # Clear after accumulating

                        # Update the summary incrementally (as before)
                        self.analysis_data['summary'] = summary_analysis.incremental_update(
                            combined_text, self.analysis_data['summary']
                        )

                        # -- Fan out to other analysis modules in separate threads --
                        # THEMES
                        self.executor.submit(
                            self.update_themes, combined_text
                        )
                        # INSIGHTS
                        self.executor.submit(
                            self.update_insights, combined_text
                        )
                        # QUESTIONS
                        self.executor.submit(
                            self.update_questions, combined_text
                        )
                        # ACTION ITEMS
                        self.executor.submit(
                            self.update_action_items, combined_text
                        )
                        # ---------------------------------------------------------

                        self.last_summary_time = current_time

                        # For now, let's just reflect the summary in the UI
                        self.root.after(0, self.update_summary_tab)

            except Empty:
                continue
            except Exception as e:
                JSONManager.log_event(
                    "Summarization Exception", f"Error in process_transcriptions: {e}"
                )
                continue
        # After processing all transcriptions, update the summary one last time
        self.process_remaining_transcriptions()
        JSONManager.log_event(
            "Summarization", "Transcription processing for summarization stopped."
        )

    def process_remaining_transcriptions(self):
        """
        Processes any remaining transcriptions that haven't been summarized or analyzed yet.
        """
        if self.unprocessed_transcriptions:
            combined_text = " ".join(self.unprocessed_transcriptions).strip()
            self.update_summary(combined_text)
            self.unprocessed_transcriptions = []  # Clear after processing

    def update_summary(self, new_transcription):
        """
        Updates the meeting summary using the summary_analysis.py (placeholder).
        """
        self.analysis_data['summary'] = summary_analysis.incremental_update(
            new_transcription, self.analysis_data['summary']
        )
        # Update the UI
        self.root.after(0, self.update_summary_tab)

    # -- NEW Analysis Update Methods (Phase 1) --
    def update_themes(self, chunk_text):
        """
        Updates the 'themes' list using theme_analysis incremental_update.
        """
        self.analysis_data['themes'] = theme_analysis.incremental_update(
            chunk_text, self.analysis_data['themes']
        )
        self.root.after(0, self.update_themes_tab)

    def update_insights(self, chunk_text):
        """
        Updates the 'insights' list using insights_analysis incremental_update.
        """
        self.analysis_data['insights'] = insights_analysis.incremental_update(
            chunk_text, self.analysis_data['insights']
        )
        self.root.after(0, self.update_insights_tab)

    def update_questions(self, chunk_text):
        """
        Updates the list of open questions using questions_analysis incremental_update.
        """
        self.analysis_data['questions'] = questions_analysis.incremental_update(
            chunk_text, self.analysis_data['questions']
        )
        self.root.after(0, self.update_questions_tab)

    def update_action_items(self, chunk_text):
        """
        Updates the list of action items using action_items_analysis incremental_update.
        """
        self.analysis_data['action_items'] = action_items_analysis.incremental_update(
            chunk_text, self.analysis_data['action_items']
        )
        self.root.after(0, self.update_action_items_tab)
    # --------------------------------------------------

    def update_meeting_details_tab(self):
        """
        Updates the Meeting Details tab with the meeting metadata.
        """
        self.details_text.config(state='normal')
        self.details_text.delete(1.0, tk.END)
        details = f"Title: {self.meeting_name}\n"
        details += f"Objective: {self.meeting_objective}\n"
        details += f"Date: {time.strftime('%Y-%m-%d')}\n"
        details += f"Start Time: {time.strftime('%H:%M:%S', time.localtime(self.start_time))}\n" if self.start_time else ""
        self.details_text.insert(tk.END, details)
        self.details_text.config(state='disabled')

    def update_transcription_tab(self, entry):
        """
        Updates the Transcription tab with the latest transcription entry.
        """
        try:
            self.transcription_text.config(state='normal')
            timestamp = entry['timestamp']
            speaker = entry['speaker_id']
            text = entry['text']
            self.transcription_text.insert(tk.END, f"[{timestamp}] Speaker {speaker}: {text}\n")
            self.transcription_text.see(tk.END)  # Auto-scroll to the end
            self.transcription_text.config(state='disabled')
        except Exception as e:
            JSONManager.log_event("Update Transcription Tab Exception", f"Error updating transcription tab: {e}")

    def generate_final_summary_and_save(self):
        """
        Generates the final meeting summary using the AI LLMs and saves all data.
        """
        # For now, this code remains as is. We'll integrate "final_polish" calls in future phases.
        self.root.after(0, self.show_processing_popup)

        # Wait briefly for concurrency to settle
        time.sleep(2)

        try:
            self.generate_final_summary()  # Possibly a direct call
            JSONManager.log_event("Final Summary", "Final summary generated successfully.")
        except Exception as e:
            JSONManager.log_event("Final Summary Error", f"Error generating final summary: {e}")

        # Save meeting data
        self.save_meeting_data()

        # Calculate total duration
        if self.start_time and self.end_time:
            duration_seconds = self.end_time - self.start_time
            formatted_duration = time.strftime("%H:%M:%S", time.gmtime(duration_seconds))
        else:
            formatted_duration = "00:00:00"

        self.root.after(
            0, lambda: self.update_processing_popup_with_stats(formatted_duration)
        )

    def generate_final_summary(self):
        """
        Stub. In the future, we'll incorporate final polishing of all analysis data.
        For now, we just pass.
        """
        pass

    def show_processing_popup(self):
        """
        Displays a processing popup window during final summary generation.
        """
        self.processing_popup = tk.Toplevel(self.root)
        self.processing_popup.title("Processing")
        self.processing_popup.geometry("400x300")
        self.processing_popup.grab_set()
        self.processing_popup.focus_set()

        self.processing_label = ttk.Label(
            self.processing_popup, text="Finalizing Meeting Summary...", font=("Arial", 12)
        )
        self.processing_label.pack(pady=30)

    def update_processing_popup_with_stats(self, formatted_duration):
        """
        Updates the processing popup with meeting statistics.
        """
        if hasattr(self, 'processing_popup') and self.processing_popup.winfo_exists():
            for widget in self.processing_popup.winfo_children():
                widget.destroy()

            msg = (
                f"Meeting '{self.meeting_name}' has been successfully recorded and summarized.\n\n"
                f"Duration: {formatted_duration}\n"
                f"Total Tokens Processed: {self.total_tokens}\n\n"
                f"You can now review your summary and insights."
            )

            label = ttk.Label(
                self.processing_popup, text=msg, justify=tk.LEFT, font=("Arial", 10)
            )
            label.pack(pady=20, padx=20)

            ok_button = ttk.Button(
                self.processing_popup, text="OK", command=self.on_completion_ok, width=10
            )
            ok_button.pack(pady=10)

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.resume_button.config(state=tk.DISABLED)
        self.status_var.set("Idle")

    def on_completion_ok(self):
        """
        Handles the completion of the processing popup.
        """
        self.processing_popup.destroy()

    def save_audio_to_wav(self, audio_data):
        """
        Saves raw audio data to a WAV file.
        """
        if not audio_data:
            return None
        try:
            static_dir = JSONManager.get_static_dir()
            os.makedirs(static_dir, exist_ok=True)
            filename = f"audio_chunk_{uuid.uuid4()}.wav"
            file_path = os.path.join(static_dir, filename)

            wf = wave.open(file_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_data)
            wf.close()

            JSONManager.log_event("Save Audio to WAV", f"Audio chunk saved to {file_path}")
            return file_path
        except Exception as e:
            JSONManager.log_event("Save Audio to WAV Exception", f"Error saving audio to WAV: {e}")
            return None

    def save_meeting_data(self):
        """
        Saves the meeting data, including transcript and summary, to MongoDB.
        """
        if self.end_time and self.start_time and self.end_time < self.start_time:
            JSONManager.log_event(
                "Save Meeting Data Error",
                "End time is before start time. Adjusting duration to 0."
            )
            duration = 0
        elif self.end_time and self.start_time:
            duration = self.end_time - self.start_time
        else:
            duration = 0

        # Compile full transcript text with speaker IDs and timestamps
        transcript_text = "\n".join([
            f"[{entry['timestamp']}] Speaker {entry['speaker_id']}: {entry['text']}"
            for entry in self.full_transcript
        ])

        meeting_data = SON([
            ("meeting_title", self.meeting_name),
            ("date", time.strftime("%Y-%m-%d")),
            ("start_time", time.strftime("%H:%M:%S", time.localtime(self.start_time)) if self.start_time else ""),
            ("end_time", time.strftime("%H:%M:%S", time.localtime(self.end_time)) if self.end_time else ""),
            ("duration", time.strftime("%H:%M:%S", time.gmtime(duration)) if duration > 0 else "00:00:00"),
            ("full_transcript", transcript_text.strip()),
            ("summary", self.analysis_data['summary']),    # using 'summary' from our analysis data
            ("tokens_used", self.total_tokens),
        ])

        success = save_meeting_data_to_mongo(meeting_data)
        if success:
            JSONManager.log_event(
                "Save to MongoDB", f"Meeting '{self.meeting_name}' data saved successfully."
            )
        else:
            JSONManager.log_event(
                "Save to MongoDB", f"Error saving meeting '{self.meeting_name}' data."
            )

    # -- Phase 1: Basic UI updates for each analysis tab --
    def update_summary_tab(self):
        self.summary_text.config(state='normal')
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, self.analysis_data['summary'])
        self.summary_text.config(state='disabled')

    def update_insights_tab(self):
        self.insights_text.config(state='normal')
        self.insights_text.delete(1.0, tk.END)
        for insight in self.analysis_data['insights']:
            self.insights_text.insert(tk.END, f"- {insight}\n")
        self.insights_text.config(state='disabled')

    def update_themes_tab(self):
        self.themes_text.config(state='normal')
        self.themes_text.delete(1.0, tk.END)
        for theme in self.analysis_data['themes']:
            self.themes_text.insert(tk.END, f"- {theme}\n")
        self.themes_text.config(state='disabled')

    def update_questions_tab(self):
        self.questions_text.config(state='normal')
        self.questions_text.delete(1.0, tk.END)
        for question in self.analysis_data['questions']:
            self.questions_text.insert(tk.END, f"- {question}\n")
        self.questions_text.config(state='disabled')

    def update_action_items_tab(self):
        self.action_items_text.config(state='normal')
        self.action_items_text.delete(1.0, tk.END)
        for action_item in self.analysis_data['action_items']:
            self.action_items_text.insert(tk.END, f"- {action_item}\n")
        self.action_items_text.config(state='disabled')


class AudioRecorder(threading.Thread):
    def __init__(self, audio_queue, stop_event, pause_event):
        """
        Initializes the AudioRecorder thread.
        """
        super().__init__()
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.overlap_buffer = []
        self.chunk_frames = []

    def run(self):
        """
        Starts the audio stream and continuously captures audio until stopped.
        """
        try:
            self.stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            JSONManager.log_event("AudioRecorder", "Audio stream opened successfully.")
            print("Recording started.")

            frames_per_chunk = int((RATE * TRANSCRIPTION_INTERVAL) / CHUNK)
            frames_per_overlap = int((RATE * OVERLAP_DURATION) / CHUNK)

            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    time.sleep(0.1)
                    continue
                try:
                    data = self.stream.read(CHUNK, exception_on_overflow=False)
                    self.chunk_frames.append(data)

                    if len(self.chunk_frames) >= frames_per_chunk:
                        frames = self.overlap_buffer + self.chunk_frames
                        self.overlap_buffer = self.chunk_frames[-frames_per_overlap:]
                        audio_data = b''.join(frames)
                        if audio_data:
                            self.audio_queue.put(audio_data)
                            JSONManager.log_event(
                                "AudioRecorder", "Audio chunk added to queue for transcription."
                            )
                        self.chunk_frames = []
                except Exception as e:
                    JSONManager.log_event(
                        "AudioRecorder Exception", f"Error reading audio stream: {e}"
                    )
                    continue

            # Handle remaining frames when stop_event is set
            if self.chunk_frames:
                frames = self.overlap_buffer + self.chunk_frames
                audio_data = b''.join(frames)
                if audio_data:
                    self.audio_queue.put(audio_data)
                    JSONManager.log_event(
                        "AudioRecorder",
                        "Remaining audio data added to queue for transcription.",
                    )

            print("Recording stopped.")

        except Exception as e:
            JSONManager.log_event(
                "AudioRecorder Exception", f"Failed to open the audio stream: {e}"
            )
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                JSONManager.log_event("AudioRecorder", "Audio stream closed.")
            self.p.terminate()
            JSONManager.log_event("AudioRecorder", "PyAudio terminated.")


def main():
    root = tk.Tk()
    app = MeetingTranscriberApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop_recording_and_close)
    root.mainloop()


if __name__ == "__main__":
    main()
