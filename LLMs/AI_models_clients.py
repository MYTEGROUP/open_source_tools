# AI_models_clients.py
import base64
import time
import os
import sys
from openai import OpenAI
from src.config.config import OPENAI_API_KEY, STATIC_DIR
from src.utilities.Manage_Json_files import JSONManager

# Declare openai_client at the module level
openai_client = None
def get_base_path():
    """Determine and return the base path for application data."""
    if getattr(sys, 'frozen', False):
        # If running in a PyInstaller bundle
        return os.path.dirname(sys.executable)
    else:
        # If running in a normal Python environment (not bundled)
        # Use the utilities two levels up from this file's utilities
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.abspath(os.path.join(current_dir, os.pardir))
        return base_path

def initialize_openai_client():
    global openai_client
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        print("API key is not set. Please ensure the API key is correctly saved.")
        openai_client = None


def generate_text(system_context, assistant_context, initial_prompt):
    if not openai_client:
        initialize_openai_client()
    if not openai_client:
        # If the OpenAI client is not initialized, return a placeholder message or perform another fallback behavior
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences.", 0

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            temperature=0.1,
            max_tokens=16300,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "assistant", "content": assistant_context},
                {"role": "user", "content": initial_prompt}
            ]
        )

        # Print total token consumption
        total_tokens = response.usage.total_tokens
        JSONManager.log_event('generate_text', f"Total tokens used: {total_tokens}")

        return response.choices[0].message.content, total_tokens

    except Exception as e:
        error_message = f"An error occurred while generating text: {e}"
        JSONManager.log_event('generate_text', error_message)
        return f"An error occurred while generating text: {e}. Please check the OpenAI API key and try again.", 0

def generate_text_mini(system_context, assistant_context, initial_prompt):
    if not openai_client:
        initialize_openai_client()
    if not openai_client:
        # If the OpenAI client is not initialized, return a placeholder message or perform another fallback behavior
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences.", 0

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=16300,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "assistant", "content": assistant_context},
                {"role": "user", "content": initial_prompt}
            ]
        )

        # Print total token consumption
        total_tokens = response.usage.total_tokens
        JSONManager.log_event('generate_text', f"Total tokens used: {total_tokens}")

        return response.choices[0].message.content, total_tokens

    except Exception as e:
        error_message = f"An error occurred while generating text: {e}"
        JSONManager.log_event('generate_text', error_message)
        return f"An error occurred while generating text: {e}. Please check the OpenAI API key and try again.", 0

def generate_text_mini_json(system_context, assistant_context, initial_prompt):
    if not openai_client:
        initialize_openai_client()
    if not openai_client:
        # If the OpenAI client is not initialized, return a placeholder message or perform another fallback behavior
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences.", 0

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=16300,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_context},
                {"role": "assistant", "content": assistant_context},
                {"role": "user", "content": initial_prompt}
            ]
        )

        # Print total token consumption
        total_tokens = response.usage.total_tokens
        JSONManager.log_event('generate_text', f"Total tokens used: {total_tokens}")

        return response.choices[0].message.content, total_tokens

    except Exception as e:
        error_message = f"An error occurred while generating text: {e}"
        JSONManager.log_event('generate_text', error_message)
        return f"An error occurred while generating text: {e}. Please check the OpenAI API key and try again.", 0


def generate_text_json(system_context, assistant_context, initial_prompt):
    initialize_openai_client()
    if not openai_client:
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    retries = 0
    max_retries = 10  # Retry up to 10 times
    retry_delay = 6  # Wait for 6 seconds before retrying

    while retries < max_retries:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                temperature=0.1,
                max_tokens=15000,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_context},
                    {"role": "assistant", "content": assistant_context},
                    {"role": "user", "content": initial_prompt}
                ]
            )

            total_tokens = response.usage.total_tokens
            JSONManager.log_event('generate_text_json', f"Total tokens used: {total_tokens}")

            return response.choices[0].message.content, total_tokens

        except Exception as e:
            error_message = str(e)
            JSONManager.log_event('generate_text_json', f"Error occurred: {error_message}")

            if "rate limit" in error_message.lower():
                retries += 1
                JSONManager.log_event('rate_limit_retry', f"Rate limit error. Retrying {retries}/{max_retries} after {retry_delay} seconds.")
                time.sleep(retry_delay)
            else:
                JSONManager.log_event('generate_text_json', f"Non-retryable error: {error_message}")
                return f"An error occurred: {error_message}", 0

    # If max retries are exhausted
    final_error_message = "Rate limit exceeded. Please try again later."
    JSONManager.log_event('generate_text_json', final_error_message)
    return final_error_message, 0


