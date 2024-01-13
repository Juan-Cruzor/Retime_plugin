from PySide2 import QtCore
from PySide2 import QtWidgets
from shiboken2 import wrapInstance

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui


class RetimingUi(QtWidgets.QDialog):

    WINDOW_TITLE = "Retiming UI"

    ABSOLUTE_BUTTON_WIDTH = 50
    RELATIVE_BUTTON_WIDTH = 64

    RETIMING_PROPERTY_NAME = "retiming_data"

    dlg_instance = None


    @classmethod
    def display(cls):
        if not cls.dlg_instance:
            cls.dlg_instance = RetimingUi()

        if cls.dlg_instance.isHidden():
            cls.dlg_instance.show()
        else:
            cls.dlg_instance.raise_()
            cls.dlg_instance.activateWindow()

    @classmethod
    def maya_main_window(cls):
        """
        Return the Maya main window widget as a Python object
        """
        main_window_ptr = omui.MQtUtil.mainWindow()
        if sys.version_info.major >= 3:
            return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
        else:
            return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)

    def __init__(self):
        super(RetimingUi, self).__init__(self.maya_main_window())

        self.setWindowTitle(self.WINDOW_TITLE)
        if cmds.about(ntOS=True):
            self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        self.absolute_buttons = []
        for i in range(1, 7):
            btn = QtWidgets.QPushButton("{0}f".format(i))
            btn.setFixedWidth(self.ABSOLUTE_BUTTON_WIDTH)
            btn.setProperty(self.RETIMING_PROPERTY_NAME, [i, False])
            self.absolute_buttons.append(btn)

        self.relative_buttons = []
        for i in [-2, -1, 1, 2]:
            btn = QtWidgets.QPushButton("{0}f".format(i))
            btn.setFixedWidth(self.RELATIVE_BUTTON_WIDTH)
            btn.setProperty(self.RETIMING_PROPERTY_NAME, [i, True])
            self.relative_buttons.append(btn)

    def create_layouts(self):
        absolute_retime_layout = QtWidgets.QHBoxLayout()
        absolute_retime_layout.setSpacing(2)
        for btn in self.absolute_buttons:
            absolute_retime_layout.addWidget(btn)

        relative_retime_layout = QtWidgets.QHBoxLayout()
        relative_retime_layout.setSpacing(2)
        for btn in self.relative_buttons:
            relative_retime_layout.addWidget(btn)
            if relative_retime_layout.count() == 2:
                relative_retime_layout.addStretch()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        main_layout.addLayout(absolute_retime_layout)
        main_layout.addLayout(relative_retime_layout)

    def create_connections(self):
        for btn in self.absolute_buttons:
            btn.clicked.connect(self.retime)

        for btn in self.relative_buttons:
            btn.clicked.connect(self.retime)

    def retime(self):
        btn = self.sender()
        if btn:
            retiming_data = btn.property(self.RETIMING_PROPERTY_NAME)

            cmds.RetimingCmd(v=retiming_data[0], i=retiming_data[1])


if __name__ == "__main__":

    try:
        retiming_ui.close() # pylint: disable=E0601
        retiming_ui.deleteLater()
    except:
        pass

    retiming_ui = RetimingUi()
    retiming_ui.show()
