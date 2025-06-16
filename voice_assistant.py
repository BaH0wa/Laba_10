import requests
import pyaudio
import json
import os
import time
import random
import re
import tempfile
import threading
from vosk import Model, KaldiRecognizer
from gtts import gTTS
import pygame


pygame.mixer.init()

is_playing = False
stop_playback = False


def speak(text, lang='ru'):
    global is_playing, stop_playback

    if is_playing:
        stop_playback = True
        time.sleep(0.5)

    stop_playback = False
    is_playing = True

    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=True, suffix='.mp3') as fp:
            tts.save(f"{fp.name}")

            pygame.mixer.music.load(f"{fp.name}")
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy() and not stop_playback:
                time.sleep(0.1)

            pygame.mixer.music.stop()

    except Exception as e:
        print(f"Ошибка TTS: {e}")
        print(text)

    is_playing = False


def find_vosk_model():
    model_dir = "model"

    subdirs = [d for d in os.listdir(model_dir) if os.path.isdir(os.path.join(model_dir, d))]

    if subdirs:
        return os.path.join(model_dir, subdirs[0])

    # Если файлы модели находятся прямо в model/
    if os.path.exists(os.path.join(model_dir, "conf")):
        return model_dir

    raise Exception("Модель Vosk не найдена!")


current_text = ""


def create_text():
    global current_text
    try:
        response = requests.get(
            "https://fish-text.ru/get",
            params={"type": "paragraph", "number": 3},
            timeout=5
        )
        data = response.json()
        if data["status"] == "success":
            current_text = data["text"]
            return "Текст успешно создан"
        else:
            raise Exception("API вернул ошибку")
    except Exception as e:
        print(f"Ошибка API: {e}")
        paragraphs = [
            "Локально сгенерированный текст",
            "Это текст создан локально, так как сервис генерации текста недоступен.",
            "Голосовой ассистент продолжает работать в автономном режиме.",
            "Вы можете использовать команды: прочесть, сохранить или текст.",
            f"Случайное число: {random.randint(100, 999)}"
        ]
        current_text = "\n".join(paragraphs)
        return "Текст создан локально"


def read_text():
    global current_text
    return current_text if current_text else "Текст не создан"


def save_html():
    global current_text
    if current_text:
        os.makedirs("output", exist_ok=True)
        with open("output/output.html", "w", encoding="utf-8") as f:
            f.write(f"<html><body><p>{current_text.replace('\n', '</p><p>')}</p></body></html>")
        return "Файл сохранён как HTML"
    return "Нет текста для сохранения"


def save_txt():
    global current_text
    if current_text:
        clean_text = re.sub('<[^<]+?>', '', current_text)
        os.makedirs("output", exist_ok=True)
        with open("output/output.txt", "w", encoding="utf-8") as f:
            f.write(clean_text)
        return "Файл сохранён как текст"
    return "Нет текста для сохранения"


def recognize_speech():
    try:
        model_path = find_vosk_model()
        print(f"Используется модель: {model_path}")
        model = Model(model_path)
    except Exception as e:
        speak(f"Ошибка загрузки модели: {e}")
        print(f"Ошибка: {e}")
        return

    recognizer = KaldiRecognizer(model, 16000)
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=8192
    )

    print("\nГотов к приему команд... Произнесите:")
    print("- 'создать' - загрузить новый текст")
    print("- 'прочесть' - озвучить текст")
    print("- 'сохранить' - сохранить как HTML")
    print("- 'текст' - сохранить как TXT")
    print("- 'стоп' - остановить чтение")
    print("- 'выход' - завершить работу\n")

    time.sleep(1)

    try:
        while True:
            data = stream.read(4096, exception_on_overflow=False)
            if len(data) == 0:
                break

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                command = result.get("text", "").lower()
                print(f"Распознано: {command}")

                if "создать" in command:
                    response = create_text()
                    speak(response)

                elif "прочесть" in command:
                    text_to_speak = read_text()
                    clean_text = re.sub('<[^<]+?>', '', text_to_speak)
                    threading.Thread(target=speak, args=(clean_text,)).start()

                elif "сохранить" in command:
                    response = save_html()
                    speak(response)

                elif "текст" in command:
                    response = save_txt()
                    speak(response)

                elif "стоп" in command:
                    global stop_playback
                    stop_playback = True
                    speak("Чтение остановлено")

                elif "выход" in command:
                    speak("До свидания!")
                    break

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    if not os.path.exists("model"):
        print("ОШИБКА: Папка 'model' не существует!")
        print("Скачайте модель с https://alphacephei.com/vosk/models")
        print("Распакуйте архив так, чтобы файлы модели находились в папке 'model'")
        exit(1)

    speak("Ассистент запущен. Ожидаю команд.")
    recognize_speech()
    pygame.mixer.quit()