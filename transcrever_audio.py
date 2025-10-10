import speech_recognition as sr
from pydub import AudioSegment
import os

# Caminho do seu arquivo MP3
mp3_path = os.path.expanduser('~/Downloads/IC5_L3_Unit 05 Pg 034 Ex 09 Listening.mp3')
wav_path = 'audio.wav'

# Convertendo MP3 para WAV
print('Convertendo MP3 para WAV...')
audio = AudioSegment.from_mp3(mp3_path)
audio.export(wav_path, format='wav')

# Transcrição com SpeechRecognition
recognizer = sr.Recognizer()

with sr.AudioFile(wav_path) as source:
    audio_data = recognizer.record(source)
    try:
        print('Transcrevendo áudio...')
        text = recognizer.recognize_google(audio_data, language='en-US')
        print(f"Transcrição: {text}")
    except sr.UnknownValueError:
        print("Google Speech Recognition não conseguiu entender o áudio.")
    except sr.RequestError as e:
        print(f"Não foi possível requisitar resultados do Google Speech Recognition; {e}") 