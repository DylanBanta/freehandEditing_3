# -*- coding: utf-8 -*-
#-----------------------------------------------------------
#
# Freehand Editing
# Copyright (C) 2010 - 2012 Pavol Kapusta
# pavol.kapusta@gmail.com
#
# Code adopted/adapted from:
#
# 'SelectPlus Menu Plugin', Copyright (C) Barry Rowlingson
# 'Numerical Vertex Edit Plugin' and 'traceDigitize' plugin,
#  Copyright (C) Cédric Möri
#
# Spinbox idea adopted from:
# 'Improved polygon capturing' plugin, Copyright (C) Adrian Weber
#
#-----------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#---------------------------------------------------------------------


# Import the PyQt and the QGIS libraries
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.core import QgsMapLayer
from qgis.gui import *

#Import own classes and tools
from .freehandeditingtool import FreehandEditingTool

# initialize Qt resources from file resources.py
from . import resources

#try:
#    from qgis.core import Qgis
#except ImportError:
#    from qgis.core import QGis as Qgis

class FreehandEditing:

    def __init__(self, iface):
      # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.active = False

    def initGui(self):
        settings = QSettings()
        # Create action
        self.freehand_edit = \
            QAction(QIcon(":/plugins/freehandEditing/icon.png"),
                    "Freehand editing", self.iface.mainWindow())
        self.freehand_edit.setEnabled(False)
        self.freehand_edit.setCheckable(True)
        # Add toolbar button and menu item
        self.iface.digitizeToolBar().addAction(self.freehand_edit)
        self.iface.editMenu().addAction(self.freehand_edit)
        
        # Set up the keyboard shortcut
        self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+E"), self.iface.mainWindow())
        self.shortcut.activated.connect(self.activateFreehandTool)

        self.spinBox = QDoubleSpinBox(self.iface.mainWindow())
        self.spinBox.setDecimals(3)
        self.spinBox.setMinimum(0.000)
        self.spinBox.setMaximum(5.000)
        self.spinBox.setSingleStep(0.100)
        toleranceval = \
            settings.value("/freehandEdit/tolerance", 0.000, type=float)
        if not toleranceval:
            settings.setValue("/freehandEdit/tolerance", 0.000)
        self.spinBox.setValue(toleranceval)
        self.spinBoxAction = \
            self.iface.digitizeToolBar().addWidget(self.spinBox)
        self.spinBox.setToolTip("Tolerance. Level of simplification.")
        self.spinBoxAction.setEnabled(False)

        # Connect to signals for button behaviour
        self.freehand_edit.triggered.connect(self.freehandediting)
        try:
            self.canvas.currentLayer().editingStarted.connect(self.toggle)
        except:
            print("no layer")
        self.iface.currentLayerChanged['QgsMapLayer*'].connect(self.toggle)
        self.canvas.mapToolSet['QgsMapTool*','QgsMapTool*'].connect(self.deactivate)

        self.spinBox.valueChanged[float].connect(self.tolerancesettings)

        # Get the tool
        self.tool = FreehandEditingTool(self.canvas)

    def activateFreehandTool(self):
        # Check if the current layer is compatible with the Freehand Editing Tool
        layer = self.canvas.currentLayer()
        if layer and layer.isEditable() and (layer.geometryType() == QgsWkbTypes.LineGeometry or layer.geometryType() == QgsWkbTypes.PolygonGeometry):
            # Activate the Freehand Editing Tool
            self.freehandediting()

    def tolerancesettings(self):
        settings = QSettings()
        settings.setValue("/freehandEdit/tolerance", self.spinBox.value())

    def freehandediting(self):
        self.canvas.setMapTool(self.tool)
        self.freehand_edit.setChecked(True)
        self.tool.rbFinished['QgsGeometry*'].connect(self.createFeature)
        self.active = True

    def toggle(self):

        mc = self.canvas
        layer = mc.currentLayer()
        if layer is None:
            self.deactivate()
            self.freehand_edit.setEnabled(False)

            return

        #Decide whether the plugin button/menu is enabled or disabled
        else:
            try:
                if layer.isEditable() and (layer.geometryType() == 2 or layer.geometryType() == 1):
                    self.freehand_edit.setEnabled(True)
                    self.spinBoxAction.setEnabled(layer.crs().projectionAcronym() != "longlat")

                    try:  # remove any existing connection first
                        layer.editingStopped.disconnect(self.toggle)
                    except TypeError:  # missing connection
                        pass
                    layer.editingStopped.connect(self.toggle)
                    try:
                        layer.editingStarted.disconnect(self.toggle)
                    except TypeError:  # missing connection
                        pass
                else:
                    self.freehand_edit.setEnabled(False)
                    self.spinBoxAction.setEnabled(False)
                    if layer.type() == 0 and (layer.geometryType() == 1  or layer.geometryType() == 2):
                        try:  # remove any existing connection first
                            layer.editingStarted.disconnect(self.toggle)
                        except TypeError:  # missing connection
                            pass
                        layer.editingStarted.connect(self.toggle)
                        try:
                            layer.editingStopped.disconnect(self.toggle)
                        except TypeError:  # missing connection
                            pass

            except:
                print ("fault")

    def createFeature(self, geom):
        settings = QSettings()
        mc = self.canvas
        layer = mc.currentLayer()
        if layer is None:
            return

        layerCRSSrsid = layer.crs().srsid()
        projectCRSSrsid = mc.mapSettings().destinationCrs().srsid()
        provider = layer.dataProvider()
        f = QgsFeature()

        if layer.crs().projectionAcronym() == "longlat":
            tolerance = 0.000
            print("0 tolerance")
        else:
            tolerance = settings.value("/freehandEdit/tolerance",
                                       0.000, type=float)
            print("punkt oder komma ", tolerance)

        #On the Fly reprojection.
        if layerCRSSrsid != projectCRSSrsid:
            p = QgsCoordinateReferenceSystem("EPSG:"+str(projectCRSSrsid))
            l = QgsCoordinateReferenceSystem("EPSG:"+str(layerCRSSrsid))
            geom.transform(QgsCoordinateTransform(p,l,QgsProject.instance()))


        print(tolerance,"tolerance")
        s = geom.simplify(tolerance)

        #validate geometry
        if not (s.validateGeometry()):
            f.setGeometry(s)

        else:

            reply = QMessageBox.question(
                self.iface.mainWindow(),
                'Feature not valid',
                "The geometry of the feature you just added isn't valid."
                "Do you want to use it anyway?",
                QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                f.setGeometry(s)
            else:
                return

        # add attribute fields to feature
        fields = layer.fields()

        f.initAttributes(fields.count())


        layer.beginEditCommand("Feature added")
        if layer.geometryType() == 1  or layer.geometryType() == 2:

            if (settings.value(
                    "/qgis/digitizing/disable_enter_attribute_values_dialog",
                    False, type=bool)):
                layer.addFeature(f)
                layer.endEditCommand()
            else:
                dlg = self.iface.getFeatureForm(layer, f)
                dlg.setMode(1)
                self.tool.setIgnoreClick(True)

                if dlg.exec_():

                    layer.endEditCommand()

                else:
                    layer.destroyEditCommand()
                self.tool.setIgnoreClick(False)
        else:
            print("false geomtry")




    def deactivate(self):

        self.freehand_edit.setChecked(False)
        if self.active:
            self.tool.rbFinished['QgsGeometry*'].disconnect(self.createFeature)
        self.active = False

    def unload(self):
        self.iface.digitizeToolBar().removeAction(self.freehand_edit)
        self.iface.digitizeToolBar().removeAction(self.spinBoxAction)
