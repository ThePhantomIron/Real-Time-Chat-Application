"""Speech-to-text helpers for the chat composer."""

from __future__ import annotations

import os
import subprocess


class SpeechToTextError(RuntimeError):
    """Raised when speech capture starts but transcription fails."""


class SpeechToTextUnavailable(SpeechToTextError):
    """Raised when no supported speech backend is available."""


def transcribe_once(timeout: int = 8, phrase_limit: int = 12) -> str:
    """
    Capture one spoken phrase and return the transcript.

    Prefer the optional ``speech_recognition`` package when installed.
    On Windows, fall back to the built-in System.Speech engine.
    """

    transcript = _transcribe_with_speech_recognition(timeout, phrase_limit)
    if transcript is not None:
        return transcript
    return _transcribe_with_windows_speech(timeout)


def _transcribe_with_speech_recognition(timeout: int, phrase_limit: int) -> str | None:
    try:
        import speech_recognition as sr
    except ImportError:
        return None

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_limit,
            )
    except OSError as exc:
        raise SpeechToTextUnavailable(
            "No microphone was detected. Connect one and try again."
        ) from exc
    except sr.WaitTimeoutError as exc:
        raise SpeechToTextError(
            "No speech was detected. Press Mic and start speaking right away."
        ) from exc

    try:
        text = recognizer.recognize_google(audio).strip()
    except sr.UnknownValueError as exc:
        raise SpeechToTextError(
            "I could not understand the audio. Please try again."
        ) from exc
    except sr.RequestError as exc:
        raise SpeechToTextError(
            "The speech recognition service is unavailable right now."
        ) from exc

    if not text:
        raise SpeechToTextError("No speech was recognized. Please try again.")
    return text


def _transcribe_with_windows_speech(timeout: int) -> str:
    if os.name != "nt":
        raise SpeechToTextUnavailable(
            "Voice input needs the 'SpeechRecognition' and 'PyAudio' packages on this platform."
        )

    script = f"""
Add-Type -AssemblyName System.Speech
$recognizerInfo = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object {{ $_.Culture.Name -eq 'en-US' }} |
    Select-Object -First 1
if (-not $recognizerInfo) {{
    $recognizerInfo = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
        Select-Object -First 1
}}
if (-not $recognizerInfo) {{
    throw 'No Windows speech recognizer is installed.'
}}
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($recognizerInfo)
try {{
    $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
    $engine.SetInputToDefaultAudioDevice()
    $result = $engine.Recognize([TimeSpan]::FromSeconds({timeout}))
    if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) {{
        throw 'No speech detected before timeout.'
    }}
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $result.Text
}} finally {{
    $engine.Dispose()
}}
"""

    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            startupinfo=startupinfo,
            creationflags=creationflags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SpeechToTextError(
            "Voice capture timed out. Press Mic and speak a little sooner."
        ) from exc

    text = (result.stdout or "").strip()
    if result.returncode == 0 and text:
        return text

    details = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    ).lower()

    if "default audio device" in details or "microphone" in details:
        raise SpeechToTextUnavailable(
            "No working microphone was found. Check your audio input settings and try again."
        )
    if "no windows speech recognizer" in details:
        raise SpeechToTextUnavailable(
            "Windows speech recognition is not installed on this machine."
        )
    if "no speech detected" in details:
        raise SpeechToTextError(
            "No speech was detected. Press Mic and speak after the button changes state."
        )

    raise SpeechToTextError("Voice transcription failed. Please try again.")
