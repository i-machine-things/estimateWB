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


def comboAlive(combo):
	""" False if the combo is None or its Qt object has been deleted (e.g. by a toolbar rebuild) """
	if combo is None:
		return False
	try:
		combo.objectName()
		return True
	except RuntimeError:
		return False


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


def fillMaterialCombo(combo):
	"""
		(re)fills the combo with the material list and the custom density entry at the end,
		keeping the current pick if it still exists. called again after materials are added or
		removed in the preferences
	"""
	from .resources import materials
	if combo.count():
		current = combo.currentText() if combo.currentData() != CUSTOM_DENSITY else CUSTOM_DENSITY
	else:
		# a new combo, e.g. after a toolbar rebuild: restore the pick from before, if any
		current = lastPick
	combo.blockSignals(True)
	combo.clear()
	combo.addItems(list(materials.keys()))
	# custom density lives in the same dropdown, see _onMaterialActivated()
	combo.addItem(LANG.chunk("customDensityItem"), CUSTOM_DENSITY)
	updateCustomItem(combo)
	if current is None:
		index = 0
	else:
		index = combo.findData(CUSTOM_DENSITY) if current == CUSTOM_DENSITY else combo.findText(current)
	combo.setCurrentIndex(max(index, 0))
	combo.setProperty("estimatePreviousIndex", combo.currentIndex())
	combo.blockSignals(False)
	if index < 0:
		# the picked material was renamed or removed in the preferences, say so instead of
		# silently calculating with another one
		from . import tools
		tools.report(LANG.chunk("materialNoLongerListed", {":material": current, ":fallback": combo.currentText()}))
	# signals were blocked, so record the (possibly changed) pick directly
	_rememberPick(combo)


def refreshMaterialCombo():
	""" refills the toolbar's material combo, if it has been installed yet """
	# comboAlive: if a toolbar rebuild deleted it, the next one installed is filled anyway
	if comboAlive(materialCombo):
		fillMaterialCombo(materialCombo)


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


# setting -> (group command name, option values in dropdown order), filled in Initialize()
settingGroups = {}


def _associated(action):
	"""
		the widgets an action has been added to. Qt6 (PySide6) replaced associatedWidgets() with
		associatedObjects(), which returns every associated QObject, not just widgets, hence the
		isinstance checks where this is used; Qt5 builds only have associatedWidgets()
	"""
	if hasattr(action, "associatedObjects"):
		return action.associatedObjects()
	return action.associatedWidgets()


def syncSettingButton(setting: str):
	"""
		shows the option in use on the setting's toolbar dropdown button. FreeCAD only does that itself
		for picks from the dropdown or the settings menu, not when the option is set otherwise
		(the separate unit commands from a shortcut or a custom toolbar, or a macro)
	"""
	from . import estimateSettings
	if setting not in settingGroups:
		return
	group, values = settingGroups[setting]
	command = FreeCADGui.Command.get(group)
	current = estimateSettings.get(setting)
	if not command or current not in values:
		return
	actions = command.getAction()
	index = values.index(current)
	if index >= len(actions):
		return
	# the group's own action (the toolbar button's) is named after the command. the same as
	# FreeCAD's ActionGroup::setCheckedAction(): icon and tooltip of the option, and the option
	# as the group's default, which is what clicking the button itself runs
	groupAction = FreeCADGui.getMainWindow().findChild(QtGui.QAction, group)
	if not groupAction:
		return
	groupAction.setIcon(actions[index].icon())
	groupAction.setToolTip(actions[index].toolTip())
	if groupAction.parent():
		groupAction.parent().setProperty("defaultAction", index)


def _findCalculateButton():
	"""
		returns (toolbar, action) of the Estimate_Calculate group button, or (None, None)
		a group command only hands out its dropdown's actions, so go from those to the dropdown
		menu, whose parent is the toolbar button (see FreeCAD's ActionGroup::addTo())
	"""
	command = FreeCADGui.Command.get("Estimate_Calculate")
	if not command:
		return None, None
	# the button can be on more than one toolbar if the user added it to a custom one,
	# prefer the workbench's own toolbar
	found = []
	for action in command.getAction():
		for menu in _associated(action):
			if not isinstance(menu, QtGui.QMenu):
				continue
			button = menu.parent()
			toolbar = button.parent() if isinstance(button, QtGui.QToolButton) else None
			if not isinstance(toolbar, QtGui.QToolBar):
				continue
			for anchor in toolbar.actions():
				if toolbar.widgetForAction(anchor) is button:
					if toolbar.objectName() == LANG.chunk("estimateMenuText"):
						return toolbar, anchor
					found.append((toolbar, anchor))
	return found[0] if found else (None, None)


