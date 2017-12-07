# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PathFinder
                                 A QGIS plugin
 Find the shortest path between two points in a raster image.
                              -------------------
        begin                : 2017-09-20
        git sha              : $Format:%H$
        copyright            : (C) 2017 by BN
        email                : biczoxd@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Default Python packages
import os.path
from time import time
from random import randint

# PyQt packages
from PyQt4.QtCore import *
from PyQt4.QtGui import QAction, QIcon, QColor

# Initialize Qt resources from file resources.py
import resources

# Import the code for the dialog
from path_finder_dialog import PathFinderDialog

# Packages by QGIS
import numpy as np
from osgeo import gdal
from qgis.core import *
from qgis.utils import iface
from qgis.gui import QgsMapTool

# My packages
import pyastar


class PathFinder:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'PathFinder_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Path finder')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'PathFinder')
        self.toolbar.setObjectName(u'PathFinder')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('PathFinder', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = PathFinderDialog()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/PathFinder/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Find path'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&Path finder'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        """Run method that performs all the real work"""

        # Init the gui.
        self.init_combobox()
        self.canvas = self.iface.mapCanvas()
        self.mouse_click = MySelectorTool(self.canvas, self.click_callback)
        iface.mapCanvas().setMapTool(self.mouse_click)
        # Try to disconnect the previous connection.
        try:
            self.dlg.pushButton_2.clicked.disconnect()
            self.dlg.pushButton.clicked.disconnect()
            self.dlg.checkBox.stateChanged.disconnect()
            self.dlg.comboBox.currentIndexChanged.disconnect()
        except:
            # In case of error don't do anything yet.
            pass

        self.dlg.pushButton_2.clicked.connect(self.clear_coordinates)
        self.dlg.pushButton.clicked.connect(self.find_path)
        self.dlg.checkBox.stateChanged.connect(self.checkbox_state_change_callback)
        self.dlg.comboBox.currentIndexChanged.connect(self.combobox_index_change_callback)


        # Show the dialog.
        self.dlg.show()
        # Run the dialog event loop.
        result = self.dlg.exec_()
        # See if OK was pressed.
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass


    def init_combobox(self):
        """
        Initialize the comobobox with the layer of the project.
        """

        # Get all the layers from the interface.
        all_layers = self.iface.legendInterface().layers()
        self.layers = []
        layers_list = []

        for layer in all_layers:
            # If the layer is a raster layer,
            if layer.type() == QgsMapLayer.RasterLayer:
                # add it to the lists.
                self.layers.append(layer)
                layers_list.append(layer.name())
        # Clear all previous layer.
        self.dlg.comboBox.clear()
        # Add the layer names to the combobox.
        self.dlg.comboBox.addItems(layers_list)

        # Trigger the combobox index change event to refres the bands in their combobox.
        if len(self.layers) > 0:
            self.dlg.comboBox.setCurrentIndex(0)
            self.combobox_index_change_callback(0)


    def combobox_index_change_callback(self, index):
        """
        Callback to handle index change in the combobox.
        """

        layer = self.layers[index]
        band_count = layer.bandCount()

        # Clear all previous item
        self.dlg.comboBox_2.clear()
        # Add the number as string to the combobox.
        self.dlg.comboBox_2.addItems([str(i) for i in range(1, band_count + 1)])


    def checkbox_state_change_callback(self, state):
        """
        Callback function to handle checkbox checkstate changes.
        """

        # Unchecked.
        if state == 0:
            self.dlg.comboBox_2.show()
            self.dlg.lineEdit_6.hide()
        # Checked.
        else:
            self.dlg.comboBox_2.hide()
            self.dlg.lineEdit_6.show()


    def click_callback(self, coordinates):
        """
        Callback function to handle mouse clicks.
        coordinates (QgsPoint): point with the coordinates
        """

        # If both of the START lineEdit fields are empty put the coordinates into them.
        if not self.dlg.lineEdit_2.text() and not self.dlg.lineEdit_3.text():
            self.dlg.lineEdit_2.setText(str(coordinates.x()))
            self.dlg.lineEdit_3.setText(str(coordinates.y()))
        # If both of the END lineEdit fields are empty put the coordinates into them.
        elif not self.dlg.lineEdit_4.text() and not self.dlg.lineEdit_5.text():
            self.dlg.lineEdit_4.setText(str(coordinates.x()))
            self.dlg.lineEdit_5.setText(str(coordinates.y()))


    def validation(self):
        """
        Before call the find path method, validate the given inputs.
        return (tuple): (true | false, message)
        """

        current_index = self.dlg.comboBox.currentIndex()

        # Check the layer first. Is valid raster layer?
        if current_index < 0:
            return (False, 'No layer selected.')

        # Check the layer type. Now I only load raster layers, but I left this here.
        if self.layers[current_index].type() != QgsMapLayer.RasterLayer:
            return (False, 'The selected layer is not raster.')

        if self.dlg.checkBox.isChecked():
            # Check the band number.
            if self.dlg.lineEdit_6.text() == '':
                return (False, 'No band number provided.')

            try:
                int(self.dlg.lineEdit_6.text())
            except:
                return (False, 'Invalid band number.')

        # Check the value limit.
        if self.dlg.lineEdit.text() == '':
            return (False, 'No value provided.')

        try:
            float(self.dlg.lineEdit.text())
        except:
            return (False, 'Invalid value.')

        # Now the coordinates.
        if self.dlg.lineEdit_2.text() == '' or self.dlg.lineEdit_3.text() == '':
            return (False, 'No start coordinates.')

        try:
            float(self.dlg.lineEdit_2.text())
            float(self.dlg.lineEdit_3.text())
        except:
            return (False, 'Invalid start coordinates.')

        if self.dlg.lineEdit_4.text() == '' or self.dlg.lineEdit_5.text() == '':
            return (False, 'No end coordinates.')

        try:
            float(self.dlg.lineEdit_4.text())
            float(self.dlg.lineEdit_5.text())
        except:
            return (False, 'Invalid end coordinates.')

        return (True,)


    def find_path(self):
        # First validate all the datas.
        validation_result = self.validation()
        if not validation_result[0]:
            QgsMessageLog.logMessage(validation_result[1])
            return

        # Index of the currently selected layer.
        selected_layer_index = self.dlg.comboBox.currentIndex()
        # Current layer object.
        layer = self.layers[selected_layer_index]
        # Data provider object of the layer.
        provider = layer.dataProvider()
        # Open the layer from its uri (basically it's a path for the file) with update acces.
        raster = gdal.Open(str(provider.dataSourceUri()), gdal.GA_Update)

        # Set the transform matrix for this instance from the opened raster layer.
        self.geo_transform_matrix = raster.GetGeoTransform()

        # Set the pixel size in the CRS of the raster.
        self.raster_size_x = layer.rasterUnitsPerPixelX()
        self.raster_size_y = layer.rasterUnitsPerPixelY()

        # Set the CRS from our raster.
        self.crs = layer.crs()

        # Get the band number.
        if self.dlg.checkBox.isChecked():
            band_number = int(self.dlg.lineEdit_6.text())
        else:
            band_number = self.dlg.comboBox_2.currentIndex() + 1

        # The band which contains the information.
        band = raster.GetRasterBand(band_number)

        # The max value.
        max_value = float(self.dlg.lineEdit.text())

        # Try to read the given band.
        try:
            band_array = band.ReadAsArray()
        except:
            QgsMessageLog.logMessage('Invalid band number.')
            return

        # Get the starting and ending coordinates. Numpy is working (default) with row ordered arrays,
        # while QGIS the opposite.
        start_coordinates = self.get_pixel_coordinates(float(self.dlg.lineEdit_2.text()), float(self.dlg.lineEdit_3.text()))
        start_coordinates_np = start_coordinates[::-1]
        end_coordinates = self.get_pixel_coordinates(float(self.dlg.lineEdit_4.text()), float(self.dlg.lineEdit_5.text()))
        end_coordinates_np = end_coordinates[::-1]

        # Check the coordinates aren't "wall" pixels.
        if band_array[start_coordinates_np[0], start_coordinates_np[1]] >= max_value:
            QgsMessageLog.logMessage('The starting coordinates are above the maximum value.')
            return
        if band_array[end_coordinates_np[0], end_coordinates_np[1]] >= max_value:
            QgsMessageLog.logMessage('The ending coordinates are above the maximum value.')
            return

        # Create copy from the band. To secure our raster and don't overwrite accidentally.
        grid = np.copy(band_array)

        # Process the grid for the algorithm.
        # Inf = wall
        # 1 = free area
        grid[band_array >= max_value] = np.inf
        grid[band_array < max_value] = 1

        # Get the time for measure the algorithm.
        t0 = time()

        # Get the path finally!
        path = pyastar.astar_path(grid, start_coordinates_np, end_coordinates_np)

        # Duration of the algorithm running time.
        duration = time() - t0

        # If no path found.
        if not len(path):
            QgsMessageLog.logMessage('No path found!')
            return

        QgsMessageLog.logMessage('Path found in %.6fs.' % duration)
        QgsMessageLog.logMessage('Steps: ' + str(len(path)))

        # Create the vector layer from the path and get the length of the created line.
        path_length = self.create_vector_layer(path)

        # Type of the CRS map unit.
        unit_type = QgsUnitTypes.encodeUnit(self.crs.mapUnits())

        self.dlg.label_10.setText('Path length: %.1f %s' % (path_length, unit_type))

        # Reload the layers into the comobox.
        self.init_combobox()

        return


    def create_vector_layer(self, path):
        """
        Create vector layer from the given path.
        path (list): list of the coordinates
        return (float): length of the created line
        """

        # New QGIS Vector layer with the base (raster) layer's CRS.
        vector_layer = QgsVectorLayer('LineString?crs=' + self.crs.toWkt(), 'Path', 'memory')
        # Get the layer renderer and the feature symbol.
        symbol = vector_layer.rendererV2().symbols2(QgsRenderContext())[0]
        # Set the feature (line) width.
        symbol.setWidth(1.0)
        # Now set the color of the feature (line) random.
        symbol.setColor(QColor.fromRgb(randint(0,255), randint(0,255), randint(0,255)))

        # Get the layer provider.
        provider = vector_layer.dataProvider()

        # Enable layer edit.
        vector_layer.startEditing()

        # Line features created from the path (list of QGIS points).
        points = []

        # Iterates over the points in a path.
        for point in path:
            # Get the CRS coordinates of the point,
            crs_coordinate = self.get_crs_coordinates(point[1], point[0])
            # then create a QGIS point from it.
            points.append(QgsPoint(crs_coordinate[0], crs_coordinate[1]))

        # New QGIS feature.
        line = QgsFeature()

        # Set feature (line) geometry from the points.
        line.setGeometry(QgsGeometry.fromPolyline(points))

        # Add the features to the vector (provider).
        provider.addFeatures([line])

        # Commit ("save") changes to the vector layer.
        vector_layer.commitChanges()

        # Then add it to the project.
        QgsMapLayerRegistry.instance().addMapLayer(vector_layer)

        return line.geometry().length()


    def get_pixel_coordinates(self, x, y):
        """
        This method calculates the image pixel coordinate for a real location.
        x (double): x coordinate
        y (double): y coordinate
        return (list): [x, y]
        """


        if (not self.geo_transform_matrix):
            QgsMessageLog.logMessage('No geo transform matrix.')
            return [0, 0]

        # Honestly I just copied this block from the QGIS Python Programming Cookbook. I didn't dig into deeper,
        # but more or less it's trivial. It uses parameters from the georeferencing information of the raster.
        ul_x = self.geo_transform_matrix[0]
        ul_y = self.geo_transform_matrix[3]
        x_dist = self.geo_transform_matrix[1]
        y_dist = self.geo_transform_matrix[5]
        rtn_x = self.geo_transform_matrix[2]
        rtn_y = self.geo_transform_matrix[4]
        # Calculate the pixel X,Y.
        pixel_x = int((x - ul_x) / x_dist)
        pixel_y = int((y - ul_y) / y_dist)

        return [pixel_x, pixel_y]


    def get_crs_coordinates(self, x, y):
        """
        This method calculates the CRS coordinate for a pixel location.
        x (int): x coordinate
        y (int): y coordinate
        return (list): [x, y]
        """

        if (not self.geo_transform_matrix):
            QgsMessageLog.logMessage('No geo transform matrix.')
            return [0, 0]

        # Get parameters from georeferencing.
        ul_x = self.geo_transform_matrix[0]
        ul_y = self.geo_transform_matrix[3]
        x_dist = self.geo_transform_matrix[1]
        y_dist = self.geo_transform_matrix[5]
        rtn_x = self.geo_transform_matrix[2]
        rtn_y = self.geo_transform_matrix[4]
        # Calculate the CRS X,Y.
        crs_x = (x * x_dist) + ul_x
        crs_y = (y * y_dist) + ul_y

        # Now the coordinates are in the topleft (?) corner if the pixels so I move them to the center.
        # May not work for your raster and CRS. In this case please contact me! (:
        crs_x += self.raster_size_x / 2
        crs_y -= self.raster_size_y / 2

        return [crs_x, crs_y]


    def clear_coordinates(self):
        """
        Clear all coordinates field (START(X,Y) END(X,Y)) on the GUI.
        """

        self.dlg.lineEdit_2.setText('')
        self.dlg.lineEdit_3.setText('')
        self.dlg.lineEdit_4.setText('')
        self.dlg.lineEdit_5.setText('')


    def get_eucl_dist(self, point_1, point_2):
        """
        Calculate the distance between two points.
        point_1 (list/tuple): first point coordinates (x, y)
        point_2 (list/tuple): second point coordinates (x, y)
        return (float): the calculated distance
        """

        return ((point_1[0] - point_2[0])**2 + (point_1[1] - point_2[1])**2)**0.5


class MySelectorTool(QgsMapTool):
    """
    Inherits the QGIS identify tool (tool is deactivated once another tool takes focus)
    """
    def __init__(self, canvas, callback):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.click_event = pyqtSignal()
        self.callback = callback


    def canvasReleaseEvent(self, mouseEvent):
        """
        Mouse click events.
        """

        # Coordinates.
        x = mouseEvent.pos().x()
        y = mouseEvent.pos().y()
        # Transform the coordinates into map coordinates (CRS).
        point = self.canvas.getCoordinateTransform().toMapCoordinates(x, y)
        # Call the callback function.
        self.callback(point)
