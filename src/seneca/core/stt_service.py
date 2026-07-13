import io
import queue
import threading
import wave

import pyaudio

from seneca.api.client import SenecaApiClient, SenecaApiError
from seneca.utils.config import config


class SpeechToTextService:
    def __init__(self, on_transcription_complete: callable, on_error: callable):
        self._on_transcription_complete = on_transcription_complete
        self._on_error = on_error

        self._client = SenecaApiClient(
            base_url=config.seneca_api_base_url,
            api_key=config.seneca_ai_api_key
        )
        self._recording_thread = None
        self._transcription_thread = None
        self._audio_queue = queue.Queue()
        self._recording = False
        self._pyaudio_instance = pyaudio.PyAudio()

    def start_recording(self):
        if self._recording:
            return

        self._recording = True
        self._audio_queue = queue.Queue() # Clear any previous api
        self._recording_thread = threading.Thread(target=self._record_audio_task)
        self._recording_thread.start()
        print("Recording started...")

    def stop_recording(self):
        if not self._recording:
            return

        self._recording = False
        if self._recording_thread:
            self._recording_thread.join() # Wait for recording to finish
        print("Recording stopped. Starting transcription...")
        
        if not self._audio_queue.empty():
            self._transcription_thread = threading.Thread(target=self._transcribe_audio_task)
            self._transcription_thread.start()
        else:
            self._on_transcription_complete("") # No api recorded

    def _record_audio_task(self):
        CHUNK = config.audio_chunk
        FORMAT = pyaudio.paInt16
        CHANNELS = config.audio_channels
        RATE = config.audio_rate # 16kHz for Whisper

        try:
            stream = self._pyaudio_instance.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            while self._recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                self._audio_queue.put(data)
            
            stream.stop_stream()
            stream.close()
        except Exception as e:
            self._on_error(f"Error during audio recording: {e}")
            self._recording = False # Stop recording flag on error

    def _transcribe_audio_task(self):
        # Collect all api data from the queue
        audio_data = []
        while not self._audio_queue.empty():
            audio_data.append(self._audio_queue.get())
        
        if not audio_data:
            self._on_transcription_complete("")
            return

        audio_bytes = b''.join(audio_data)

        # Create an in-memory WAV file
        wav_buffer = io.BytesIO()
        wav_buffer.name = "audio.wav"
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(self._pyaudio_instance.get_sample_size(pyaudio.paInt16))
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)
        
        wav_buffer.seek(0)
        
        # Extract base language from locale (e.g. "es" from "es_ES")
        lang_code = config.app_locale.split('_')[0] if config.app_locale else "en"

        try:
            result = self._client.speech_to_text(audio=wav_buffer, lang=lang_code, filename="audio.wav")
            self._on_transcription_complete(result.text)
        except SenecaApiError as e:
            self._on_error(f"API Error during transcription: {e}")
        except Exception as e:
            self._on_error(f"Error during transcription: {e}")

    def is_recording(self):
        return self._recording

    def __del__(self):
        # Clean up PyAudio resources when the service is destroyed
        if hasattr(self, '_pyaudio_instance'):
            self._pyaudio_instance.terminate()
