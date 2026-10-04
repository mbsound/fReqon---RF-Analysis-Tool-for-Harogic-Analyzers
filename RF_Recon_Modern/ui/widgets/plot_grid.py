"""
plot_grid.py - Grid lines for a PlotItem, drawn separately from its axes.

pyqtgraph's own grid is painted by the AxisItems, which then span the whole
plot: every trace update repaints both axes, tick labels and all, and they can
never be cached. This item draws only lines, at exactly the positions the axes
put their ticks, so the axes keep to their strips and are cached as pixmaps.
"""

import pyqtgraph as pg
from PyQt6.QtCore import QLineF, QRectF
from PyQt6.QtWidgets import QGraphicsItem


class LinkedGrid(pg.GraphicsObject):
    def __init__(self, plot_item, x=True, y=True, alpha=0.15, color=(200, 200, 200)):
        super().__init__()
        self.plot_item = plot_item
        self.show_x, self.show_y = x, y
        self.pens = (pg.mkPen((*color, int(255 * alpha)), width=1),            # major ticks
                     pg.mkPen((*color, int(255 * alpha * 0.4)), width=1))      # minor ticks
        self._lines = None
        self._rect = QRectF()
        self.setZValue(-1000)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, False)
        vb = plot_item.getViewBox()
        vb.sigRangeChanged.connect(self._invalidate)
        vb.sigResized.connect(self._invalidate)
        plot_item.addItem(self, ignoreBounds=True)

    def _invalidate(self, *args):
        self._lines = None
        self.prepareGeometryChange()
        self._rect = self.plot_item.getViewBox().viewRect()
        self.update()

    def boundingRect(self):
        return self._rect

    def _build(self):
        vb = self.plot_item.getViewBox()
        rect = vb.viewRect()
        self._rect = rect
        lines = ([], [])
        if self.show_x:
            ax = self.plot_item.getAxis('bottom')
            for level, (spacing, values) in enumerate(ax.tickValues(rect.left(), rect.right(), ax.geometry().width())[:2]):
                for v in values:
                    lines[level].append(QLineF(v, rect.top(), v, rect.bottom()))
        if self.show_y:
            ax = self.plot_item.getAxis('left')
            for level, (spacing, values) in enumerate(ax.tickValues(rect.top(), rect.bottom(), ax.geometry().height())[:2]):
                for v in values:
                    lines[level].append(QLineF(rect.left(), v, rect.right(), v))
        self._lines = lines

    def paint(self, p, *args):
        if self._lines is None:
            self._build()
        for pen, lines in zip(self.pens, self._lines):
            if lines:
                p.setPen(pen)
                p.drawLines(lines)


def install_grid(plot_widget, x=True, y=True, alpha=0.15):
    """
    Replace plot_widget's axis-drawn grid with a LinkedGrid and cache the axis
    items as pixmaps (they only change when the range or geometry does).
    """
    pi = plot_widget.getPlotItem() if hasattr(plot_widget, "getPlotItem") else plot_widget
    pi.showGrid(x=False, y=False)
    grid = LinkedGrid(pi, x=x, y=y, alpha=alpha)
    for name in ('left', 'bottom', 'right', 'top'):
        ax = pi.getAxis(name)
        if ax is not None:
            ax.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
    return grid
