import glob
import os
import time
import zipfile
import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal


def find_stockfish_binary():
    """Ищет stockfish*.exe; если в папке лежит архив stockfish*.zip — сам распаковывает."""
    exes = glob.glob("stockfish*.exe") + glob.glob("**/stockfish*.exe", recursive=True)
    for path in exes:
        if os.path.isfile(path):
            return os.path.abspath(path)

    zips = glob.glob("stockfish*.zip")
    for zpath in zips:
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall("stockfish_unpacked")
            exes = glob.glob("**/stockfish*.exe", recursive=True)
            for path in exes:
                if os.path.isfile(path):
                    return os.path.abspath(path)
        except Exception:
            pass

    return None


def infer_castling_rights(piece_fen: str) -> str:
    rows = piece_fen.split("/")
    if len(rows) != 8:
        return "-"

    def expand_row(r):
        res = ""
        for ch in r:
            res += "." * int(ch) if ch.isdigit() else ch
        return res

    top = expand_row(rows[0])
    bottom = expand_row(rows[7])

    rights = ""
    if len(bottom) == 8 and bottom[4] == "K":
        if bottom[7] == "R":
            rights += "K"
        if bottom[0] == "R":
            rights += "Q"
    if len(top) == 8 and top[4] == "k":
        if top[7] == "r":
            rights += "k"
        if top[0] == "r":
            rights += "q"
    return rights if rights else "-"


def count_side_pieces(piece_fen: str, is_white: bool) -> int:
    if is_white:
        return sum(1 for ch in piece_fen if ch in "PNBRQK")
    return sum(1 for ch in piece_fen if ch in "pnbrqk")


def format_score(info) -> str:
    score = info["score"].white()
    if score.is_mate():
        m = score.mate()
        return f"M{m}" if m > 0 else f"-M{abs(m)}"
    cp = score.score(mate_score=10000) / 100.0
    return f"{cp:+.1f}"


class AnalysisWorker(QThread):
    result_ready = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self, vision, think_time=0.35, mode="mine"):
        super().__init__()
        self.vision = vision
        self.think_time = think_time
        self.mode = mode  # "mine" (1 ход за меня), "both" (обе стороны), "opponent" (соперник)
        self.running = True
        self.last_piece_fen = None
        self.last_orientation = None

    def set_mode(self, mode: str):
        self.mode = mode
        self.last_piece_fen = None

    def reset_cache(self):
        self.last_piece_fen = None

    def run(self):
        sf_path = find_stockfish_binary()
        if not sf_path:
            self.status_changed.emit(
                "[ОШИБКА] Не найден файл stockfish*.exe! Положи скачанный Stockfish в папку с программой."
            )
            return

        try:
            engine = chess.engine.SimpleEngine.popen_uci(sf_path)
            engine.configure({"Threads": 2, "Hash": 64})
        except Exception as e:
            self.status_changed.emit(
                f"[ОШИБКА] Не удалось запустить Stockfish ({e}). "
                "Скачай версию Stockfish without AVX2 (x86-64 или universal)."
            )
            return

        self.status_changed.emit("[OK] Stockfish запущен. Показываю 1 лучший ход.")

        try:
            while self.running:
                try:
                    piece_fen, white_at_bottom = self.vision.scan_board()
                except Exception:
                    time.sleep(0.2)
                    continue

                if piece_fen is None:
                    if self.last_piece_fen is not None:
                        self.last_piece_fen = None
                        self.result_ready.emit({"valid": False})
                    time.sleep(0.2)
                    continue

                if piece_fen == self.last_piece_fen and white_at_bottom == self.last_orientation:
                    time.sleep(0.14)
                    continue

                # Защита от захвата в момент, когда ты тянешь фигуру мышкой (фигура поднята с клетки)
                if self.last_piece_fen is not None and white_at_bottom == self.last_orientation:
                    prev_my = count_side_pieces(self.last_piece_fen, white_at_bottom)
                    curr_my = count_side_pieces(piece_fen, white_at_bottom)
                    prev_opp = count_side_pieces(self.last_piece_fen, not white_at_bottom)
                    curr_opp = count_side_pieces(piece_fen, not white_at_bottom)
                    if curr_my == prev_my - 1 and curr_opp == prev_opp:
                        time.sleep(0.12)
                        continue

                # Контрольный повторный снимок через 0.1 сек, чтобы позиция точно устаканилась
                time.sleep(0.10)
                try:
                    confirm_fen, confirm_bottom = self.vision.scan_board()
                except Exception:
                    continue
                if confirm_fen != piece_fen or confirm_bottom != white_at_bottom:
                    continue

                castling = infer_castling_rights(piece_fen)
                try:
                    board_w = chess.Board(f"{piece_fen} w {castling} - 0 1")
                    board_b = chess.Board(f"{piece_fen} b {castling} - 0 1")
                except Exception:
                    time.sleep(0.2)
                    continue

                if not board_w.is_valid() and not board_b.is_valid():
                    self.last_piece_fen = None
                    self.result_ready.emit({"valid": False})
                    time.sleep(0.2)
                    continue

                if self.mode == "mine":
                    need_white = white_at_bottom
                    need_black = not white_at_bottom
                elif self.mode == "opponent":
                    need_white = not white_at_bottom
                    need_black = white_at_bottom
                else:
                    need_white = True
                    need_black = True

                data = {
                    "valid": True,
                    "white_at_bottom": white_at_bottom,
                    "white": None,
                    "black": None,
                }

                if need_white and board_w.is_valid():
                    res_w = engine.analyse(board_w, chess.engine.Limit(time=self.think_time))
                    pv_w = res_w.get("pv")
                    if pv_w:
                        move_w = pv_w[0]
                        data["white"] = {
                            "from_sq": move_w.from_square,
                            "to_sq": move_w.to_square,
                            "score": format_score(res_w),
                        }

                if need_black and board_b.is_valid():
                    res_b = engine.analyse(board_b, chess.engine.Limit(time=self.think_time))
                    pv_b = res_b.get("pv")
                    if pv_b:
                        move_b = pv_b[0]
                        data["black"] = {
                            "from_sq": move_b.from_square,
                            "to_sq": move_b.to_square,
                            "score": format_score(res_b),
                        }

                self.last_piece_fen = piece_fen
                self.last_orientation = white_at_bottom
                self.result_ready.emit(data)

        finally:
            try:
                engine.quit()
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.wait(1500)