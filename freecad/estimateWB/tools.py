from .resources import materials, LANG
from . import estimateSettings
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Optional  # not str|None: that needs Python 3.10, older FreeCAD ships 3.8

import FreeCAD
import FreeCADGui
from PySide import QtGui

################################################################################
# reporting
################################################################################

def report(msg: str):
	""" prints the message to the report view panel and raises the panel, so it isn't missed """
	showReportView()
	now = datetime.now().strftime("%H:%M:%S")
	FreeCAD.Console.PrintMessage(f"\n{now} {msg}")


def showReportView():
	""" raises the Report view panel so console output isn't missed if it's hidden/docked away """
	window = FreeCADGui.getMainWindow()
	report = window.findChild(QtGui.QDockWidget, "Report view") if window else None
	if not report:
		return
	if report.isHidden():
		report.show()
	# raise_() also selects the Report view tab when it is tabified behind another dock
	report.raise_()


def msgbox(title: str, msg: str, copy: str):
	""" displays the result as a popup with option to copy a value """

	# Not sure this is the best way to report stuff in FreeCAD, not a whole lot of things open a new window. I just hate having to try and read
	# the report view for each result. - zackwhit
	msgBox = QtGui.QMessageBox() 
	msgBox.setIcon(QtGui.QMessageBox.Information)
	msgBox.setWindowTitle(title)
	msgBox.setText(msg)
	msgBox.setStandardButtons(QtGui.QMessageBox.Ok)

	# Adding the result to the clipboard
	copyBtn = QtGui.QPushButton(LANG.chunk("resultWeightPopCopy"))
	copyBtn.clicked.connect(lambda: saveToClipboard(copy))
	msgBox.addButton(copyBtn, QtGui.QMessageBox.AcceptRole)
	
	# Show result message box
	msgBox.exec()


def saveToClipboard(textToSave: str):
	"""	copies the parameter to clipboard """
	QtGui.QGuiApplication.clipboard().setText(textToSave)


################################################################################
# custom density
################################################################################

PARAMS = "User parameter:BaseApp/Preferences/Mod/estimateWB"

def promptDensity(default: Optional[float] = None):
	"""
		asks for a density in g/cm³, returns None if cancelled or not processable
		invalid input is reported, cancelling is not
	"""
	# str() keeps every digit of the saved density, :g would round it to 6 on the next OK
	text, ok = QtGui.QInputDialog.getText(None, LANG.chunk("promptDensityTitle"), LANG.chunk("promptDensityText"),
		QtGui.QLineEdit.Normal, str(default) if default else "")
	if not ok:
		return None
	try:
		density = float(text.strip().replace(",", "."))
	except ValueError:
		density = None
	# isfinite: "inf" parses and is > 0, but can't be rounded for the result
	if density is None or not isfinite(density) or density <= 0:
		report(LANG.chunk("promptDensityError"))
		return None
	return density


def getCustomDensity():
	""" returns the saved custom density in g/cm³ or None if none has been saved yet """
	density = FreeCAD.ParamGet(PARAMS).GetFloat("customDensity", 0.0)
	# isfinite: "inf" parses and is > 0, but can't be rounded for the result
	return density if isfinite(density) and density > 0 else None


def setCustomDensity(density: float):
	""" saves the custom density in g/cm³ to the workbench preferences """
	FreeCAD.ParamGet(PARAMS).SetFloat("customDensity", density)


################################################################################
# calculations
################################################################################

SIGNIFICANT_DIGITS = 3

def roundup(number: float):
	"""
		returns the rounded number according to FreeCad settings
		values below 1 keep at least SIGNIFICANT_DIGITS significant digits, so large units like m³ or ft³
		don't round small parts to 0.00 (or 0.0353 ft³ up to 0.04)
	"""
	precision = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Units").GetInt("Decimals")
	precision = 2 if not precision else precision
	# str() gives the shortest decimal that represents the float, so e.g. 2.675 rounds to 2.68 instead
	# of following the binary 2.67499999... down to 2.67
	value = Decimal(str(number))
	rounded = value.quantize(Decimal("1e" + str(-precision)), rounding = ROUND_HALF_UP)
	if value and abs(value) < 1:
		# adjusted() is the exponent of the first significant digit, e.g. -2 for 0.0353
		small = value.quantize(Decimal("1e" + str(-max(precision, SIGNIFICANT_DIGITS - 1 - value.adjusted()))), rounding = ROUND_HALF_UP)
		# keep the extra digits only while the result stays below 1 (0.999999 is 1.00, not 1.000)
		if abs(small) < 1:
			rounded = small
	return rounded


def volumeOf(object: object):
	""" returns the volume of the passed object """
	if hasattr(object, "Shape"):
		return object.Shape.Volume
	else:
		report(LANG.chunk("resultHasNoVolume", {":object": object.Label}))
		return 0.0


def estimateVolume(*void):
	""" calculates the volume of selected objects and reports to the selected report option """
	objects = FreeCADGui.Selection.getSelection()

	volume = 0.0

	for object in objects:
		volume += volumeOf(object)

	if volume == 0:
		if len(objects) > 1 :
			report(LANG.chunk("resultSelectionNoVolume"))
		return

	volume /= float(estimateSettings.get("sizeScaleFactor"))
	
	msg = LANG.chunk("resultHasVolumeOf", {":volume" : f"{roundup(volume)} {estimateSettings.get('sizeScale')}³"})
	if estimateSettings.get("reportOutput") == "console":
		report(msg)
	elif estimateSettings.get("reportOutput") == "popup":
		msgbox(LANG.chunk("resultVolumePopTitle"), msg, f"{str(roundup(volume))}")


def estimateWeight(material : Optional[str] = None, density : Optional[float] = None):
	"""
		calculates the weight of the selected objects according to the passed material and reports to the selected report option  
		an explicitly passed density (e.g. the toolbar's custom density) takes precedence over the material lookup  
		prompts for density if neither has been passed
	"""
	objects = FreeCADGui.Selection.getSelection()

	volume = 0.0

	for object in objects:
		volume += volumeOf(object)
		
	if volume == 0:
		if len(objects) > 1 :
			report(LANG.chunk("resultSelectionNoVolume"))
		return
    
	if material == "None": # even None, if passed, ends up a string here
		material = None
	
	if density is None:
		if material:
			density = materials.get(material)
		else:
			density = promptDensity()
			if not density:
				return  # cancelled, or invalid input that promptDensity() reported
	
	# FreeCAD reported volume is always mm³
	# density is always g/cm³
	volume /= 1000
	
	mass = volume * density
	mass = mass * float(estimateSettings.get("weightUnitFactor"))

	msg = LANG.chunk("resultNeedsMaterialOf", {":amount" : f"{roundup(mass)} {estimateSettings.get('weightUnit')}", ":material": material if material else ""})
	if estimateSettings.get("reportOutput") == "console":
		report(msg)
	elif estimateSettings.get("reportOutput") == "popup":
		msgbox(LANG.chunk("resultWeightPopTitle"), msg, f"{roundup(mass)}")
