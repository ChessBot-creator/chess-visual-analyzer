import ctypes
import json
import os
import threading
import time
import cv2
import mss
import numpy as np

# Корректная работа при масштабировании экрана Windows (125%, 150% и т.д.)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


START_LAYOUT_WHITE_BOTTOM = [
    ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
    ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
    ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
]


class BoardNotFoundError(Exception):
    pass


class BoardVision:
    def __init__(self, config_path="config.json", templates_dir="templates"):
        self.config_path = config_path
        self.templates_dir = templates_dir
        self._local = threading.local()
        self.board_rect = None
        self.grad_threshold = 12.0
        self.templates = {}  # {"wP": [(gray, edge), ...], ...}

        if os.path.exists(self.config_path):
            self.load_config()
        if os.path.exists(self.templates_dir):
            self.load_templates()

    def _get_sct(self):
        if not hasattr(self._local, "sct"):
            self._local.sct = mss.mss()
        return self._local.sct

    def grab_screen(self, region=None):
        sct = self._get_sct()
        monitor = region if region else sct.monitors[1]
        raw = np.array(sct.grab(monitor))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def _has_chess_grid(self, gray_roi):
        resized = cv2.resize(gray_roi, (400, 400), interpolation=cv2.INTER_AREA)
        sobel_x = np.abs(cv2.Sobel(resized, cv2.CV_64F, 1, 0, ksize=3)).mean(axis=0)
        sobel_y = np.abs(cv2.Sobel(resized, cv2.CV_64F, 0, 1, ksize=3)).mean(axis=1)

        step = 50
        peaks_x = sum(
            sobel_x[i * step - 2 : i * step + 3].max() > sobel_x.mean() * 1.7
            for i in range(1, 8)
        )
        peaks_y = sum(
            sobel_y[i * step - 2 : i * step + 3].max() > sobel_y.mean() * 1.7
            for i in range(1, 8)
        )
        return peaks_x >= 5 and peaks_y >= 5

    def auto_find_board(self):
        """Ищет доску на всех подключенных мониторах."""
        sct = self._get_sct()
        best_rect = None
        best_area = 0

        for mon in sct.monitors[1:]:
            screen = self.grab_screen(mon)
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 35, 110)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w < 300 or h < 300:
                    continue
                aspect = w / float(h)
                if 0.96 <= aspect <= 1.04 and (w * h) > best_area:
                    roi = gray[y : y + h, x : x + w]
                    if self._has_chess_grid(roi):
                        best_area = w * h
                        best_rect = {
                            "left": int(mon["left"] + x),
                            "top": int(mon["top"] + y),
                            "width": int(w),
                            "height": int(h),
                        }

        if best_rect is None:
            raise BoardNotFoundError("Доска не найдена автоматически")

        self.board_rect = best_rect
        return best_rect

    def set_board_rect(self, rect: dict):
        self.board_rect = rect

    def _extract_cell_inner(self, board_gray, row, col):
        """Вырезает центральные 72% клетки без координат a-h, 1-8 и границ."""
        h, w = board_gray.shape
        cell_h = h / 8.0
        cell_w = w / 8.0

        y1 = int((row + 0.14) * cell_h)
        y2 = int((row + 0.86) * cell_h)
        x1 = int((col + 0.14) * cell_w)
        x2 = int((col + 0.86) * cell_w)

        cell = board_gray[y1:y2, x1:x2]
        return cv2.resize(cell, (64, 64), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _compute_edge_map(cell_gray):
        gx = cv2.Sobel(cell_gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(cell_gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        max_val = float(mag.max())
        if max_val > 0:
            mag = (mag / max_val) * 255.0
        return mag.astype(np.uint8)

    @staticmethod
    def _cell_gradient_energy(cell_gray):
        gx = cv2.Sobel(cell_gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(cell_gray, cv2.CV_64F, 0, 1, ksize=3)
        return float(np.mean(np.hypot(gx, gy)))

    def calibrate_from_start_position(self):
        """Калибровка по стартовой расстановке (32 фигуры)."""
        if self.board_rect is None:
            self.auto_find_board()

        os.makedirs(self.templates_dir, exist_ok=True)
        for f in os.listdir(self.templates_dir):
            os.remove(os.path.join(self.templates_dir, f))

        board_bgr = self.grab_screen(self.board_rect)
        board_gray = cv2.cvtColor(board_bgr, cv2.COLOR_BGR2GRAY)

        # Автоопределение, где стоят белые (снизу или сверху) по яркости фигур
        top_cells = [self._extract_cell_inner(board_gray, r, c) for r in (0, 1) for c in range(8)]
        bot_cells = [self._extract_cell_inner(board_gray, r, c) for r in (6, 7) for c in range(8)]
        white_at_bottom = np.mean(bot_cells) >= np.mean(top_cells)

        layout = START_LAYOUT_WHITE_BOTTOM
        if not white_at_bottom:
            layout = [row[::-1] for row in layout[::-1]]

        empty_energies = []
        piece_energies = []
        counters = {}

        for r in range(8):
            for c in range(8):
                cell = self._extract_cell_inner(board_gray, r, c)
                energy = self._cell_gradient_energy(cell)
                piece = layout[r][c]

                if piece is None:
                    empty_energies.append(energy)
                else:
                    piece_energies.append(energy)
                    idx = counters.get(piece, 0)
                    counters[piece] = idx + 1
                    filename = os.path.join(self.templates_dir, f"{piece}_{idx}.png")
                    cv2.imwrite(filename, cell)

        max_empty = max(empty_energies) if empty_energies else 8.0
        min_piece = min(piece_energies) if piece_energies else 20.0
        self.grad_threshold = (max_empty + min_piece) / 2.0

        self.save_config()
        self.load_templates()

    def save_config(self):
        data = {
            "board_rect": self.board_rect,
            "grad_threshold": self.grad_threshold,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.board_rect = data.get("board_rect")
        self.grad_threshold = data.get("grad_threshold", 12.0)

    def load_templates(self):
        self.templates.clear()
        for fname in os.listdir(self.templates_dir):
            if not fname.endswith(".png"):
                continue
            piece = fname.split("_")[0]
            img = cv2.imread(os.path.join(self.templates_dir, fname), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                edge = self._compute_edge_map(img)
                self.templates.setdefault(piece, []).append((img, edge))

    def get_stable_board_gray(self, max_wait=0.65):
        """Ждет завершения анимации движения фигуры."""
        deadline = time.time() + max_wait
        prev = cv2.cvtColor(self.grab_screen(self.board_rect), cv2.COLOR_BGR2GRAY)
        while time.time() < deadline:
            time.sleep(0.085)
            curr = cv2.cvtColor(self.grab_screen(self.board_rect), cv2.COLOR_BGR2GRAY)
            diff = float(np.mean(cv2.absdiff(prev, curr)))
            if diff < 1.8:
                return curr
            prev = curr
        return prev

    def classify_cell(self, cell_gray):
        if self._cell_gradient_energy(cell_gray) < self.grad_threshold:
            return None

        cell_edge = self._compute_edge_map(cell_gray)
        best_piece = None
        best_score = -1.0

        for piece, tmpl_list in self.templates.items():
            for tmpl_gray, tmpl_edge in tmpl_list:
                s_gray = float(cv2.matchTemplate(cell_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)[0][0])
                s_edge = float(cv2.matchTemplate(cell_edge, tmpl_edge, cv2.TM_CCOEFF_NORMED)[0][0])
                score = 0.55 * s_gray + 0.45 * s_edge
                if score > best_score:
                    best_score = score
                    best_piece = piece

        return best_piece if best_score > 0.56 else None

    def scan_board(self):
        """Возвращает (piece_fen, white_at_bottom) или (None, True), если доска перекрыта."""
        if not self.board_rect or not self.templates:
            return None, True

        board_gray = self.get_stable_board_gray()
        grid = [[None] * 8 for _ in range(8)]

        w_kings = 0
        b_kings = 0
        w_rows = []
        b_rows = []

        for r in range(8):
            for c in range(8):
                piece = self.classify_cell(self._extract_cell_inner(board_gray, r, c))
                grid[r][c] = piece
                if piece:
                    if piece == "wK":
                        w_kings += 1
                    elif piece == "bK":
                        b_kings += 1

                    if piece.startswith("w"):
                        w_rows.append(r)
                    else:
                        b_rows.append(r)

        # Проверка корректности кадра: на доске обязаны быть оба короля
        if w_kings != 1 or b_kings != 1:
            return None, True

        mean_w = sum(w_rows) / len(w_rows) if w_rows else 7.0
        mean_b = sum(b_rows) / len(b_rows) if b_rows else 0.0
        white_at_bottom = mean_w >= mean_b

        if not white_at_bottom:
            grid = [row[::-1] for row in grid[::-1]]

        return self._grid_to_piece_fen(grid), white_at_bottom

    @staticmethod
    def _grid_to_piece_fen(grid):
        fen_map = {
            "wP": "P", "wN": "N", "wB": "B", "wR": "R", "wQ": "Q", "wK": "K",
            "bP": "p", "bN": "n", "bB": "b", "bR": "r", "bQ": "q", "bK": "k",
        }
        rows = []
        for r in range(8):
            empty = 0
            row_str = ""
            for c in range(8):
                p = grid[r][c]
                if p is None:
                    empty += 1
                else:
                    if empty > 0:
                        row_str += str(empty)
                        empty = 0
                    row_str += fen_map[p]
            if empty > 0:
                row_str += str(empty)
            rows.append(row_str)
        return "/".join(rows)