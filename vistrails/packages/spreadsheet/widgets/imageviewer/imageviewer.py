###############################################################################
##
## Copyright (C) 2014-2016, New York University.
## Copyright (C) 2011-2014, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah.
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice,
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright
##    notice, this list of conditions and the following disclaimer in the
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the New York University nor the names of its
##    contributors may be used to endorse or promote products derived from
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################
################################################################################
# ImageViewer widgets/toolbar implementation
################################################################################


import os
from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport

from vistrails.packages.spreadsheet.basic_widgets import SpreadsheetCell,\
    SpreadsheetMode
from vistrails.packages.spreadsheet.spreadsheet_cell import QCellWidget,\
    QCellToolBar, SpreadsheetAction
from vistrails.packages.spreadsheet.spreadsheet_controller import \
    spreadsheetController
from . import imageviewer_rc

################################################################################


class ImageFileToSpreadsheet(SpreadsheetMode):
    def compute_output(self, output_module, configuration):
        fname = output_module.get_input('value').name
        window = spreadsheetController.findSpreadsheetWindow()
        local_file = window.file_pool.make_local_copy(fname)
        self.display_and_wait(output_module, configuration,
                              ImageViewerCellWidget, (local_file,))


class ImageViewerCell(SpreadsheetCell):
    """
    ImageViewerCell is a custom Module to display labels, images, etc.
    
    """    
    def compute(self):
        """ compute() -> None
        Dispatch the display event to the spreadsheet with images and labels
        
        """
        if self.has_input("File"):
            window = spreadsheetController.findSpreadsheetWindow()
            file_to_display = self.get_input("File")
            fileValue = window.file_pool.make_local_copy(file_to_display.name)
        else:
            fileValue = None
        self.displayAndWait(ImageViewerCellWidget, (fileValue, ))


class ImageViewerCellWidget(QCellWidget):
    """
    ImageViewerCellWidget is the actual QLabel that will draw
    labels/images on the spreadsheet
    
    """
    def __init__(self, parent=None):
        """ ImageViewerCellWidget(parent: QWidget) -> ImageViewerCellWidget
        Initialize the widget with its toolbar type and aligment
        
        """
        super().__init__(parent=parent)
        self.setLayout(QtWidgets.QVBoxLayout(self))
        self.setAnimationEnabled(True)
        
        self.label = QtWidgets.QLabel()
        self.layout().addWidget(self.label)
        
        self.label.setAutoFillBackground(True)
        self.label.palette().setColor(QtGui.QPalette.Window, QtCore.Qt.white)
        self.label.setMouseTracking(False)
        self.label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.label.setScaledContents(False)
        self.toolBarType = ImageViewerToolBar
        self.originalPix = None
        self.setMinimumSize(1, 1)

    def updateContents(self, inputPorts):
        """ updateContents(inputPorts: tuple) -> None
        Update the widget contents based on the input data
        
        """
        (fileValue, ) = inputPorts
        if fileValue:
            img = QtGui.QImage()
            if img.load(fileValue.name):
                self.originalPix = QtGui.QPixmap.fromImage(img)
                self.label.setPixmap(self.originalPix.scaled(self.label.size(),
                                                         QtCore.Qt.KeepAspectRatio,
                                                         QtCore.Qt.SmoothTransformation))
            else:
                self.label.setText("Invalid image file!")

        QCellWidget.updateContents(self, inputPorts)

    def saveToPNG(self, filename):
        """ saveToPNG(filename: str) -> bool
        Save the current widget contents to an image file
        
        """
        pixmap = self.label.pixmap()
        if pixmap and (not pixmap.isNull()):
            return pixmap.save(filename)
        return False

    def dumpToFile(self, filename):
        """ dumpToFile(filename: str) -> None
        Dumps the cell as an image file

        """
        pixmap = self.label.pixmap()
        if pixmap and (not pixmap.isNull()):
            if not os.path.splitext(filename)[1]:
                pixmap.save(filename, 'PNG')
            else:
                pixmap.save(filename)

    def saveToPDF(self, filename):
        """ saveToPDF(filename: str) -> bool
        Save the current widget contents to a pdf file
        
        """
        printer = QtPrintSupport.QPrinter()
        
        printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
        printer.setOutputFileName(filename)
        painter = QtGui.QPainter()
        painter.begin(printer)
        rect = painter.viewport()
        pixmap = self.label.pixmap()
        size = pixmap.size()
        size.scale(rect.size(), QtCore.Qt.KeepAspectRatio)
        painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
        painter.setWindow(pixmap.rect())
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

    def resizeEvent(self, e):
        if self.originalPix!=None:
            self.label.setPixmap(self.originalPix.scaled(self.label.size(),
                                                         QtCore.Qt.KeepAspectRatio,
                                                         QtCore.Qt.SmoothTransformation))


class ImageViewerFitToCellAction(SpreadsheetAction):
    """
    ImageViewerFitToCellAction is the action to stretch the image to
    fit inside a cell
    
    """
    def __init__(self, parent=None):
        """ ImageViewerFitToCellAction(parent: QWidget)
                                       -> ImageViewerFitToCellAction
        Setup the image, status tip, etc. of the action
        
        """
        super().__init__(QtGui.QIcon(":/images/fittocell.png"),
                         "&Fit To Cell",
                         parent)
        self.setStatusTip("Scale image content to fit cell frame")
        self.setCheckable(True)
        self.setChecked(True)

    def toggledSlot(self, checked):
        """ toggledSlot(checked: boolean) -> None
        Execute the action when the button is toggled
        
        """
        cellWidget = self.toolBar.getSnappedWidget()
        cellWidget.label.setScaledContents(checked)
        self.toolBar.slider.updateStatus((self.toolBar.sheet,
                                          self.toolBar.row,
                                          self.toolBar.col,
                                          cellWidget))
        
    def updateStatus(self, info):
        """ updateStatus(info: tuple) -> None
        Updates the status of the button based on the input info
        
        """
        (sheet, row, col, cellWidget) = info
        self.setChecked(cellWidget.label.hasScaledContents())


