# BSD 2-Clause License
#
# Copyright (c) 2022, Social Cognition in Human-Robot Interaction,
#                     Istituto Italiano di Tecnologia, Genova
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from pyicub.utils import importFromJSONFile, exportJSONFile
from pyicub.controllers.position import JointPose, iCubPart, DEFAULT_TIMEOUT

import importlib
import inspect
import json

class JointsTrajectoryCheckpoint:

    def __init__(self, pose: JointPose, duration: float=0.0, timeout: float=DEFAULT_TIMEOUT, joints_speed=[]):
        self.pose = pose
        self.duration = duration
        self.timeout = timeout
        self.joints_speed = joints_speed

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)


class LimbMotion:
    def __init__(self, part: iCubPart):
        self.part = part
        self.checkpoints = []

    def createJointsTrajectory(self, pose: JointPose, duration: float=0.0, timeout: float=DEFAULT_TIMEOUT, joints_speed=[]):
        if not pose.joints_list:
            pose.joints_list = self.part.joints_list
        if not joints_speed:
            joints_speed = self.part.joints_speed
        checkpoint = JointsTrajectoryCheckpoint(pose=pose, duration=duration, timeout=timeout, joints_speed=joints_speed)
        self.checkpoints.append(checkpoint)
        return checkpoint

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)

class PyiCubCustomCall:

    def __init__(self, target, args=()):
        self.target = target
        self.args = args

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)

class GazeMotion:
    def __init__(self, lookat_method: str):
        self.checkpoints = []
        self.lookat_method = lookat_method

    def addCheckpoint(self, value: list):
        self.checkpoints.append(value)

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)

class iCubFullbodyStep:

    def __init__(self, offset_ms=None, name=None, JSON_dict=None, JSON_file=None):
        if not name:
            self.name = self.__class__.__name__
        self.limb_motions = {}
        self.gaze_motion = None
        self.custom_calls = []
        self.offset_ms = offset_ms
        if JSON_dict or JSON_file:
            if JSON_dict:
                self.importFromJSONDict(JSON_dict)
            else:
                self.importFromJSONFile(JSON_file)
        else:
            self.prepare()

    def prepare(self):
        raise NotImplementedError("The method 'prepare' contains definition for creating custom iCubFullbodyStep.")

    def createCustomCall(self, target, args=()):
        cc = PyiCubCustomCall(target=target, args=args)
        self.setCustomCall(cc)
        return cc

    def createGazeMotion(self, lookat_method: str):
        gm = GazeMotion(lookat_method)
        self.setGazeMotion(gm)
        return gm
    
    def createPart(self, name, robot_part, joints_nr, joints_list, joints_speed):
        return iCubPart(name, robot_part, joints_nr, joints_list, joints_speed)

    def createLimbMotion(self, part: iCubPart):
        lm = LimbMotion(part)
        self.setLimbMotion(lm)
        return lm

    def exportJSONFile(self, filepath):
        exportJSONFile(filepath, self.toJSON())

    def importFromJSONDict(self, json_dict):
        self.name = json_dict["name"]
        self.offset_ms = json_dict["offset_ms"]
        for part,pose in json_dict["limb_motions"].items():
            part = self.createPart(pose["part"]["name"], pose["part"]["robot_part"], pose["part"]["joints_nr"], pose["part"]["joints_list"], pose["part"]["joints_speed"])
            lm = self.createLimbMotion(part)
            for v in pose["checkpoints"]:
                pose = JointPose(target_joints=v['pose']['target_joints'], joints_list=v['pose']['joints_list'])
                lm.createJointsTrajectory(pose, duration=v['duration'], timeout=v['timeout'], joints_speed=v["joints_speed"])
        if json_dict["gaze_motion"]:
            gaze = self.createGazeMotion(lookat_method=json_dict["gaze_motion"]["lookat_method"])
            for v in json_dict["gaze_motion"]["checkpoints"]:
                gaze.addCheckpoint(v)
        if json_dict["custom_calls"]:
            for v in json_dict["custom_calls"]:
                self.createCustomCall(target=v["target"], args=v["args"])

    def importFromJSONFile(self, JSON_file):
        JSON_dict = importFromJSONFile(JSON_file)
        self.importFromJSONDict(JSON_dict)


    def join(self, step):
        for k,v in step.limb_motions.items():
            if k in self.limb_motions.keys():
                raise Exception("Cannot join current step because part %s is already present." % k)
            else:
                self.limb_motions[k] = v
        if step.custom_calls:
            self.custom_calls.extend(step.custom_calls)
        if step.gaze_motion:
            self.gaze_motion = step.gaze_motion
    
    def setLimbMotion(self, limb_motion: LimbMotion):
        self.limb_motions[limb_motion.part.name] = limb_motion

    def setCustomCall(self, custom_call: PyiCubCustomCall):
        self.custom_calls.append(custom_call)

    def setGazeMotion(self, gaze_motion: GazeMotion):
        self.gaze_motion = gaze_motion

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)


