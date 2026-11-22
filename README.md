# Chess Visual Analyzer

[English](#english) | [Русский](#russian)

---

## English

Real-time visual chess board analyzer built with Python (**OpenCV** + **python-chess** + **PyQt6** + **Stockfish**).  
It captures the board directly from your screen (works on Chess.com, Lichess, and any 2D chess interface) and draws a transparent, click-through overlay highlighting the best move.

### Features
* **Pure Computer Vision:** Works completely outside the browser — no extensions or page injection required.
* **Click-Through Overlay:** Renders clean highlight squares over the board without blocking mouse clicks.
* **One-Key Calibration:** Automatically detects the board grid and extracts piece templates from the starting position.
* **Flexible Modes:** Show the best move for your side only, both sides simultaneously, or the opponent.

### Installation & Usage (Windows)
1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) (make sure to check **Add python.exe to PATH** during installation).
2. Download **Stockfish** for Windows from [stockfishchess.org](https://stockfishchess.org/download/) and place the `.exe` file (or `.zip` archive) inside the project folder.
3. Double-click **`install.bat`** to install all required Python packages.
4. Open a starting chess position (all 32 pieces on their initial squares), run **`start.bat`**, and press **`F9`** to calibrate.

### Hotkeys
* **`F7`** — Switch mode: My side only (1 best move) / Both sides / Opponent only
* **`F8`** — Show / hide overlay squares
* **`F9`** — Calibrate board (press on the starting position)

### Troubleshooting
* **Overlay stops updating mid-game:** If everything worked fine for several moves and suddenly stopped showing suggestions, press **`F7`** a few times (3 times to cycle back to your current mode). This resets the position cache and forces a fresh board scan.
* **Window moved or resized:** Return to a starting position and press **`F9`** to recalibrate.

> **Disclaimer:** This tool is designed for position analysis, studying, and testing against bots. Do not use engine assistance in rated online games against human players.

---

## Русский

Визуальный анализатор шахматной доски в реальном времени на Python (**OpenCV** + **python-chess** + **PyQt6** + **Stockfish**).  
Программа считывает позицию прямо с экрана (работает на Chess.com, Lichess и любых других 2D-досках) и рисует поверх доски прозрачные квадраты с лучшим ходом, не мешая кликам мыши.

### Возможности
* **Компьютерное зрение без вмешательства в браузер:** Не требует расширений и не лезет в код страницы.
* **Прозрачный оверлей:** Подсвечивает фигуру и целевую клетку поверх окна, пропуская все клики сквозь себя.
* **Калибровка одной кнопкой:** Сама находит сетку доски и запоминает фигуры со стартовой позиции.
* **Три режима анализа:** Подсказка только для твоей стороны (1 лучший ход), сразу для обеих сторон или только для соперника.

### Установка и запуск (Windows)
1. Установи **Python 3.10+** с [python.org](https://www.python.org/downloads/) (при установке обязательно поставь галочку **Add python.exe to PATH**).
2. Скачай **Stockfish** для Windows с [stockfishchess.org](https://stockfishchess.org/download/) и положи `.exe` файл (или `.zip` архив) в папку с программой.
3. Запусти **`install.bat`**, чтобы установить нужные библиотеки.
4. Открой начальную расстановку на шахматном сайте (все 32 фигуры на старте), запусти **`start.bat`** и нажми **`F9`** для калибровки.

### Горячие клавиши
* **`F7`** — Переключить режим: только моя сторона (1 лучший ход) / обе стороны / соперник
* **`F8`** — Показать / скрыть квадраты оверлея
* **`F9`** — Калибровка доски (нажимать на начальной позиции)

### Решение проблем
* **Подсказки перестали появляться посреди партии:** Если после нескольких ходов всё работало нормально, а потом квадраты внезапно пропали или перестали обновляться — нажми клавишу **`F7`** несколько раз (3 нажатия вернут твой привычный режим). Это сбросит кэш позиции и заново запустит анализ.
* **Окно браузера сдвинулось или изменился масштаб:** Открой начальную позицию и снова нажми **`F9`**.

> **Примечание:** Программа создана для разбора позиций, обучения и игры против ботов. Не используй движок в рейтинговых онлайн-партиях против реальных игроков.
