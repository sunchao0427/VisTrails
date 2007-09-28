"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup
import sys

VERSION = '1.0b.954'
plist = dict(
    CFBundleName='VisTrails',
    CFBundleShortVersionString=VERSION,
    CFBundleGetInfoString=' '.join(['VisTrails', VERSION]),
    CFBundleExecutable='vistrails',
    CFBundleIdentifier='edu.utah.sci.vistrails',
)

sys.path.append('../../vistrails')
APP = ['../../vistrails/vistrails.py']
#comma-separated list of additional data files and
#folders to include (not for code!)
#DATA_FILES = ['/usr/local/graphviz-2.12/bin/dot',]
OPTIONS = {'argv_emulation': True,
           'iconfile': 'resources/vistrails_icon_small.icns',
           'includes': 'sip,pylab',
           'packages': 'PyQt4,vtk,SOAPpy,MySQLdb,matplotlib,packages,core,gui',
           'plist': plist,
           }

setup(
    app=APP,
 #   data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
