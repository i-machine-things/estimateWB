from .resources import icon, LANG

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

# reference to the embedded material combo box, read by commands.Estimate_By_Material
# when the calculate button next to it is clicked
materialCombo = None

# item data marking the combo's custom density entry (material entries carry no data)
CUSTOM_DENSITY = "__custom_density__"

# the last picked combo entry (material name or CUSTOM_DENSITY). kept outside the combo because
# FreeCAD rebuilds the toolbar when switching workbenches, which replaces the combo
lastPick = None


def _rememberPick(combo):
	global lastPick
	lastPick = combo.currentData() if combo.currentData() == CUSTOM_DENSITY else combo.currentText()


def updateCustomItem(combo):
	""" labels the custom density entry with the saved density, if there is one """
	from . import tools
	index = combo.findData(CUSTOM_DENSITY)
	if index < 0:
		return
	density = tools.getCustomDensity()
	if density:
		combo.setItemText(index, LANG.chunk("customDensityItemSet", {":density": f"{density:g}"}))
	else:
		combo.setItemText(index, LANG.chunk("customDensityItem"))


def _onMaterialActivated(combo, index):
	"""
		picking the custom density entry (also re-picking it) prompts for the density and saves it,
		cancelling falls back to the previously picked entry
	"""
	from . import tools
	if combo.itemData(index) != CUSTOM_DENSITY:
		combo.setProperty("estimatePreviousIndex", index)
		return
	density = tools.promptDensity(tools.getCustomDensity())
	if density:
		tools.setCustomDensity(density)
		updateCustomItem(combo)
		combo.setProperty("estimatePreviousIndex", index)
		return
	# cancelled: go back to what was picked before (that is the custom entry itself when re-picking it)
	previous = combo.property("estimatePreviousIndex")
	combo.setCurrentIndex(previous if previous is not None else 0)


def _findCalculateButton():
	"""
		returns (toolbar, action) of the Estimate_Calculate group button, or (None, None)
		a group command only hands out its dropdown's actions, so go from those to the dropdown
		menu, whose parent is the toolbar button (see FreeCAD's ActionGroup::addTo())
	"""
	command = FreeCADGui.Command.get("Estimate_Calculate")
	if not command:
		return None, None
	for action in command.getAction():
		# Qt6 (PySide6) replaced associatedWidgets() with associatedObjects(), which returns
		# every associated QObject, not just widgets, hence the isinstance checks; Qt5
		# (FreeCAD < 1.0) only has associatedWidgets()
		if hasattr(action, "associatedObjects"):
			associated = action.associatedObjects()
		else:
			associated = action.associatedWidgets()
		for menu in associated:
			if not isinstance(menu, QtGui.QMenu):
				continue
			button = menu.parent()
			toolbar = button.parent() if isinstance(button, QtGui.QToolButton) else None
			if not isinstance(toolbar, QtGui.QToolBar):
				continue
			for anchor in toolbar.actions():
				if toolbar.widgetForAction(anchor) is button:
					return toolbar, anchor
	return None, None

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
			"Estimate_By_Material": commands.Estimate_By_Material(),
			"Estimate_Volume": commands.Estimate_Volume()
		}
		for type in fn:
			FreeCADGui.addCommand(type, fn[type])
		# weight and volume share one toolbar button with a dropdown arrow (a FreeCAD group
		# command), the material combo is placed in front of it; the menu lists both plainly
		FreeCADGui.addCommand("Estimate_Calculate", commands.Estimate_Calculate(list(fn.keys())))

		self.appendToolbar(LANG.chunk("estimateMenuText"), ["Estimate_Calculate"])
		self.appendMenu(LANG.chunk("estimateMenuText"), list(fn.keys()))

	def Activated(self):
		# the toolbar is only fully built once Qt has processed the pending events from
		# appendToolbar(), so the combo is inserted on the next event loop tick rather
		# than directly here
		QtCore.QTimer.singleShot(0, self._installMaterialCombo)

	def _installMaterialCombo(self):
		global materialCombo
		from .resources import materials

		# found through FreeCAD's own command manager instead of guessing at Qt object names
		toolbar, anchor = _findCalculateButton()
		if not toolbar:
			FreeCAD.Console.PrintError("estimateWB: Estimate_Calculate has no toolbar button to attach the material combo to\n")
			return
		existing = toolbar.findChild(QtGui.QComboBox, "Estimate_MaterialCombo")
		if existing:
			materialCombo = existing
			return
		combo = QtGui.QComboBox()
		combo.setObjectName("Estimate_MaterialCombo")
		combo.setToolTip(LANG.chunk("estimateByMaterialToolTip"))
		# resize with the custom density label, which changes after the first show
		combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
		# show 10 entries with a scrollbar instead of a list over the whole screen height;
		# styles with a popup-style combo ignore maxVisibleItems unless combobox-popup is 0
		combo.setMaxVisibleItems(10)
		combo.setStyleSheet("QComboBox { combobox-popup: 0; }")
		# the list view picks AlwaysOff while it still assumes popup mode, so set it explicitly
		combo.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		combo.addItems(list(materials.keys()))
		# custom density lives in the same dropdown, see _onMaterialActivated()
		combo.addItem(LANG.chunk("customDensityItem"), CUSTOM_DENSITY)
		updateCustomItem(combo)
		# restore the pick from before a toolbar rebuild, if any
		if lastPick is not None:
			index = combo.findData(CUSTOM_DENSITY) if lastPick == CUSTOM_DENSITY else combo.findText(lastPick)
			combo.setCurrentIndex(max(index, 0))
		combo.setProperty("estimatePreviousIndex", combo.currentIndex())
		combo.activated.connect(lambda index, c = combo: _onMaterialActivated(c, index))
		combo.currentIndexChanged.connect(lambda index, c = combo: _rememberPick(c))
		# inserted right before the calculate button, which reads this combo's
		# current selection when clicked
		toolbar.insertWidget(anchor, combo)
		materialCombo = combo

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