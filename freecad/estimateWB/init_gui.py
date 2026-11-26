from .resources import icon, LANG

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

# reference to the embedded material combo box, read by commands.Estimate_By_Material
# when the calculate button next to it is clicked
materialCombo = None

class estimateWB(FreeCADGui.Workbench):
	"""
		this is the main workbench class that embeds the menu and toolbar buttons with assigned functions
	"""

	MenuText = "Estimate"
	ToolTip = LANG.chunk("wbToolTip")
	Icon = icon("icon")
	
	def Initialize(self):
		"""
			This function is executed when FreeCAD starts
		"""

		# TMYK: import all the needed files that contain your FreeCAD commands here
		from . import commands 

		# setting commands
		fn = {
			"Report_console": commands.Set_estimateSettings("reportOutput", "console"),
			"Report_popup": commands.Set_estimateSettings("reportOutput", "popup"),
			"Scale_qmm": commands.Set_estimateSettings("sizeScale", "mm"),
			"Scale_qcm": commands.Set_estimateSettings("sizeScale", "cm"),
			"Scale_qm": commands.Set_estimateSettings("sizeScale", "m"),
			"Weight_g": commands.Set_estimateSettings("weightUnit", "g"),
			"Weight_kg": commands.Set_estimateSettings("weightUnit", "kg"),
			"Weight_lb": commands.Set_estimateSettings("weightUnit", "lb")
		}
		# TMYK: the first parameter is visible e.g as the menu entry, second parameter is a list of the assigned commands names
		# you could as well assign a manual list as second parameter
		self.appendToolbar(LANG.chunk("settingsMenuText"), list(fn.keys()))
		self.appendMenu(LANG.chunk("settingsMenuText"), list(fn.keys()))
		# you could as well add every command linewise, with the first parameter being the assigned command name, the second the respective function call
		for type in fn:
			FreeCADGui.addCommand(type, fn[type])

		# estimate commands
		# TMYK: but assigning like this is actually cool, because it is dynamically extendable
		fn = {
			"Estimate_Volume": commands.Estimate_Volume(),
			"Estimate_Weight_Custom": commands.Estimate_Weight_Custom(),
			"Estimate_By_Material": commands.Estimate_By_Material()
		}

		self.appendToolbar(LANG.chunk("estimateMenuText"), list(fn.keys()))
		self.appendMenu(LANG.chunk("estimateMenuText"), list(fn.keys()))
		for type in fn:
			FreeCADGui.addCommand(type, fn[type])

	def Activated(self):
		# the toolbar is only fully built once Qt has processed the pending events from
		# appendToolbar(), so the combo is inserted on the next event loop tick rather
		# than directly here
		QtCore.QTimer.singleShot(0, self._installMaterialCombo)

	def _installMaterialCombo(self):
		global materialCombo
		from .resources import materials

		# look the command's QAction(s) up through FreeCAD's own command manager instead
		# of guessing at Qt object names, then find the toolbar(s) it actually ended up in
		command = FreeCADGui.Command.get("Estimate_By_Material")
		if not command:
			FreeCAD.Console.PrintError("estimateWB: could not find the Estimate_By_Material command\n")
			return

		for action in command.getAction():
			# Qt6 (PySide6) replaced associatedWidgets() with associatedObjects(), which returns
			# every associated QObject, not just widgets, hence the isinstance check; Qt5
			# (FreeCAD < 1.0) only has associatedWidgets()
			if hasattr(action, "associatedObjects"):
				associated = action.associatedObjects()
			else:
				associated = action.associatedWidgets()
			for widget in associated:
				if not isinstance(widget, QtGui.QToolBar):
					continue
				existing = widget.findChild(QtGui.QComboBox, "Estimate_MaterialCombo")
				if existing:
					materialCombo = existing
					return
				combo = QtGui.QComboBox()
				combo.setObjectName("Estimate_MaterialCombo")
				combo.setToolTip(LANG.chunk("estimateByMaterialToolTip"))
				combo.addItems(list(materials.keys()))
				# inserted right before the calculate button, which reads this combo's
				# current selection when clicked
				widget.insertWidget(action, combo)
				materialCombo = combo
				return

		FreeCAD.Console.PrintError("estimateWB: Estimate_By_Material has no toolbar action to attach the material combo to\n")

	def Deactivated(self):
		pass

	def ContextMenu(self, recipient):
		# self.appendContextMenu("My commands",self.list) # add commands to the context menu / right click
		pass

	# This function is mandatory if this is a full Python workbench
	# This is not a template, the returned string should be exactly "Gui::PythonWorkbench"
	def GetClassName(self): 
		return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(estimateWB())