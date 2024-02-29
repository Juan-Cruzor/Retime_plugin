import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

import maya.cmds as cmds
import maya.mel as mel


def maya_useNewAPI():
    """
    The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.
    """
    pass

#MPxCommand allow us to access to its methods
class RetimingCmd(om.MPxCommand):

    COMMAND_NAME = "RetimingCmd"
    # MSyntax.kDouble to return the appropiate type of value
    VALUE_FLAG = ["-v", "-value", om.MSyntax.kDouble]
    INCREMENTAL_FLAG = ["-i", "-incremental"]


    def __init__(self):
        super(RetimingCmd, self).__init__()
        #Creating an instance of the animation curves that allows to access to the "doIt" and "unDoIt" methods
        self.anim_curve_change = oma.MAnimCurveChange()

        self.num_keys_updated = 0
        # Set and retrieve anim time values in the specified units
        self.max_time = om.MTime(9999999, om.MTime.uiUnit())

    def doIt(self, arg_list):
        try:
            arg_db = om.MArgDatabase(self.syntax(), arg_list)
        except:
            self.displayError("Error parsing arguments")
            raise

        if arg_db.isFlagSet(RetimingCmd.VALUE_FLAG[0]):
            value = om.MTime(arg_db.flagArgumentDouble(RetimingCmd.VALUE_FLAG[0], 0), om.MTime.uiUnit())
            incremental = arg_db.isFlagSet(RetimingCmd.INCREMENTAL_FLAG[0])
            selection_list = arg_db.getObjectList()

            self.do_retiming(selection_list, value, incremental)
            self.setResult(self.num_keys_updated)

        else:
            raise RuntimeError("A value (-v) must be passed to the commmand")

    def undoIt(self):
        self.anim_curve_change.undoIt()

    def redoIt(self):
        self.anim_curve_change.redoIt()

    def isUndoable(self):
        #The function should only be undoable if one or more keys were updated
        return self.num_keys_updated > 0


    def do_retiming(self, selection_list, retime_value, incremental):
        range_start_time, range_end_time = self.get_selected_range()

        anim_curves = self.get_anim_curves(selection_list)
        for anim_curve in anim_curves:
            key_data = self.calculate_retiming(anim_curve, range_start_time, range_end_time, retime_value, incremental)
           

            self.apply_retiming(anim_curve, key_data)

    def calculate_retiming(self, anim_curve_fn, range_start_time, range_end_time, retime_value, incremental):
        """
        Return a list of tuples containing all keys that will be retimed on an anim curve
        Tuple format is (key_index, updated_time, original_time)
        """
        num_keys = anim_curve_fn.numKeys
        if num_keys == 0:
            return []

        root_retime_key_index = self.find_closest_index(anim_curve_fn, range_start_time)
        if root_retime_key_index < 0:
            return []

        last_retime_key_index = self.find_closest_index(anim_curve_fn, range_end_time)

        root_retime_key_time = anim_curve_fn.input(root_retime_key_index)
        key_data = [(root_retime_key_index, root_retime_key_time, root_retime_key_time)]

        current_time = root_retime_key_time
        time_diff = om.MTime(0, om.MTime.uiUnit())
        one_frame = om.MTime(1, om.MTime.uiUnit())

        for index in range(root_retime_key_index + 1, num_keys):
            next_keyframe_time = anim_curve_fn.input(index)

            if incremental:
                time_diff = next_keyframe_time - current_time
                if index <= last_retime_key_index + 1:
                    time_diff += retime_value
                    if time_diff < one_frame:
                        time_diff = one_frame
            else:
                if index <= last_retime_key_index + 1:
                    time_diff = retime_value
                else:
                    time_diff = next_keyframe_time - current_time

            new_time = key_data[-1][1] + time_diff
            key_data.append((index, new_time, next_keyframe_time))

            current_time = next_keyframe_time

        next_index = key_data[-1][0] + 1
        key_data.append((next_index, self.max_time, self.max_time))

        return key_data


    def apply_retiming(self, anim_curve_fn, key_data):
        '''
        The indices of keys on an anim curve are ordered by the time and must remain in the correct order
        when updating the time. The time cannot be changed in a way that will invalidate the order of the indicies.
        This means the new time must always be greater than the time of the key at the previous index and
        less than the time of the key at the next index.

        Recursion is used to adjust the time on each key in an order that ensures this is always the case.
        '''
        self.apply_retiming_recursive(anim_curve_fn, 0, key_data)

    def apply_retiming_recursive(self, anim_curve_fn, index, key_data):
        '''
        Tuple format for each entry in key_data is (key_index, updated_time, original_time)
        '''
        if index >= len(key_data) - 1:
            return

        key_index = key_data[index][0]
        updated_time = key_data[index][1]
        orig_time = key_data[index][2]

        next_key_orig_time = key_data[index + 1][2]

        if updated_time < next_key_orig_time:
            self.update_time(anim_curve_fn, key_index, updated_time)
            self.apply_retiming_recursive(anim_curve_fn, index + 1, key_data)
        else:
            self.apply_retiming_recursive(anim_curve_fn, index + 1, key_data)
            self.update_time(anim_curve_fn, key_index, updated_time)

    def update_time(self, anim_curve_fn, index, updated_time):
        if anim_curve_fn.input(index) != updated_time:
            anim_curve_fn.setInput(index, updated_time, self.anim_curve_change)
            self.num_keys_updated += 1

    def find_closest_index(self, anim_curve_fn, target_time):
        """
        Find the closest index without going past the target time
        """
        index = anim_curve_fn.findClosest(target_time)
        closest_time = anim_curve_fn.input(index)
        if closest_time > target_time:
            index -= 1

        return index

    def get_anim_curves(self, selection_list):
        """
            Args:
                selection_list[List]
        """
        anim_curves = []

        sel_iter = om.MItSelectionList(selection_list)
        while not sel_iter.isDone():
            obj = sel_iter.getDependNode()
            depend_fn = om.MFnDependencyNode(obj)

            self.get_anim_curves_from_connections(depend_fn, anim_curves)

            sel_iter.next()

        return anim_curves

    def get_anim_curves_from_connections(self, depend_fn, anim_curves):
        plugs = depend_fn.getConnections()
        for plug in plugs:
            if plug.isKeyable and not plug.isLocked:
                dg_iter = om.MItDependencyGraph(plug, om.MFn.kAnimCurve, om.MItDependencyGraph.kUpstream, om.MItDependencyGraph.kBreadthFirst, om.MItDependencyGraph.kNodeLevel)

                while not dg_iter.isDone():
                    if len(dg_iter.getNodePath()) > 2:
                        break

                    anim_curve_fn = oma.MFnAnimCurve(dg_iter.currentNode())
                    anim_curves.append(anim_curve_fn)

                    dg_iter.next()

    def get_selected_range(self):
        playback_slider = mel.eval("$tempVar = $gPlayBackSlider")
        start_frame, end_frame = cmds.timeControl(playback_slider, q=True, rangeArray=True)
        end_frame -= 1

        start_time = om.MTime(start_frame, om.MTime.uiUnit())
        end_time = om.MTime(end_frame, om.MTime.uiUnit())

        return [start_time, end_time]


    @classmethod
    def creator(cls):
        return RetimingCmd()

    @classmethod
    def create_syntax(cls):
        # It allows us to specify the arguments and flags that are passed to the command
        syntax = om.MSyntax()
        # Specifies the type of arguments for both the incremental parameter and the value
        syntax.addFlag(*cls.VALUE_FLAG)
        syntax.addFlag(*cls.INCREMENTAL_FLAG)

        syntax.setObjectType(om.MSyntax.kSelectionList, 1)
        syntax.useSelectionAsDefault(True)

        return syntax


