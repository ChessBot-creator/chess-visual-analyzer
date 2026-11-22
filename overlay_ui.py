import ctypes
import chess
from PyQt6.QtCore import Qt, QRectF, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget


class BoardOverlay(QWidget):
    def __init__(self, board_rect: dict):
        super().__init__()
        self.move_data = {"valid": False}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.update_board_rect(board_rect)

    def showEvent(self, event):
        super().showEvent(event)
        # Жестко включаем сквозное пропускание кликов мыши на уровне Win32 API
        try:
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            )
        except Exception:
            pass

    def update_board_rect(self, board_rect: dict):
        self.setGeometry(
            board_rect["left"],
            board_rect["top"],
            board_rect["width"],
            board_rect["height"],
        )
        self.update()

    def update_moves(self, data: dict):
        self.move_data = data
        self.update()

    def _square_to_rect(self, sq: int, white_at_bottom: bool, inset: float) -> QRectF:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)

        if white_at_bottom:
            col = file_idx
            row = 7 - rank_idx
        else:
            col = 7 - file_idx
            row = rank_idx

        cell_w = self.width() / 8.0
        cell_h = self.height() / 8.0

        return QRectF(
            col * cell_w + inset,
            row * cell_h + inset,
            cell_w - inset * 2,
            cell_h - inset * 2,
        )

    def _draw_side_move(self, painter: QPainter, info: dict, color: QColor, tag: str, inset: float, white_bottom: bool):
        if not info:
            return

        from_rect = self._square_to_rect(info["from_sq"], white_bottom, inset)
        to_rect = self._square_to_rect(info["to_sq"], white_bottom, inset)

        # Пунктирная линия от фигуры к целевой клетке
        link_color = QColor(color)
        link_color.setAlpha(150)
        painter.setPen(QPen(link_color, 2.0, Qt.PenStyle.DashLine))
        painter.drawLine(from_rect.center(), to_rect.center())

        # Квадрат 1: фигура, которой нужно ходить
        src_fill = QColor(color)
        src_fill.setAlpha(28)
        painter.setBrush(src_fill)
        painter.setPen(QPen(color, 3.5))
        painter.drawRoundedRect(from_rect, 6, 6)

        # Квадрат 2: клетка, куда ходить
        dst_fill = QColor(color)
        dst_fill.setAlpha(75)
        painter.setBrush(dst_fill)
        painter.setPen(QPen(color, 3.5))
        painter.drawRoundedRect(to_rect, 6, 6)

        # Мини-метка (W / B и оценка)
        badge_rect = QRectF(from_rect.left() + 3, from_rect.top() + 3, 50, 18)
        painter.setBrush(QColor(15, 18, 24, 215))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{tag} {info['score']}")

    def paintEvent(self, event):
        if not self.move_data.get("valid"):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        white_bottom = self.move_data.get("white_at_bottom", True)

        # Белые — бирюзовый квадрат
        self._draw_side_move(
            painter,
            self.move_data.get("white"),
            QColor(0, 240, 255),
            "W",
            inset=2.5,
            white_bottom=white_bottom,
        )

        # Черные — оранжевый квадрат
        self._draw_side_move(
            painter,
            self.move_data.get("black"),
            QColor(255, 115, 0),
            "B",
            inset=7.5,
            white_bottom=white_bottom,
        )


class BoardSelectorOverlay(QWidget):
    """Запасное выделение доски мышью, если автопоиск не сработал."""
    area_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.start_pt = None
        self.end_pt = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        virtual_geo = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geo)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pt = event.position().toPoint()
            self.end_pt = self.start_pt
            self.update()

    def mouseMoveEvent(self, event):
        if self.start_pt is not None:
            self.end_pt = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start_pt and self.end_pt:
            rect = QRect(self.start_pt, self.end_pt).normalized()
            side = max(rect.width(), rect.height())
            if side > 150:
                global_tl = self.mapToGlobal(rect.topLeft())
                self.close()
                self.area_selected.emit({
                    "left": global_tl.x(),
                    "top": global_tl.y(),
                    "width": side,
                    "height": side,
                })
            else:
                self.start_pt = None
                self.end_pt = None
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(
            QRect(0, 40, self.width(), 50),
            Qt.AlignmentFlag.AlignCenter,
            "Зажми левую кнопку мыши и обведи шахматную доску от угла до угла",
        )

        if self.start_pt and self.end_pt:
            rect = QRect(self.start_pt, self.end_pt).normalized()
            side = max(rect.width(), rect.height())
            sq_rect = QRect(rect.topLeft().x(), rect.topLeft().y(), side, side)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sq_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 240, 255), 3))
            painter.drawRect(sq_rect)