def _installMaterialCombo():
	global materialCombo

	# found through FreeCAD's own command manager instead of guessing at Qt object names
	toolbar, anchor = _findCalculateButton()
	if not toolbar:
		materialCombo = None
		FreeCAD.Console.PrintError("estimateWB: Estimate_Calculate has no toolbar button to attach the material combo to\n")
		return
	existing = toolbar.findChild(QtGui.QComboBox, "Estimate_MaterialCombo")
	if comboAlive(existing):
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
	fillMaterialCombo(combo)
	combo.activated.connect(lambda index, c = combo: _onMaterialActivated(c, index))
	combo.currentIndexChanged.connect(lambda index, c = combo: _rememberPick(c))
	# inserted right before the calculate button, which reads this combo's
	# current selection when clicked
	toolbar.insertWidget(anchor, combo)
	# FreeCAD can rebuild the toolbar without activating the workbench again (e.g. after
	# Tools > Customize), which deletes the combo together with its toolbar action
	combo.destroyed.connect(lambda *_: QtCore.QTimer.singleShot(0, _reinstallMaterialCombo))
	materialCombo = combo


def _reinstallMaterialCombo():
	""" puts the combo back if it got deleted while the workbench is still active """
	global materialCombo
	if comboAlive(materialCombo):
		return
	materialCombo = None
	if isinstance(FreeCADGui.activeWorkbench(), estimateWB):
		_installMaterialCombo()


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
			"Scale_qmm": commands.Set_estimateSettings("sizeScale", "mm"),
			"Scale_qcm": commands.Set_estimateSettings("sizeScale", "cm"),
			"Scale_qm": commands.Set_estimateSettings("sizeScale", "m"),
			"Scale_qin": commands.Set_estimateSettings("sizeScale", "in"),
			"Scale_qft": commands.Set_estimateSettings("sizeScale", "ft"),
			"Weight_g": commands.Set_estimateSettings("weightUnit", "g"),
			"Weight_kg": commands.Set_estimateSettings("weightUnit", "kg"),
			"Weight_lb": commands.Set_estimateSettings("weightUnit", "lb"),
			"Weight_oz": commands.Set_estimateSettings("weightUnit", "oz")
		}
		# you could as well add every command linewise, with the first parameter being the assigned command name, the second the respective function call
		for type in fn:
			FreeCADGui.addCommand(type, fn[type])
		# the toolbar bundles the options of each setting into one dropdown button
		groups = {}
		for setting, group in (("sizeScale", "Settings_VolumeUnit"), ("weightUnit", "Settings_WeightUnit")):
			options = {name: command.fnParams[1] for name, command in fn.items() if command.fnParams[0] == setting}
			FreeCADGui.addCommand(group, commands.Settings_Group(setting, options))
			groups[group] = options
			settingGroups[setting] = (group, list(options.values()))
		# TMYK: the first parameter is visible e.g as the menu entry, second parameter is a list of the assigned commands names
		# you could as well assign a manual list as second parameter
		self.appendToolbar(LANG.chunk("settingsMenuText"), list(groups.keys()))
		# the groups again, as submenus: picks there go through the group, so its toolbar button follows
		self.appendMenu(LANG.chunk("settingsMenuText"), list(groups.keys()))

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
		QtCore.QTimer.singleShot(0, _installMaterialCombo)

	def Deactivated(self):
		pass

	def ContextMenu(self, recipient):
		# self.appendContextMenu("My commands",self.list) # add commands to the context menu / right click
		pass

	# This function is mandatory if this is a full Python workbench
	# This is not a template, the returned string should be exactly "Gui::PythonWorkbench"
	def GetClassName(self): 
		return "Gui::PythonWorkbench"


# workbench settings in Edit > Preferences > Estimate
# the dialog looks the group icon up as "preferences-estimate" in FreeCAD's icon paths
import os
FreeCADGui.addIconPath(os.path.dirname(icon("preferences-estimate")))
from .preferences import EstimatePreferencePage
FreeCADGui.addPreferencePage(EstimatePreferencePage, "Estimate")

FreeCADGui.addWorkbench(estimateWB())