class ImageViewerZoomSlider(QtWidgets.QSlider):
    """
    ImageViewerZoomSlider is a slider that allows user to zoom in and
    out by dragging it
    
    """
    def __init__(self, parent=None):
        """ ImageViewerZoomSlider(parent: QWidget) -> ImageViewerZoomSlider
        Setup the ranges, status tip, etc. of the slider
        
        """
        QtWidgets.QSlider.__init__(self, QtCore.Qt.Horizontal, parent)
        self.setRange(100, 300)
        self.setValue(100)
        self.setTracking(True)
        self.setStatusTip("Zoom in the image")
        self.valueChanged.connect(self.updateZoom)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.Expanding)
        
    def updateZoom(self, value):
        """ updateZoom(value: int) -> None
        Update the image when the slider value changed
        
        """
        if self.toolBar:
            cellWidget = self.toolBar.getSnappedWidget()
            if not cellWidget.label.hasScaledContents():
                newWidth = cellWidget.originalPix.width()*value//100
                pixmap = cellWidget.originalPix.scaledToWidth(newWidth)
                cellWidget.label.setPixmap(pixmap)

    def updateStatus(self, info):
        """ updateStatus(info: tuple) -> None
        Updates the status of the button based on the input info
        
        """
        (sheet, row, col, cellWidget) = info
        if cellWidget:
            if (not cellWidget.label.hasScaledContents() and
                not cellWidget._playing):
                self.setEnabled(True)
                originalWidth = cellWidget.originalPix.width()
                self.setValue(cellWidget.label.pixmap().width()*100//originalWidth)
            else:
                self.setEnabled(False)
                self.setValue(100)


class ImageViewerZoomLabel(QtWidgets.QLabel):
    """
    ImageViewerZoomLabel is the label sitting next to the ImageViewerZoomSlider
    
    """
    def __init__(self, parent=None):
        """ ImageViewerZoomLabel(parent: QWidget) -> None
        Setup the label with a status tip
        
        """
        QtWidgets.QLabel.__init__(self, "100%", parent)
        self.setStatusTip("Zoom in the image")
        
    def updateValue(self, value):
        """ updateValue(value: int)
        Updates the label with the new percentage value
        """
        self.setText(str(value)+"%")


class ImageViewerRotateAction(SpreadsheetAction):
    """
    ImageViewerRotateAction is the action to rotate the image
    
    """
    def __init__(self, parent=None):
        """ ImageViewerRotateAction(parent: QWidget)
                                       -> ImageViewerRotateAction
        Setup the image, status tip, etc. of the action
        
        """
        super().__init__(QtGui.QIcon(":/images/rotate.png"),
                         "&Rotate CW...",
                         parent)
        self.setStatusTip("Rotate 90 degrees CW")
        self.rotationMatrix = QtGui.QTransform(0,1,-1,0,0,0)
        
    def triggeredSlot(self, checked=False):
        """ toggledSlot(checked: boolean) -> None
        Execute the action when the button is clicked
        
        """
        cellWidget = self.toolBar.getSnappedWidget()
        if not cellWidget.label.pixmap() or cellWidget.label.pixmap().isNull():
            return
        cellWidget.originalPix = cellWidget.originalPix.transformed(
            self.rotationMatrix)
        cellWidget.label.setPixmap(cellWidget.label.pixmap().transformed(
            self.rotationMatrix))


class ImageViewerFlipAction(SpreadsheetAction):
    """
    ImageViewerFlipAction is the action to flip the image
    
    """
    def __init__(self, parent=None):
        """ ImageViewerFlipAction(parent: QWidget) -> ImageViewerFlipAction
        Setup the image, status tip, etc. of the action
        
        """
        super().__init__(QtGui.QIcon(":/images/flip.png"),
                         "&Flip Horizontal...",
                         parent)
        self.setStatusTip("Flip the image horizontally")
        self.flipMatrix = QtGui.QTransform(-1,0,0,1,0,0)
        
    def triggeredSlot(self, checked=False):
        """ toggledSlot(checked: boolean) -> None
        Execute the action when the button is clicked
        
        """
        cellWidget = self.toolBar.getSnappedWidget()
        label = cellWidget.label
        if not label.pixmap() or label.pixmap().isNull():
            return
        cellWidget.originalPix = cellWidget.originalPix.transformed(
            self.flipMatrix)
        label.setPixmap(label.pixmap().transformed(self.flipMatrix))


class ImageViewerToolBar(QCellToolBar):
    """
    ImageViewerToolBar derives from CellToolBar to give the ImageViewerCellWidget
    a customizable toolbar
    
    """
    def createToolBar(self):
        """ createToolBar() -> None
        This will get call initiallly to add customizable widgets
        
        """
        self.appendAction(ImageViewerFitToCellAction(self))
        self.appendAction(ImageViewerRotateAction(self))
        self.appendAction(ImageViewerFlipAction(self))
        self.slider = ImageViewerZoomSlider(self)
        label = ImageViewerZoomLabel(self)
        self.slider.valueChanged.connect(label.updateValue)
        self.appendWidget(self.slider)
        self.appendWidget(label)
        self.addAnimationButtons()
