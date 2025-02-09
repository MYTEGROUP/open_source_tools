#src.utilities.Manage_Json_files.py

import os
import sys
import json
from datetime import datetime
import threading

class JSONManager:
    _lock = threading.Lock()  # A lock to handle concurrent file access

    @staticmethod
    def get_base_dir():
        """Determine the base directory path, handling both .exe and Python environments."""
        if getattr(sys, 'frozen', False):
            # If running in a PyInstaller bundle (.exe)
            return os.path.dirname(sys.executable)
        else:
            # If running in a standard Python environment
            return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    @staticmethod
    def get_storage_dir():
        """Determine the storage directory path."""
        return os.path.join(JSONManager.get_base_dir(), 'storage')

    @staticmethod
    def get_static_dir():
        """Determine the static directory path."""
        return os.path.join(JSONManager.get_base_dir(), 'static')

    @staticmethod
    def get_json_path(filename):
        """Get the full path for a JSON file in the storage directory."""
        return os.path.join(JSONManager.get_storage_dir(), filename)

    @staticmethod
    def read_json_file_with_default(filename, default=None):
        """Read a JSON file and return a default value if the file does not exist or is empty."""
        data = JSONManager.read_json_file(filename)
        return data if data else default

    @staticmethod
    def write_json_file(filename, data):
        """Write data to a JSON file, ensuring the directory and file exist."""
        file_path = JSONManager.get_json_path(filename)
        temp_file_path = file_path + '.tmp'

        os.makedirs(JSONManager.get_storage_dir(), exist_ok=True)

        try:
            with JSONManager._lock:
                # Write to a temporary file first
                with open(temp_file_path, 'w') as file:
                    json.dump(data, file, indent=4)
                # Rename the temporary file to the target file
                os.replace(temp_file_path, file_path)
            JSONManager.log_event("write_json_file", f"Successfully wrote to {filename}")
            return True
        except Exception as e:
            JSONManager.log_event("write_json_file", f"Failed to write to {filename}: {str(e)}")
            return False

    @staticmethod
    def read_json_file(filename):
        """Read a JSON file, ensuring it exists before reading."""
        file_path = JSONManager.get_json_path(filename)

        if not os.path.exists(file_path):
            return {}

        try:
            with JSONManager._lock:
                with open(file_path, 'r') as file:
                    return json.load(file)
        except json.JSONDecodeError:
            JSONManager.log_event("read_json_file", f"Failed to decode JSON in {filename}")
            return {}
        except Exception as e:
            JSONManager.log_event("read_json_file", f"Failed to read {filename}: {str(e)}")
            return {}

    @staticmethod
    def write_text_file(file_path, data):
        """Write data to a text file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(data)
            JSONManager.log_event("write_text_file", f"Successfully wrote to {file_path.name}")
            return True
        except Exception as e:
            JSONManager.log_event("write_text_file", f"Failed to write to {file_path.name}: {str(e)}")
            return False

    @staticmethod
    def read_text_file(file_path):
        """Read a text file."""
        if not file_path.exists():
            return ""

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            JSONManager.log_event("read_text_file", f"Failed to read {file_path.name}: {str(e)}")
            return ""

    @staticmethod
    def save_key_value(filename, key, value):
        """Save a key-value pair to the specified JSON file."""
        try:
            data = JSONManager.read_json_file(filename)
            data.setdefault(key, []).append(value)
            JSONManager.write_json_file(filename, data)
            JSONManager.log_event("save_key_value", f"Saved {key}: {value} to {filename}")
        except Exception as e:
            JSONManager.log_event("save_key_value", f"Failed to save {key}: {value} to {filename}: {str(e)}")
            raise

    @staticmethod
    def save_user_email(filename, email):
        try:
            data = JSONManager.read_json_file(filename)
            if 'user_id' in data:
                data['email'] = email
            else:
                data = {'emails': [email]}

            JSONManager.write_json_file(filename, data)
            JSONManager.log_event("save_user_email", f"Saved email {email} to {filename}")
        except Exception as e:
            JSONManager.log_event("save_user_email", f"Failed to save email {email} to {filename}: {str(e)}")
            raise

    @staticmethod
    def log_event(step, message):
        """Logs events and errors to a JSON file."""
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'step': step,
            'message': message
        }
        log_file_path = JSONManager.get_json_path('BackendLog.json')

        os.makedirs(JSONManager.get_storage_dir(), exist_ok=True)

        try:
            with JSONManager._lock:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Critical error: Unable to write log: {str(e)}")

    @staticmethod
    def log_stripe_event(step, message, status):
        """Logs Stripe events and errors to a JSON file."""
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'step': step,
            'message': message,
            'status': status  # Add status to indicate success or failure
        }
        log_file_path = JSONManager.get_json_path('StripeLog.json')

        # Ensure the storage directory exists
        os.makedirs(JSONManager.get_storage_dir(), exist_ok=True)

        try:
            with JSONManager._lock:
                # Append the log entry to the log file
                with open(log_file_path, 'a') as log_file:
                    log_file.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            # If logging fails, there should be some way to notify or handle it
            print(f"Critical error: Unable to write log: {str(e)}")

    @staticmethod
    def save_todo_list(instructions):
        """Save the AI instructions to 'TodoList.json' with 'is_completed: False'."""
        success = JSONManager.write_json_file('TodoList.json', instructions)
        JSONManager.log_event("save_todo_list", "Saved TodoList.json")
        if not success:
            JSONManager.log_event("save_todo_list", "Failed to save TodoList.json")

    @staticmethod
    def update_profile_picture_status(status):
        """
        Update the 'profile_picture' status in user_info.json.
        """
        try:
            user_info = JSONManager.read_json_file('user_info.json')
            user_info['profile_picture'] = status
            JSONManager.write_json_file('user_info.json', user_info)
            JSONManager.log_event("update_profile_picture_status", f"Profile picture status updated to {status}.")
        except Exception as e:
            JSONManager.log_event("update_profile_picture_status_error", f"Error updating profile picture status: {e}")

    @staticmethod
    def update_meeting(meeting_data):
        """
        Update an existing meeting entry in the Meetings.json file.
        Matching is based on meeting_title and date.
        """
        try:
            with JSONManager._lock:
                file_path = JSONManager.get_json_path('Meetings.json')
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        meetings_data = json.load(f)
                else:
                    meetings_data = {"meetings": []}

                # Find the meeting to update
                for i, m in enumerate(meetings_data["meetings"]):
                    if m["meeting_title"] == meeting_data["meeting_title"] and m["date"] == meeting_data["date"]:
                        # Update the meeting data
                        meetings_data["meetings"][i] = meeting_data
                        break
                else:
                    # Meeting not found, append it
                    meetings_data["meetings"].append(meeting_data)

                # Write back to JSON
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(meetings_data, f, ensure_ascii=False, indent=4)

            JSONManager.log_event("update_meeting",
                                  f"Meeting '{meeting_data['meeting_title']}' on {meeting_data['date']} updated successfully.")
            return True
        except Exception as e:
            JSONManager.log_event("update_meeting", f"Error updating meeting: {e}")
            return False
