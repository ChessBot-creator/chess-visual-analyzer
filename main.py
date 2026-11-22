import ctypes
import ctypes.wintypes
import os
import sys

# Важно: board_vision импортируем ДО PyQt6 для правильного масштаба экрана Windows
from board_vision import BoardNotFoundError, BoardVision

from PyQt6.QtCore import QAbstractNativeEventFilter
from PyQt6.QtWidgets import QApplication
from engine_worker import AnalysisWorker, find_stockfish_binary
from overlay_ui import BoardOverlay, BoardSelectorOverlay


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callbacks):
        super().__init__()
        self.callbacks = callbacks

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312:  # WM_HOTKEY
                    cb = self.callbacks.get(msg.wParam)
                    if cb:
                        cb()
                    return True, 0
            except Exception:
                pass
        return False, 0


class ChessAssistantApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.vision = BoardVision()
        self.overlay = None
        self.worker = None
        self.selector = None
        self.overlay_visible = True
        self.analysis_mode = "mine"  # "mine" -> "both" -> "opponent"

        # Регистрируем глобальные горячие клавиши F7, F8 и F9
        ctypes.windll.user32.RegisterHotKey(None, 1, 0, 0x77)  # VK_F8
        ctypes.windll.user32.RegisterHotKey(None, 2, 0, 0x78)  # VK_F9
        ctypes.windll.user32.RegisterHotKey(None, 3, 0, 0x76)  # VK_F7
        self.hotkey_filter = HotkeyFilter({
            1: self.toggle_overlay,
            2: self.recalibrate,
            3: self.cycle_mode,
        })
        self.app.installNativeEventFilter(self.hotkey_filter)
        self.app.aboutToQuit.connect(self.cleanup)

    def start_engine_and_overlay(self):
        if self.overlay is None:
            self.overlay = BoardOverlay(self.vision.board_rect)
        else:
            self.overlay.update_board_rect(self.vision.board_rect)

        if self.overlay_visible:
            self.overlay.show()

        if self.worker is None:
            self.worker = AnalysisWorker(self.vision, think_time=0.35, mode=self.analysis_mode)
            self.worker.result_ready.connect(self.overlay.update_moves)
            self.worker.status_changed.connect(print)
            self.worker.start()
        else:
            self.worker.reset_cache()

    def cycle_mode(self):
        order = ["mine", "both", "opponent"]
        labels = {
            "mine": "ТОЛЬКО МОЯ СТОРОНА (1 лучший ход)",
            "both": "ОБЕ СТОРОНЫ (белые + черные)",
            "opponent": "ТОЛЬКО СОПЕРНИК (1 лучший ход)",
        }
        idx = (order.index(self.analysis_mode) + 1) % len(order)
        self.analysis_mode = order[idx]
        print(f"[F7] Режим: {labels[self.analysis_mode]}")
        if self.worker:
            self.worker.set_mode(self.analysis_mode)

    def toggle_overlay(self):
        if not self.overlay:
            return
        self.overlay_visible = not self.overlay_visible
        if self.overlay_visible:
            self.overlay.show()
            print("[F8] Квадраты ВКЛЮЧЕНЫ")
        else:
            self.overlay.hide()
            print("[F8] Квадраты СКРЫТЫ")

    def recalibrate(self):
        print("\n[F9] Ищу шахматную доску для калибровки...")
        if self.overlay:
            self.overlay.hide()

        try:
            self.vision.auto_find_board()
            self._finish_calibration()
        except BoardNotFoundError:
            print("[!] Автопоиск не нашел доску — обведи её мышью на экране.")
            self.selector = BoardSelectorOverlay()
            self.selector.area_selected.connect(self._on_manual_rect)
            self.selector.show()

    def _on_manual_rect(self, rect: dict):
        self.vision.set_board_rect(rect)
        self._finish_calibration()

    def _finish_calibration(self):
        self.vision.calibrate_from_start_position()
        print("[OK] Калибровка успешно сохранена!")
        self.overlay_visible = True
        self.start_engine_and_overlay()

    def cleanup(self):
        ctypes.windll.user32.UnregisterHotKey(None, 1)
        ctypes.windll.user32.UnregisterHotKey(None, 2)
        ctypes.windll.user32.UnregisterHotKey(None, 3)
        if self.worker:
            self.worker.stop()

    def run(self):
        print("==================================================")
        print("  CHESS VISUAL ANALYZER (1 ЛУЧШИЙ ХОД)")
        print("==================================================")
        print("  F7 — режим: только я (1 ход) / обе стороны / соперник")
        print("  F8 — показать / скрыть квадраты")
        print("  F9 — калибровка (нажми на стартовой позиции)")
        print("==================================================\n")

        if not find_stockfish_binary():
            print("[!] ВНИМАНИЕ: Файл Stockfish не найден в папке!")
            print("    Скачай Stockfish для Windows и положи .zip или .exe в эту папку.\n")

        if os.path.exists("config.json") and os.path.exists("templates") and self.vision.board_rect:
            print("[OK] Загружена сохраненная калибровка доски.")
            self.start_engine_and_overlay()
        else:
            print("[ИНСТРУКЦИЯ ПЕРВОГО ЗАПУСКА]:")
            print("1. Открой в браузере Chess.com (раздел 'Анализ' или партия против бота).")
            print("2. Убедись, что на доске стоит НАЧАЛЬНАЯ позиция (все 32 фигуры на старте).")
            print("3. Нажми клавишу F9 на клавиатуре!\n")

        sys.exit(self.app.exec())


if __name__ == "__main__":
    ChessAssistantApp().run()