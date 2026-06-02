import queue
import threading

import numpy as np
import pyaudio
from faster_whisper import WhisperModel

from seneca.utils.config import config


class SpeechToTextService:
    def __init__(self, on_transcription_complete: callable, on_error: callable):
        self._on_transcription_complete = on_transcription_complete
        self._on_error = on_error

        self._model = None
        self._recording_thread = None
        self._transcription_thread = None
        self._audio_queue = queue.Queue()
        self._recording = False
        self._pyaudio_instance = pyaudio.PyAudio()

        self._load_whisper_model()

    def _load_whisper_model(self):
        try:
            print(f"Loading Whisper model: {config.whisper_model_size}, device: {config.whisper_device}, compute_type: {config.whisper_compute_type}")
            self._model = WhisperModel(
                config.whisper_model_size,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type
            )
            print("Whisper model loaded successfully.")
        except Exception as e:
            self._on_error(f"Failed to load Whisper model: {e}")
            self._model = None # Ensure model is None if loading fails

    def start_recording(self):
        if self._recording:
            return

        self._recording = True
        self._audio_queue = queue.Queue() # Clear any previous audio
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
            self._on_transcription_complete("") # No audio recorded

    def _record_audio_task(self):
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000 # 16kHz for Whisper

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
        if not self._model:
            self._on_error("Whisper model not loaded.")
            return

        # Collect all audio data from the queue
        audio_data = []
        while not self._audio_queue.empty():
            audio_data.append(self._audio_queue.get())
        
        if not audio_data:
            self._on_transcription_complete("")
            return

        # Convert raw audio bytes to numpy array (float32)
        # pyaudio.paInt16 means 2 bytes per sample
        audio_bytes = b''.join(audio_data)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0 # Normalize to [-1, 1]

        try:
            segments, info = self._model.transcribe(audio_np, beam_size=5)
            transcription = "".join(segment.text for segment in segments)
            self._on_transcription_complete(transcription)
        except Exception as e:
            self._on_error(f"Error during transcription: {e}")

    def is_recording(self):
        return self._recording

    def __del__(self):
        # Clean up PyAudio resources when the service is destroyed
        if hasattr(self, '_pyaudio_instance'):
            self._pyaudio_instance.terminate()