class iCubFullbodyAction:

    def __init__(self, description='empty', name=None, offset_ms=None, JSON_dict=None, JSON_file=None):
        self.steps = []
        self.wait_for_steps = []
        if not name:
            self.name = self.__class__.__name__
        else:
            self.name = name
        self.description = description
        self.offset_ms = offset_ms
        if JSON_dict or JSON_file:
            if JSON_dict:
                self.importFromJSONDict(JSON_dict)
            else:
                self.importFromJSONFile(JSON_file)
        else:
            self.prepare()

    def prepare(self):
        raise NotImplementedError("The method 'prepare' contains definition for creating custom actions.")

    def addAction(self, action):
        self.steps.extend(action.steps)
        self.wait_for_steps.extend(action.wait_for_steps)

    def addStep(self, step: iCubFullbodyStep, wait_for_completed: bool=True):
        self.steps.append(step)
        self.wait_for_steps.append(wait_for_completed)

    def importFromJSONDict(self, json_dict):
        self.name = json_dict["name"]
        self.offset_ms = json_dict["offset_ms"]
        self.description = json_dict["description"]
        steps = json_dict["steps"]
        for i in range(0, len(steps)):
            res = iCubFullbodyStep(JSON_dict=steps[i])
            self.addStep(res, json_dict["wait_for_steps"][i])

    def importFromJSONFile(self, JSON_file):
        JSON_dict = importFromJSONFile(JSON_file)
        self.importFromJSONDict(JSON_dict)

    def exportJSONFile(self, filepath):
        exportJSONFile(filepath, self.toJSON())

    def setName(self, name):
        self.name = name

    def setDescription(self, description):
        self.description = description

    def setOffset(self, offset_ms):
        self.offset_ms = offset_ms

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)


class TemplateParameter:

    def __init__(self, name: str, value: object):
        self._param_ = {}
        self._name_ = name
        self._param_[name] = value
    
    def value(self):
        return self._param_

    def name(self):
        return self._name_

    def exportJSONFile(self, filepath):
        exportJSONFile(filepath, self.toJSON() )

    def toJSON(self):
        #return self._param_
        return json.dumps(self._param_, default=lambda o: o.__dict__, indent=4)

class iCubActionTemplate(iCubFullbodyAction):

    def __init__(self, name='TemplateAction', description='empty', offset_ms=None):
        self.name = name
        self.params = {}
        self.prepare_params()
        iCubFullbodyAction.__init__(self, description=description, name=name, offset_ms=offset_ms)

    def __replace_params__(self, template_dict, params_dict):
        if isinstance(template_dict, dict):
            for key, value in template_dict.items():
                template_dict[key] = self.__replace_params__(value, params_dict)
        elif isinstance(template_dict, list):
            for i, item in enumerate(template_dict):
                template_dict[i] = self.__replace_params__(item, params_dict)
        elif isinstance(template_dict, str) and template_dict.startswith('$'):
            param_key = template_dict[1:]  # Remove the '$' character
            if param_key in params_dict:
                return params_dict[param_key]
        return template_dict

    def prepare_params(self):
        raise NotImplementedError("The method 'prepare_params' contains definition for creating custom actions.")
            
    def createParam(self, name):
        self.params[name] = '$' + name

    def getActionDict(self):
        return self.__replace_params__(json.loads(self.toJSON()), self.params)

    def getAction(self, action_name=None):
        action_dict = self.getActionDict()
        action = iCubFullbodyAction(JSON_dict=action_dict)
        if not action_name:
            action_name = self.name    
        action.setName(action_name)
        return action

    def getParams(self):
        return self.params

    def getParam(self, name):
        return self.params[name]
    
    def setParams(self, params):
        for param in params:
            self.setParam(param.name, param.value)

    def setParam(self, name, value):
        if name in self.params.keys():
            self.params[name] = value
        else:
            raise Exception("The key %s is not present among the parameter names" % name)