def generate_text_json_o1(system_context, assistant_context, initial_prompt, model="o1-mini"):
    print("werre in")
    initialize_openai_client()
    if not openai_client:
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    retries = 0
    max_retries = 10  # Retry up to 10 times
    retry_delay = 6  # Wait for 6 seconds before retrying

    model_name = model

    while retries < max_retries:
        try:
            # Check if the model supports the 'system' role
            models_without_system_role = ["o1-mini", "o1-preview"]  # Add other user_model if necessary
            if model_name in models_without_system_role:
                # Append system context to assistant context
                combined_assistant_context = f"{system_context}\n\n{assistant_context}"
                messages = [
                    {"role": "assistant", "content": combined_assistant_context},
                    {"role": "user", "content": initial_prompt}
                ]
            else:
                messages = [
                    {"role": "system", "content": system_context},
                    {"role": "assistant", "content": assistant_context},
                    {"role": "user", "content": initial_prompt}
                ]

            response = openai_client.chat.completions.create(
                model=model_name,
                messages=messages
            )

            total_tokens = response.usage.total_tokens
            JSONManager.log_event('generate_text_json', f"Total tokens used: {total_tokens}")

            return response.choices[0].message.content, total_tokens

        except Exception as e:
            error_message = str(e)
            JSONManager.log_event('generate_text_json', f"Error occurred: {error_message}")

            if "rate limit" in error_message.lower():
                retries += 1
                JSONManager.log_event('rate_limit_retry', f"Rate limit error. Retrying {retries}/{max_retries} after {retry_delay} seconds.")
                time.sleep(retry_delay)
            else:
                JSONManager.log_event('generate_text_json', f"Non-retryable error: {error_message}")
                return f"An error occurred: {error_message}", 0

    # If max retries are exhausted
    final_error_message = "Rate limit exceeded. Please try again later."
    JSONManager.log_event('generate_text_json', final_error_message)
    return final_error_message, 0




def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def vision(image_path, system_context, assistant_context, initial_prompt):
    initialize_openai_client()
    if not openai_client:
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    base64_image = encode_image(image_path)

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_context},
            {"role": "assistant", "content": assistant_context},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{initial_prompt}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ]
    )
    return response.choices[0].message.content

def vision_text(image_path, system_context, assistant_context, initial_prompt):
    initialize_openai_client()
    if not openai_client:
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    base64_image = encode_image(image_path)

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_context},
            {"role": "assistant", "content": assistant_context},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{initial_prompt}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ]
    )
    return response.choices[0].message.content


def text_to_speech(text, output_path):
    """
       Converts text to speech using the AI model and saves the output as an audio file.
       :param text: The text to be converted to speech
       :param output_path: The file path to save the audio output
    """


    initialize_openai_client()
    if not openai_client:
        # If the OpenAI client is not initialized, return a placeholder message or perform another fallback behavior
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    # Define the full path to the static utilities
    static_dir = STATIC_DIR

    # Ensure the static utilities exists
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # Define the full path to the audio file within the static utilities
    audio_file_path = output_path

    # Generate the audio speech
    response = openai_client.audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=text
    )

    # Save the audio file to the specified path
    response.stream_to_file(audio_file_path)

    return audio_file_path

def transcribe_voice_to_text(audio_file_path):
    initialize_openai_client()
    if not openai_client:
        raise Exception("OpenAI client is not initialized. Please set the OpenAI API key in User Preferences.")
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        print("API Response:", transcript)  # Print the response to verify

        return transcript  # Directly return the transcript
    except Exception as e:
        raise e


def text_to_speech_file(input_text, filename="InitialGreeting.mp3"):
    initialize_openai_client()
    if not openai_client:
        return "OpenAI client is not initialized. Please set the OpenAI API key in User Preferences."

    # Determine the base path of the application
    base_path = get_base_path()

    # Define the full path to the static utilities
    static_dir = os.path.join(base_path, 'static')

    # Ensure the static utilities exists
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # Define the full path to the audio file within the static utilities
    audio_file_path = os.path.join(static_dir, filename)

    # Generate the audio speech
    response = openai_client.audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=input_text
    )

    # Save the response content directly to a file
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(response.content)

    return audio_file_path
