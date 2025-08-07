import os
import FreeCADGui
from . import ICONPATH, tools


class Estimate_By_Material:
    def GetResources(self):
        return {
            'Pixmap': os.path.join(ICONPATH, "MATERIAL_SELECTION.svg"),  # Use your preferred icon
            'MenuText': "Estimate Weight by Material",
            'ToolTip': "Choose a material to estimate the weight",
        }

    def Activated(self):
        from PySide import QtGui
        materials = tools.materials
        material, ok = QtGui.QInputDialog.getItem(
            None,
            "Select Material",
            "Material:",
            materials,
            0,
            False
        )
        if ok and material:
            FreeCADGui.runCommand(f"Estimate_{material}_Weight")

    def IsActive(self):
        return True


class estimateWB(FreeCADGui.Workbench):
    MenuText = "Estimate"
    ToolTip = tools.LANG.chunk("wbToolTip")[0]  # "Display a body's volume or weight to estimate costs of printing"
    Icon = os.path.join(ICONPATH, "icon.svg")

    def Initialize(self):
        """This function is executed when FreeCAD starts"""
        from . import commands

        # --- Scale Tools ---
        scale_units = ['mm', 'cm', 'm']
        scale_cmds = [f"Scale_q{u}" for u in scale_units]
        self.appendToolbar("Scale", scale_cmds)
        self.appendMenu("Scale", scale_cmds)
        for u in scale_units:
            FreeCADGui.addCommand(f"Scale_q{u}", commands.Set_Scale(u))

        # --- Estimate Tools ---
        estimate_cmds = ["Estimate_Volume", "Estimate_Weight_Custom", "Estimate_By_Material"]
        self.appendToolbar("Estimate", estimate_cmds)
        self.appendMenu("Estimate", estimate_cmds)
        FreeCADGui.addCommand("Estimate_Volume", commands.Estimate_Volume())
        FreeCADGui.addCommand("Estimate_Weight_Custom", commands.Estimate_Weight_Custom())
        FreeCADGui.addCommand("Estimate_By_Material", Estimate_By_Material())

        # Register all material-specific commands (hidden, not in toolbar)
        for material in tools.materials:
            FreeCADGui.addCommand(f"Estimate_{material}_Weight", commands.Estimate_Weight(material))

        # --- Weight Units ---
        weight_units = ['g', 'kg', 'lb']
        weight_cmds = [f"Weight_{u}" for u in weight_units]
        self.appendToolbar("Weight Units", weight_cmds)
        self.appendMenu("Weight Units", weight_cmds)
        for u in weight_units:
            FreeCADGui.addCommand(f"Weight_{u}", commands.Set_Weight_Unit(u))

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        pass

    def GetClassName(self): 
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(estimateWB())
