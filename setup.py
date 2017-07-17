#coding: utf-8
import os
from distutils.core import setup
import py2exe # Patching distutils setup
import matplotlib


print "Removing Trash"
os.system("rmdir /s /q build")

# delete the old build drive
os.system("rmdir /s /q dist")

DLL_EXCLUDES = ["MSVCP90.dll", "MSVCM90.DLL", "MSVCR90.DLL", "HID.DLL",
    "w9xpopen.exe", 'libifcoremd.dll']

# modules to exclude
EXCLUDES = ['IPython', 'Image', 'PIL', 'Tkconstants', 'Tkinter', '_hashlib',
    '_imaging', '_ssl', '_ssl', 'bz2', 'compiler', 'cookielib', 'cookielib',
    'doctest', 'email', 'nose', 'optparse', 'pdb', 'pydoc', 'pywin', 'readline',
    'tcl', 'tornado', 'zipfile', 'zmq']

# exclude unused matplotlib backends
EXCLUDES += ['_gtkagg', '_tkagg']

# Including/excluding DLLs and Python modules
INCLUDES = []

# data files
DATA_FILES = matplotlib.get_py2exe_datafiles()
DATA_FILES += [('.', ['sigtools.pyd', "genvelope.conf"])]


setup(
    options={
        "py2exe":{
            "dll_excludes": DLL_EXCLUDES,
            "compressed": 2, # compress the library archive
            "optimize": 2,
            "excludes": EXCLUDES,
        }
    },
    console=[{'script': 'genvelope.pyw'}],
    data_files = DATA_FILES,
)

"""
setup(
    options={
        "py2exe": {
            "compressed": 2,
            "optimize": 2,
            'bundle_files': 1,
            "includes": INCLUDES,
            "excludes": EXCLUDES,
            "dll_excludes": DLL_EXCLUDES,
            "dist_dir": "dist",
        },
    },
    data_files=DATA_FILES,
    windows=[{
        "script": "genvelope.py",
        "dest_base": "Genvelope",
        "version": "0.0.1",
        "company_name": u"GIN SB RAS",
        "copyright": u"Petr Predein",
        "name": "Genvelope",
        "description": "Genvelope",
    },],
    zipfile = None,
    )
"""
