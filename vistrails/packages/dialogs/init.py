###############################################################################
##
## Copyright (C) 2011-2014, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah. 
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without 
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice, 
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright 
##    notice, this list of conditions and the following disclaimer in the 
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the University of Utah nor the names of its 
##    contributors may be used to endorse or promote products derived from 
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################
from vistrails.core.modules.vistrails_module import Module, ModuleError
import vistrails.core.modules.basic_modules
import vistrails.core.modules.module_registry
from PyQt4 import QtGui

##############################################################################

class Dialog(Module):
    def __init__(self, *args, **kwargs):
        super(Dialog, self).__init__(*args, **kwargs)
        self.cacheable_dialog = False

    def is_cacheable(self):
        return self.cacheable_dialog

class TextDialog(Dialog):
    label = ''
    mode =  QtGui.QLineEdit.Normal

    def compute(self):
        if self.has_input('title'):
            title = self.get_input('title')
        else:
            title = 'VisTrails Dialog'
        if self.has_input('label'):
            label = self.get_input('label')
        else:
            label = self.label

        if self.has_input('default'):
            default = self.get_input('default')
        else:
            default = ''
            
        if self.has_input('cacheable') and self.get_input('cacheable'):
            self.cacheable_dialog = True
        else:
            self.cacheable_dialog = False

        (result, ok) = QtGui.QInputDialog.getText(None, title, label,
                                                  self.mode,
                                                  default)
        if not ok:
            raise ModuleError(self, "Canceled")
        self.set_output('result', str(result))


class PasswordDialog(TextDialog):
    label = 'Password'
    mode = QtGui.QLineEdit.Password


class YesNoDialog(Dialog):
    def compute(self):
        if self.hasInputFromPort('title'):
            title = self.getInputFromPort('title')
        else:
            title = 'VisTrails Dialog'
        if self.hasInputFromPort('label'):
            label = self.getInputFromPort('label')
        else:
            label = 'Yes/No?'

        if self.hasInputFromPort('cacheable') and self.getInputFromPort('cacheable'):
            self.cacheable_dialog = True
        else:
            self.cacheable_dialog = False

        result = QtGui.QMessageBox.question(
                None,
                title, label,
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        result = result == QtGui.QMessageBox.Yes

        self.setResult('result', result)


##############################################################################

def initialize(*args, **keywords):
    reg = vistrails.core.modules.module_registry.get_module_registry()
    basic = vistrails.core.modules.basic_modules

    reg.add_module(Dialog, abstract=True)
    reg.add_input_port(Dialog, "title", basic.String)
    reg.add_input_port(Dialog, "cacheable", basic.Boolean)

    reg.add_module(TextDialog)
    reg.add_input_port(TextDialog, "label", basic.String)
    reg.add_input_port(TextDialog, "default", basic.String)
    reg.add_output_port(TextDialog, "result", basic.String)

    reg.add_module(PasswordDialog)

    reg.add_module(YesNoDialog)
    reg.add_input_port(YesNoDialog, "label", basic.String)
    reg.add_output_port(YesNoDialog, "result", basic.Boolean)
