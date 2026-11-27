"""Small RGB histogram of the current white-balanced input preview."""
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets as W


class Histogram(W.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(155)
        self.setMaximumHeight(220)
        self.bins = None
        self.setToolTip('RGB histogram of the white-balanced input preview; values outside 0–1 are clipped to the edges.')

    def set_image(self, image):
        self.bins = None
        if image is not None:
            pixels = np.asarray(image)[..., :3].reshape(-1, 3)
            pixels = pixels[::max(1, len(pixels) // 100000)]
            pixels = pixels[np.isfinite(pixels).all(axis=1)]
            self.bins = np.array([np.histogram(np.clip(pixels[:, c], 0, 1), bins=128, range=(0, 1))[0]
                                  for c in range(3)])
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor('#202020'))
        painter.setPen(QtGui.QColor('#dddddd'))
        from spektrafilm_gui.i18n import tr
        painter.drawText(10, 20, tr('RGB · White-balanced input'))
        if self.bins is None:
            return
        height = self.height() - 38
        scale = max(1, self.bins.max())
        for values, color in zip(self.bins, ('#ef6666', '#75d687', '#739df1')):
            path = QtGui.QPainterPath()
            for i, value in enumerate(values):
                x, y = 8 + i * (self.width() - 16) / 127, self.height() - 8 - value / scale * height
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 1.3))
            painter.drawPath(path)
