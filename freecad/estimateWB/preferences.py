from .resources import LANG, getUserMaterials, setUserMaterials
from . import estimateSettings

import FreeCAD
from PySide import QtCore, QtGui


class EstimatePreferencePage:
	"""
		TMYK: a python preference page for Edit > Preferences, registered in init_gui.py with
		FreeCADGui.addPreferencePage(). FreeCAD shows self.form and calls loadSettings() when
		the dialog opens and saveSettings() on OK/Apply
	"""
	def __init__(self, parent = None):
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
		for name, density in getUserMaterials().items():
			self.addRow(name, f"{density:g}")

	def saveSettings(self):
		estimateSettings.set("reportOutput", "popup" if self.outputPopup.isChecked() else "console")

		user = {}
		for row in range(self.table.rowCount()):
			name = (self.table.item(row, 0).text() if self.table.item(row, 0) else "").strip()
			density = (self.table.item(row, 1).text() if self.table.item(row, 1) else "").strip()
			if not name and not density:
				continue
			try:
				value = float(density.replace(",", "."))
			except ValueError:
				value = 0
			if not name or value <= 0:
				FreeCAD.Console.PrintWarning(LANG.chunk("prefsMaterialSkipped", {":row": str(row + 1)}) + "\n")
				continue
			user[name] = value
		setUserMaterials(user)

		# the toolbar combo only exists once the workbench has been activated
		from . import init_gui
		init_gui.refreshMaterialCombo()
