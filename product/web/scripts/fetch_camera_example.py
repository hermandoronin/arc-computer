"""Fetch a pinned Espressif example; make only documented local configuration edits."""
from pathlib import Path
import hashlib
import io
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '94afccf35fb1e401facddbcf9e13bcf7c76a31d8'
BASE = f'https://raw.githubusercontent.com/espressif/arduino-esp32/{COMMIT}/'
FILES = ['CameraWebServer.ino', 'app_httpd.cpp', 'board_config.h', 'camera_index.h', 'camera_pins.h', 'partitions.csv']
records = []
archive = ROOT / 'dist/assets/firmware/esp32-camera-3.3.12.zip'
archive.parent.mkdir(parents=True, exist_ok=True)
readme = '''ARC: локальная камера AI-Thinker ESP32-CAM

Исходник: Espressif CameraWebServer из Arduino-ESP32 3.3.12.
Commit: 94afccf35fb1e401facddbcf9e13bcf7c76a31d8
https://github.com/espressif/arduino-esp32/tree/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer

Изменения ARC: в board_config.h выбран только CAMERA_MODEL_AI_THINKER;
ssid и password в CameraWebServer.ino оставлены пустыми. Других изменений нет.
Установи esp32 by Espressif Systems 3.3.12. Открой всю папку CameraWebServer,
а не отдельный скетч. Выбери AI Thinker ESP32-CAM, раздел приложения >=3 MB.
Укажи SSID и пароль локально; не публикуй файл с паролем.

UART: TX адаптера (3,3 V) -> U0R; RX -> U0T; GND общий.
Питание платы: внешний стабилизированный источник 5 V на 5V, не на GPIO.
GPIO0 -> GND только на время Reset/загрузки. После записи убери перемычку,
нажми Reset, открой Serial Monitor 115200 и локальный адрес из лога.

Образец предназначен для доверенной локальной сети. Запись, тревоги и
защищённый удалённый доступ не настроены. Сборка прошивки и запуск на железе
в рамках ARC не выполнены. Проверь модель, уровни и питание перед запуском.

Исходная лицензия Espressif находится в UPSTREAM-LICENSE.md.
'''
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for filename in FILES:
        url = BASE + 'libraries/ESP32/examples/Camera/CameraWebServer/' + filename
        original = urllib.request.urlopen(url, timeout=30).read()
        text = original.decode()
        if filename == 'board_config.h':
            assert '\n#define CAMERA_MODEL_ESP_EYE' in text
            assert '\n//#define CAMERA_MODEL_AI_THINKER' in text
            text = text.replace('\n#define CAMERA_MODEL_ESP_EYE', '\n//#define CAMERA_MODEL_ESP_EYE').replace('\n//#define CAMERA_MODEL_AI_THINKER', '\n#define CAMERA_MODEL_AI_THINKER')
        if filename == 'CameraWebServer.ino':
            import re
            text, n = re.subn(r'const char \*(ssid|password) = "[^"]*";', r'const char *\1 = "";', text)
            assert n == 2, 'Unexpected upstream Wi-Fi declarations'
        content = text.encode()
        z.writestr('CameraWebServer/' + filename, content)
        records.append(dict(file=filename, source_url=url, upstream_sha256=hashlib.sha256(original).hexdigest(), packaged_sha256=hashlib.sha256(content).hexdigest()))
    license_bytes = urllib.request.urlopen(BASE + 'LICENSE.md',timeout=30).read()
    z.writestr('CameraWebServer/UPSTREAM-LICENSE.md',license_bytes)
    z.writestr('CameraWebServer/ARC-READ-ME.txt',readme)
manifest = dict(commit=COMMIT, release='3.3.12', compiled=False, hardware_tested=False, files=records,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(ROOT / 'research/evidence/firmware-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Prepared {archive.name}: {archive.stat().st_size} bytes')
