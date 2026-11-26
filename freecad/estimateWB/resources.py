from pathlib import Path
import json
import FreeCAD

# plain paths next to this file rather than importlib.resources.files(), which needs Python 3.9
# while older FreeCAD versions ship 3.8. the workbench is always installed as a regular folder
resourcefiles = Path(__file__).parent / "resources"
languagefiles = Path(__file__).parent / "languages"


def icon(name: str):
	"""	returns an icon file path """
	file = name + ".svg"
	return str(resourcefiles / file)


with open(resourcefiles / "materials.json", "r", encoding="utf-8") as jsonfile:
	""" the built-in material list with names and densities in g/cm³ """
	baseMaterials = json.loads(jsonfile.read().replace("\n", ""))

# user added materials are stored as a json object {name: density} in the workbench preferences
PARAMS = "User parameter:BaseApp/Preferences/Mod/estimateWB"

def getUserMaterials():
	""" returns the user added materials as {name: density in g/cm³} """
	try:
		user = json.loads(FreeCAD.ParamGet(PARAMS).GetString("userMaterials") or "{}")
		return {str(name): float(density) for name, density in user.items() if float(density) > 0}
	except (ValueError, TypeError, AttributeError):
		return {}

def setUserMaterials(user: dict):
	""" stores the user added materials and updates the material list """
	FreeCAD.ParamGet(PARAMS).SetString("userMaterials", json.dumps(user))
	reloadMaterials()

def reloadMaterials():
	"""
		rebuilds the material list in place (other modules hold a reference to it):
		built-in materials first, then user materials, which override built-ins of the same name
	"""
	materials.clear()
	materials.update(baseMaterials)
	materials.update(getUserMaterials())

materials = {}
reloadMaterials()


class language:
	def __init__(self):
		# try to open the language file according to FreeCAD settings, default to english
		try:
			language = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General").GetString("Language")
			with open(languagefiles / f"{language}.json", "r", encoding="utf-8") as jsonfile:
				self.language = json.loads(jsonfile.read().replace("\n", ""))
		except:
			with open(languagefiles / "English.json", "r", encoding="utf-8") as jsonfile:
				self.language = json.loads(jsonfile.read().replace("\n", ""))
	

	def chunk(self, chunk:str, replacements:dict = {}):
		"""
			returns the requested language chunk from the loaded language file
			a passed dict replaces found keys with the corresponding value
		"""
		chunk = self.language.get(chunk)
		if chunk and len(replacements):
			# replace found dict keys with their value
			for find, replace in replacements.items():
				chunk = chunk.replace(find, replace);
		return chunk

LANG = language()
