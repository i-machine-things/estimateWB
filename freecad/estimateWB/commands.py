from .resources import icon, LANG
from . import tools, estimateSettings
import json

import FreeCADGui
from FreeCADGui import Selection

class BaseCommand():
	"""
		TMYK: here the commands are defined by child classes, each their own
		* name
		* function
		* pixmap (icon)
		* menu text
		* tooltip

		available commands (classes extending the base command) are initialized with their
		respective properties before FreeCAD calls their methods on interaction.
		basically there is no need to change anything in this class as far as i know
	"""
	fnParams = {}
	FreeCADGui.doCommandGui("import freecad.estimateWB.commands")

	def __init__(self):
		pass

	def GetResources(self):
		return {"Pixmap": self.pixmap,
				"MenuText": self.menuText,
				"ToolTip": self.toolTip}

	def Activated(self):
		"""
			as opposed to the online ressources the parameters are converted to a tuple and json for string passing.
			this allows for multiple parameters for commands
		"""
		FreeCADGui.doCommandGui(f"freecad.estimateWB.commands.{self.__class__.__name__}.do('{json.dumps(self.fnParams)}')")

	@classmethod
	def do(self, fnParams:str = ""):
		"""
			reconvert the former passed string back to a tuple and spread as non keyword parameters
		"""
		self.function(*json.loads(fnParams))

################################################################################

class Estimate_Volume(BaseCommand):
	# TMYK: without a parameter for the function the command can be set up just like this
	name = LANG.chunk("estimateVolumeName")
	function = tools.estimateVolume
	pixmap = icon("icon")
	menuText = LANG.chunk("estimateVolumeName")
	toolTip = LANG.chunk("estimateVolumeToolTip")
	def IsActive(self):
		return Selection.hasSelection()

################################################################################

class Estimate_By_Material(BaseCommand):
	# TMYK: the material comes from the combo box the workbench embeds next to this
	# button in the toolbar (see init_gui.materialCombo), so this overrides Activated()
	# instead of just declaring fnParams up front
	name = LANG.chunk("estimateByMaterialName")
	function = tools.estimateWeight
	pixmap = icon("calculate")
	menuText = LANG.chunk("estimateByMaterialName")
	toolTip = LANG.chunk("estimateByMaterialToolTip")
	def IsActive(self):
		return Selection.hasSelection()
	def Activated(self):
		tools.showReportView()
		from . import init_gui
		combo = init_gui.materialCombo
		if not combo:
			tools.report("estimateWB: material combo box is not available, cannot estimate weight")
			return
		if combo.currentData() == init_gui.CUSTOM_DENSITY:
			# custom density entry: the density was saved when it was picked in the combo,
			# only prompt here as a fallback if there is none saved
			density = tools.getCustomDensity() or tools.promptDensity()
			if not density:
				tools.report(LANG.chunk("promptDensityError"))
				return
			tools.setCustomDensity(density)
			init_gui.updateCustomItem(combo)
			self.fnParams = (None, density)
		else:
			self.fnParams = (combo.currentText(),)
		FreeCADGui.doCommandGui(f"freecad.estimateWB.commands.{self.__class__.__name__}.do('{json.dumps(self.fnParams)}')")

################################################################################

class Set_estimateSettings(BaseCommand):
	"""
		currently supported fnParams are
		* sizeScale - mm, cm and m
		* weightUnit - g, kg and lb
		* reportOutput - console and popup

		icons have to be named accordingly fnParams[0]_fnParams[1].svg
		language chunks should start with fnParams[0] as well

		see __init__.py resources.LANG and languages/*.json
	"""
	function = estimateSettings.set
	def __init__(self, *fnParams):
		self.fnParams = fnParams
		setting, value = fnParams
		self.name = LANG.chunk(setting + "_Setting", {":option": value})
		self.pixmap = icon(f"{setting}_{value}")
		self.menuText = LANG.chunk(setting + "_Setting", {":option": value})
		self.toolTip = LANG.chunk(setting + "_Setting", {":option": value})
	def IsActive(self):
		setting, value = self.fnParams
		return estimateSettings.get(setting) != value