def initializePlugin(plugin):
    """
    """
    vendor = "Juan Cruz"
    version = "2.0.0"

    plugin_fn = om.MFnPlugin(plugin, vendor, version)
    try:
        plugin_fn.registerCommand(RetimingCmd.COMMAND_NAME, RetimingCmd.creator, RetimingCmd.create_syntax)
    except:
        om.MGlobal.displayError("Failed to register command: {0}".format(RetimingCmd.COMMAND_NAME))


def uninitializePlugin(plugin):
    """
    """
    plugin_fn = om.MFnPlugin(plugin)
    try:
        plugin_fn.deregisterCommand(RetimingCmd.COMMAND_NAME)
    except:
        om.MGlobal.displayError("Failed to deregister command: {0}".format(RetimingCmd.COMMAND_NAME))


if __name__ == "__main__":

    cmds.file(new=True, force=True)

    plugin_name = "retiming_cmd.py"
    cmds.evalDeferred('if cmds.pluginInfo("{0}", q=True, loaded=True): cmds.unloadPlugin("{0}")'.format(plugin_name))
    cmds.evalDeferred('if not cmds.pluginInfo("{0}", q=True, loaded=True): cmds.loadPlugin("{0}")'.format(plugin_name))
    #Creates a polycube with some keyframes
    cmds.evalDeferred('cmds.polyCube(); cmds.setKeyframe(); cmds.currentTime(2); cmds.setKeyframe(); cmds.currentTime(3); cmds.setKeyframe(); cmds.currentTime(4); cmds.setKeyframe()')
