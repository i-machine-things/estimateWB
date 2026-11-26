from .resources import LANG, getUserMaterials, setUserMaterials
from . import estimateSettings

import FreeCAD
from math import isfinite
from PySide import QtCore, QtGui


class EstimatePreferencePage:
	"""
		TMYK: a python preference page for Edit > Preferences, registered in init_gui.py with
		FreeCADGui.addPreferencePage(). FreeCAD shows self.form and calls loadSettings() when
		the dialog opens and saveSettings() on OK/Apply
	"""
	def __init__(self, parent = None):
		# the materials as loaded into the table, see saveSettings()
		self.loadedMaterials = None
		self.form = QtGui.QWidget(parent)
		self.form.setWindowTitle(LANG.chunk("prefsTitle"))
		layout = QtGui.QVBoxLayout(self.form)

		# result output, formerly the report view / popup toolbar toggle
		output = QtGui.QGroupBox(LANG.chunk("prefsOutputGroup"))
		outputLayout = QtGui.QVBoxLayout(output)
		self.outputConsole = QtGui.QRadioButton(LANG.chunk("prefsOutputConsole"))
		self.outputPopup = QtGui.QRadioButton(LANG.chunk("prefsOutputPopup"))
		outputLayout.addWidget(self.outputConsole)
		outputLayout.addWidget(self.outputPopup)
		layout.addWidget(output)

		# user added materials, listed in the toolbar's material combo after the built-in ones
		materials = QtGui.QGroupBox(LANG.chunk("prefsMaterialsGroup"))
		materialsLayout = QtGui.QVBoxLayout(materials)
		hint = QtGui.QLabel(LANG.chunk("prefsMaterialsHint"))
		hint.setWordWrap(True)
		materialsLayout.addWidget(hint)
		self.table = QtGui.QTableWidget(0, 2)
		self.table.setHorizontalHeaderLabels([LANG.chunk("prefsMaterialName"), LANG.chunk("prefsMaterialDensity")])
		self.table.horizontalHeader().setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		self.table.verticalHeader().setVisible(False)
		self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		materialsLayout.addWidget(self.table)
		buttons = QtGui.QHBoxLayout()
		add = QtGui.QPushButton(LANG.chunk("prefsMaterialAdd"))
		add.clicked.connect(self.addRow)
		remove = QtGui.QPushButton(LANG.chunk("prefsMaterialRemove"))
		remove.clicked.connect(self.removeRows)
		buttons.addWidget(add)
		buttons.addWidget(remove)
		buttons.addStretch()
		materialsLayout.addLayout(buttons)
		layout.addWidget(materials)

	def addRow(self, name: str = "", density: str = ""):
		""" appends a material row; without arguments an empty one to type into """
		row = self.table.rowCount()
		self.table.insertRow(row)
		self.table.setItem(row, 0, QtGui.QTableWidgetItem(name if isinstance(name, str) else ""))
		self.table.setItem(row, 1, QtGui.QTableWidgetItem(density))
		if not name:
			self.table.setCurrentCell(row, 0)
			self.table.editItem(self.table.item(row, 0))

	def removeRows(self):
		for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse = True):
			self.table.removeRow(row)

	def loadSettings(self):
		popup = estimateSettings.get("reportOutput") == "popup"
		self.outputPopup.setChecked(popup)
		self.outputConsole.setChecked(not popup)
		self.table.setRowCount(0)
		self.loadedMaterials = getUserMaterials()
		for name, density in self.loadedMaterials.items():
			# str() keeps every digit, :g would round to 6 and save that on the next OK
			self.addRow(name, str(density))

	def saveSettings(self):
		estimateSettings.set("reportOutput", "popup" if self.outputPopup.isChecked() else "console")

		# commit a cell that is still being edited
		self.table.setCurrentIndex(QtCore.QModelIndex())
		user = {}
		rows = {}
		for row in range(self.table.rowCount()):
			name = (self.table.item(row, 0).text() if self.table.item(row, 0) else "").strip()
			density = (self.table.item(row, 1).text() if self.table.item(row, 1) else "").strip()
			if not name and not density:
				continue
			try:
				value = float(density.replace(",", "."))
			except ValueError:
				value = 0
			if not name or not isfinite(value) or value <= 0:
				FreeCAD.Console.PrintWarning(LANG.chunk("prefsMaterialSkipped", {":row": str(row + 1)}) + "\n")
				continue
			# the material list already has an entry with this label, picking it would be ambiguous
			if name == LANG.chunk("customDensityItem"):
				FreeCAD.Console.PrintWarning(LANG.chunk("prefsMaterialReserved", {":row": str(row + 1), ":name": name}) + "\n")
				continue
			if name in user:
				FreeCAD.Console.PrintWarning(LANG.chunk("prefsMaterialDuplicate", {":name": name, ":row": str(rows[name]), ":used": str(row + 1)}) + "\n")
			user[name] = value
			rows[name] = row + 1
		# only store when the table changed: if the stored list couldn't be read, the table loaded
		# empty and saving it unchanged (e.g. for the output setting) would overwrite it for good
		if user != self.loadedMaterials:
			setUserMaterials(user)
			self.loadedMaterials = user

		# the toolbar combo only exists once the workbench has been activated
		from . import init_gui
		init_gui.refreshMaterialCombo()