class iCubActionTemplateImportedJSON(iCubActionTemplate):

    def __init__(self, JSON_dict):
        self._json_dict_ = JSON_dict
        self.name = JSON_dict['name']
        iCubActionTemplate.__init__(self, description=JSON_dict["description"], name=JSON_dict["name"], offset_ms=JSON_dict["offset_ms"])

    def getActionDict(self):
        return self.__replace_params__(self._json_dict_, self.params)
    
    def prepare_params(self):
        for k in self._json_dict_['params'].keys():
            self.createParam(name=k)

    def prepare(self):
        pass

    def setParam(self, JSON_file):
        value = importFromJSONFile(JSON_file)
        name = list(value.keys())[0]
        value = value[name]
        self.params[name] = value


class ActionsManager:

    def __init__(self):
        self.__actions__ = {}

    def __get_subclasses__(self, module, base_class):
        subclasses = []
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, base_class) and obj != base_class:
                subclasses.append(obj)
        return subclasses

    def __instantiate_actions__(self, module):
        try:
            module = importlib.import_module(module)
            clsmembers = self.__get_subclasses__(module, iCubFullbodyAction)
            actions = []

            for class_ in clsmembers:
                actions.append( class_() )
            
            return actions

        except (ImportError, AttributeError) as e:
            print(f"Error: {e}")
            print(f"Could not import or instantiate classes for module: {module}")
    
        return None

    def addAction(self, action: iCubFullbodyAction, action_id=None):
        if not action_id:
            action_id = action.name
        if action_id in self.__actions__.keys():
            raise Exception("An error occurred adding a new action! Class name '%s' already present! Please choose different names for each class actions." % action_id)
        self.__actions__[action_id] = action
        return action_id
    
    def deleteAction(self, action_id: str):
        if action_id in self.__actions__.keys():
            del self.__actions__[action_id]
        else:
            raise Exception("action_id '%s' not found! Please provide an action identifier previously imported!" % action_id)
        
    def flushActions(self, name_prefix=None):
        if name_prefix:
            keys_to_delete = [k for k in self.__actions__.keys() if k.startswith(name_prefix)]
            for k in keys_to_delete:
                del self.__actions__[k]
        else:
            self.__actions__.clear()

    def importActionsFromModule(self, module):
        actions = self.__instantiate_actions__(module)
        for action in actions:
            self.addAction(action)

    def getAction(self, action_id: str):
        if action_id in self.__actions__.keys():
            return self.__actions__[action_id]
        raise Exception("action_id '%s' not found! Please provide an action identifier previously imported!" % action_id)

    def getActions(self):
        return self.__actions__.keys()

    def exportActions(self, path):
        for k, action in self.__actions__.items():
            action.exportJSONFile('%s/%s.json' % (path, k))
   
    def importTemplateFromJSONFile(self, JSON_file):
        JSON_dict = importFromJSONFile(JSON_file)
        return self.importTemplateFromJSONDict(JSON_dict=JSON_dict)

    def importTemplateFromJSONDict(self, JSON_dict):
        return iCubActionTemplateImportedJSON(JSON_dict=JSON_dict)

    def importTemplateJSONFile(self, JSON_file):
        return importFromJSONFile(JSON_file)

