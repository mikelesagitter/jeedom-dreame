#!/usr/bin/env python3
# -*- coding: utf-8 -*-


__version__ = "3.0.0"

import asyncio
from collections.abc import Mapping
import datetime
import json
import logging
import socket
import time
import uuid
import paho.mqtt.client as mqtt

from .const import ERROR_CONNECTION_REFUSED, ERROR_NO_ROUTE_TO_HOST, ROBOT_PORT

from .utils import generate_tls_context
from .configs import iRobotConfig


class iRobot:
    '''
    This is a Class for iRobot WiFi connected Vacuum cleaners and mops

    Most of the underlying info was obtained from here:
    https://github.com/koalazak/dorita980 many thanks!
    '''

    VERSION = __version__ = "3.0"

    states = {"charge": "Charging",
              "new": "New Mission",
              "run": "Running",
              "resume": "Running",
              "hmMidMsn": "Docking",
              "recharge": "Recharging",
              "stuck": "Stuck",
              "hmUsrDock": "User Docking",
              "completed": "Mission Completed",
              "cancelled": "Cancelled",
              "stop": "Stopped",
              "pause": "Paused",
              "evac": "Emptying",
              "hmPostMsn": "Docking - End Mission",
              "chargingerror": "Base Unplugged",
              "":  None}

    # from various sources
    _ErrorMessages = {
        0: "None",
        1: "Left wheel off floor",
        2: "Main brushes stuck",
        3: "Right wheel off floor",
        4: "Left wheel stuck",
        5: "Right wheel stuck",
        6: "Stuck near a cliff",
        7: "Left wheel error",
        8: "Bin error",
        9: "Bumper stuck",
        10: "Right wheel error",
        11: "Bin error",
        12: "Cliff sensor issue",
        13: "Both wheels off floor",
        14: "Bin missing",
        15: "Reboot required",
        16: "Bumped unexpectedly",
        17: "Path blocked",
        18: "Docking issue",
        19: "Undocking issue",
        20: "Docking issue",
        21: "Navigation problem",
        22: "Navigation problem",
        23: "Battery issue",
        24: "Navigation problem",
        25: "Reboot required",
        26: "Vacuum problem",
        27: "Vacuum problem",
        28: "Error",
        29: "Software update needed",
        30: "Vacuum problem",
        31: "Reboot required",
        32: "Smart map problem",
        33: "Path blocked",
        34: "Reboot required",
        35: "Unrecognised cleaning pad",
        36: "Bin full",
        37: "Tank needed refilling",
        38: "Vacuum problem",
        39: "Reboot required",
        40: "Navigation problem",
        41: "Timed out",
        42: "Localization problem",
        43: "Navigation problem",
        44: "Pump issue",
        45: "Lid open",
        46: "Low battery",
        47: "Reboot required",
        48: "Path blocked",
        52: "Pad required attention",
        53: "Software update required",
        54: "Blades stuck",
        55: "Left blades stuck",
        56: "Right blades stuck",
        57: "Cutting deck stuck",
        58: "Navigation problem",
        59: "Tilt detected",
        60: "Rolled over",
        62: "Stop button pushed",
        63: "Hardware error",
        65: "Hardware problem detected",
        66: "Low memory",
        67: "Handle lifted",
        68: "Dead camera",
        69: "Navigation problem",
        70: "Problem sensing beacons",
        73: "Pad type changed",
        74: "Max area reached",
        75: "Navigation problem",
        76: "Hardware problem detected",
        78: "Left wheel error",
        79: "Right wheel error",
        85: "Path to charging station blocked",
        86: "Path to charging station blocked",
        88: "Back-up refused",
        89: "Mission runtime too long",
        91: "Workspace path error",
        92: "Workspace path error",
        93: "Workspace path error",
        94: "Wheel motor over temp",
        95: "Wheel motor under temp",
        96: "Blade motor over temp",
        97: "Blade motor under temp",
        98: "Software error",
        99: "Navigation problem",
        101: "Battery isn't connected",
        102: "Charging error",
        103: "Charging error",
        104: "No charge current",
        105: "Charging current too low",
        106: "Battery too warm",
        107: "Battery temperature incorrect",
        108: "Battery communication failure",
        109: "Battery error",
        110: "Battery cell imbalance",
        111: "Battery communication failure",
        112: "Invalid charging load",
        114: "Internal battery failure",
        115: "Cell failure during charging",
        116: "Charging error of Home Base",
        118: "Battery communication failure",
        119: "Charging timeout",
        120: "Battery not initialized",
        121: "Clean the charging contacts",
        122: "Charging system error",
        123: "Battery not initialized",
        216: "Charging base bag full",
        1000: "Left edge-sweeping brush stuck",
        1001: "Right edge-sweeping brush stuck",
        1002: "Cleaning unavailable. Check subscription status.",
        1003: "Dead vision board",
        1004: "Map was unavailable",
        1007: "Contact customer care",
        1008: "Cleaning arm is stuck",
        1009: "Robot stalled",
    }

    def __init__(self, config: iRobotConfig):
        '''
        Initialize the iRobot object
        '''
        self._loop = asyncio.get_running_loop()
        self._debug = False
        self._logger = logging.getLogger()
        if self._logger.getEffectiveLevel() == logging.DEBUG:
            self._debug = True

        if not all([config.name, config.ip, config.blid, config.password]):
            missing_params = []
            if not config.name:
                missing_params.append("name")
            if not config.ip:
                missing_params.append("ip")
            if not config.blid:
                missing_params.append("blid")
            if not config.password:
                missing_params.append("password")
            raise ValueError(f"Missing parameter(s): {', '.join(missing_params)}. Could not configure iRobot")

        self._config = config
        self.port = ROBOT_PORT
        self.__local_mqtt_client = None
        self.__local_mqtt = False
        self.__connected = False
        self.__try_to_connect = True
        self.raw = False
        self.mapSize = None
        self.current_state = None
        self.master_state = {}
        self.update_seconds = 300  # update with all values every 5 minutes
        self.__robot_mqtt_client = None
        self.history = {}
        self.timers = {}
        self.flags = {}
        self.max_sqft = None
        self.cb = None

        self.__is_connected = asyncio.Event()
        self.__robot_msg_queue: asyncio.Queue[mqtt.MQTTMessage] = asyncio.Queue()
        self.__command_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._loop.create_task(self.__process_robot_msg_queue())
        self._loop.create_task(self.__process_command_queue())
        self._loop.create_task(self.__periodic_update())

    @property
    def name(self):
        return self._config.name

    @property
    def ip(self):
        return self._config.ip

    async def event_wait(self, evt, timeout):
        '''
        Event.wait() with timeout
        '''
        try:
            await asyncio.wait_for(evt.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        return evt.is_set()

    async def setup_client(self):
        if self.__robot_mqtt_client is None:
            self.__robot_mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self._config.blid,
                clean_session=True,
                protocol=mqtt.MQTTv311)
            # Assign event callbacks
            self.__robot_mqtt_client.on_message = self.on_robot_mqtt_message
            self.__robot_mqtt_client.on_connect = self.on_robot_mqtt_connect
            self.__robot_mqtt_client.on_subscribe = self.on_robot_mqtt_subscribe
            self.__robot_mqtt_client.on_disconnect = self.on_robot_mqtt_disconnect

            self._logger.info("Setting TLS")
            try:
                ssl_context = generate_tls_context()
                self.__robot_mqtt_client.tls_set_context(ssl_context)
                self.__robot_mqtt_client.tls_insecure_set(True)
            except Exception as e:
                self._logger.exception("Error setting TLS: %s", e)

            # disables peer verification
            self.__robot_mqtt_client.username_pw_set(self._config.blid, self._config.password)
            self._logger.info("Setting TLS - OK")
            return True
        return False

    def connect(self):
        '''
        just create async_connect task
        '''
        return self._loop.create_task(self.async_connect())

    async def async_connect(self):
        '''
        Connect to iRobot MQTT server
        '''
        count = 0
        max_retries = 3
        retry_timeout = 1
        while not self.__connected and self.__try_to_connect:
            try:
                if self.__robot_mqtt_client is None:
                    self._logger.info("Try to connect to %s with ip %s", self._config.name, self._config.ip)
                    await self.setup_client()
                    await self._loop.run_in_executor(None, self.__robot_mqtt_client.connect, self._config.ip, self.port, 60)
                else:
                    self._logger.info("Attempting to Reconnect...")
                    self.__robot_mqtt_client.loop_stop()
                    await self._loop.run_in_executor(None, self.__robot_mqtt_client.reconnect)
                self.__robot_mqtt_client.loop_start()
                await self.event_wait(self.__is_connected, 1)  # wait for MQTT on_connect to fire (timeout 1 second)
            except (ConnectionRefusedError, OSError) as e:
                if e.errno == 111:  # errno.ECONNREFUSED
                    self._logger.error(ERROR_CONNECTION_REFUSED, self.name)
                elif e.errno == 113:  # errno.No Route to Host
                    self._logger.error(ERROR_NO_ROUTE_TO_HOST, self.ip)
                else:
                    self._logger.error("Connection Error: %s ", e)

                self._logger.debug("sleeping %is", retry_timeout)
                await asyncio.sleep(retry_timeout)
                retry_timeout = retry_timeout * 2
                self._logger.error("Attempting retry Connection# %i", count)

                count += 1
                if count >= max_retries:
                    retry_timeout = 60

            except asyncio.CancelledError:
                self._logger.error('Connection Cancelled')
                break
            except Exception as e:
                self._logger.exception(e)
                if count >= max_retries:
                    break

        if not self.__connected:
            self._logger.error("Unable to connect to %s", self._config.name)
        return self.__connected

    async def disconnect(self):
        if not self.__connected:
            return
        try:
            self.__robot_mqtt_client.disconnect()
            if self.__local_mqtt:
                self.__local_mqtt_client.loop_stop()
        except Exception as e:
            self._logger.warning("Some exception occured during mqtt disconnect: %s", e)

    def _set_connected(self, state: bool):
        self.__connected = state
        self.publish('status', 'Online' if self.__connected else f"Offline at {time.ctime()}")

    def on_robot_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._logger.info("%s connected", self.name)
            self._set_connected(True)
            self.__robot_mqtt_client.subscribe('#')
            self.__robot_mqtt_client.subscribe("$SYS/#")
        else:
            self._logger.error("Connected with result code %s", reason_code)
            self._logger.error("Please make sure your blid and password are correct for robot %s", self._config.name)
            self.__try_to_connect = False
            self._set_connected(False)
            self.__robot_mqtt_client.disconnect()
        self._loop.call_soon_threadsafe(self.__is_connected.set)

    def on_robot_mqtt_message(self, client, userdata, message: mqtt.MQTTMessage):
        asyncio.run_coroutine_threadsafe(self.__robot_msg_queue.put(message), self._loop)

    async def __process_robot_msg_queue(self):
        while True:
            try:
                if self.__robot_msg_queue.qsize() > 15:
                    self._logger.warning('Pending event queue size is: %i', self.__robot_msg_queue.qsize())
                msg = await self.__robot_msg_queue.get()

                if not self.__command_queue.empty():
                    self._logger.debug('Command waiting in queue, pausing processing')
                    await asyncio.sleep(0.1)

                json_data = self.decode_payload(msg.topic, msg.payload)
                self.dict_merge(self.master_state, json_data)

                self._logger.debug("Received data: %s, %s", msg.topic, msg.payload)

                if self.raw:
                    self.publish(msg.topic, msg.payload)
                else:
                    await self._loop.run_in_executor(None, self.decode_topics, json_data)

                self.__robot_msg_queue.task_done()
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(e)

    async def __process_command_queue(self):
        while True:
            try:
                value = await self.__command_queue.get()
                command = value.get('command')
                setting = value.get('setting')
                schedule = value.get('schedule')
                if command:
                    await self._loop.run_in_executor(None, self._send_command, command)
                if setting:
                    await self._loop.run_in_executor(None, self._set_preference, *setting)
                if schedule:
                    await self._loop.run_in_executor(None, self._set_cleanSchedule, schedule)
                self.__command_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(e)

    async def __periodic_update(self):
        while True:
            try:
                # default every 5 minutes
                await asyncio.sleep(self.update_seconds)
                if self.__connected:
                    self._logger.info("Publishing %s master_state", self.name)
                    await self._loop.run_in_executor(None, self.decode_topics, self.master_state)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(e)

    def on_robot_mqtt_subscribe(self, client, userdata, mid, reason_codes, properties):
        self._logger.debug("Subscribed: %s %s", mid, reason_codes)

    def on_robot_mqtt_disconnect(self, client, userdata, flags, reason_code, properties):
        self._loop.call_soon_threadsafe(self.__is_connected.clear)
        self._set_connected(False)
        if reason_code != 0:
            self._logger.warning("Unexpected disconnect from %s! - reconnecting", self.name)
        else:
            self._logger.info('%s disconnected', self.name)

    def set_mqtt_topic(self, topic, subscribe=False):
        if self._config.blid:
            topic = f"{topic}/{self._config.blid}{'/#' if subscribe else ''}"
        return topic

    def setup_mqtt_client(self, broker=None,
                          port=1883,
                          user=None,
                          passwd=None,
                          brokerFeedback='/irobot/feedback',
                          brokerCommand='/irobot/command',
                          brokerSetting='/irobot/setting'):
        # returns an awaitable future

        return self._loop.run_in_executor(None, self._setup_mqtt_client, broker,
                                          port, user, passwd,
                                          brokerFeedback, brokerCommand,
                                          brokerSetting)

    def _setup_mqtt_client(self, broker=None,
                           port=1883,
                           user=None,
                           passwd=None,
                           brokerFeedback='/irobot/feedback',
                           brokerCommand='/irobot/command',
                           brokerSetting='/irobot/setting'):
        '''
        setup local mqtt connection to broker for feedback,
        commands and settings
        '''
        try:
            self.brokerFeedback = self.set_mqtt_topic(brokerFeedback)
            self.brokerCommand = self.set_mqtt_topic(brokerCommand, True)
            self.brokerSetting = self.set_mqtt_topic(brokerSetting, True)

            # connect to broker
            self.__local_mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, f"iRobot-{uuid.uuid4().hex[:10]}")
            # Assign event callbacks
            self.__local_mqtt_client.on_message = self.broker_on_message
            self.__local_mqtt_client.on_connect = self.broker_on_connect
            self.__local_mqtt_client.on_disconnect = self.broker_on_disconnect
            if user and passwd:
                self.__local_mqtt_client.username_pw_set(user, passwd)
            self.__local_mqtt_client.connect(broker, port, 60)
            self.__local_mqtt_client.loop_start()
            self.__local_mqtt = True
        except socket.error:
            self._logger.error("Unable to connect to MQTT Broker")
            self.__local_mqtt_client = None
        return self.__local_mqtt_client

    def broker_on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties):
        self._logger.debug("Broker Connected with result code %s", reason_code)
        # subscribe to commands and settings messages
        if reason_code == 0:
            client.subscribe(self.brokerCommand)
            client.subscribe(self.brokerSetting)
            self._logger.info('subscribed to %s, %s', self.brokerCommand, self.brokerSetting)

    def broker_on_message(self, client, userdata, message: mqtt.MQTTMessage):
        # receive commands and settings from broker
        payload = message.payload.decode("utf-8")
        if "command" in message.topic:
            self._logger.info("Received COMMAND from broker: %s", payload)
            self.send_command(payload)
        elif "setting" in message.topic:
            self._logger.info("Received SETTING from broker: %s", payload)
            cmd = payload.split(None, 1)
            self.set_preference(cmd[0], cmd[1])
        else:
            self._logger.warning("Unknown topic: %s", message.topic)

    def broker_on_disconnect(self, client: mqtt.Client, userdata, flags, reason_code, properties):
        self._logger.debug("Broker disconnected")

    async def async_send_command(self, command):
        await self.__command_queue.put({'command': command})

    async def async_set_preference(self, preference, setting):
        await self.__command_queue.put({'setting': (preference, setting)})

    async def async_set_cleanSchedule(self, setting):
        await self.__command_queue.put({'schedule': setting})

    def send_command(self, command):
        asyncio.run_coroutine_threadsafe(self.__command_queue.put({'command': command}), self._loop)

    def set_preference(self, preference, setting):
        asyncio.run_coroutine_threadsafe(self.__command_queue.put({'setting': (preference, setting)}), self._loop)

    def set_cleanSchedule(self, setting):
        asyncio.run_coroutine_threadsafe(self.__command_queue.put({'schedule': setting}), self._loop)

    def _send_command(self, command):
        '''
        eg
        {"command": "reset", "initiator": "admin", "time": 1609950197}
        {"command": "find", "initiator": "rmtApp", "time": 1612462418, "robot_id": null, "select_all": null}}}}'
        '''
        self._logger.info("Processing COMMAND: %s", command)
        if isinstance(command, dict):
            Command = command
        else:
            Command = {}
            try:
                Command = json.loads(command)  # was command, object_pairs_hook=OrderedDict
            except json.decoder.JSONDecodeError:
                Command["command"] = command
        Command["time"] = self.totimestamp(datetime.datetime.now())
        Command["initiator"] = "localApp"
        myCommand = json.dumps(Command)
        self._logger.info("Sending Command: %s", myCommand)
        self.__robot_mqtt_client.publish("cmd", myCommand)

    def send_region_command(self, command):
        '''
        send region specific start command
        example command:
        "cmd": {
                    "command": "start",
                    "ordered": 1,
                    "pmap_id": "wpVy73n9R5GrVYtEPZJ5iA",
                    "regions": [
                        {
                            "region_id": "6",
                            "type": "rid"
                        }
                    ],
                    "user_pmapv_id": "201227T172634"
                }
        command is json string, or dictionary.
        need 'regions' defined, or else whole map will be cleaned.
        if 'pmap_id' is not specified, the first pmap_id found in robots list is used.
        '''
        pmaps = self.get_property('pmaps')
        self._logger.info('pmaps: %s', pmaps)
        myCommand = {}
        if not isinstance(command, dict):
            command = json.loads(command)

        myCommand['command'] = command.get('command', 'start')
        myCommand['ordered'] = 1
        pmap_id = command.get('pmap_id')
        user_pmap_id = command.get('user_pmapv_id')

        if pmaps:
            found = False
            for pmap in pmaps:
                for k, v in pmap.items():
                    if pmap_id:
                        if k == pmap_id:
                            user_pmap_id = v
                            found = True
                            break
                    else:
                        pmap_id = k
                        user_pmap_id = v
                        found = True
                        break
                if found:
                    break

        myCommand['pmap_id'] = pmap_id
        for region in command.get('regions', []):
            myCommand.setdefault('regions', [])
            if not isinstance(region, dict) and str(region).isdigit():
                region = {'region_id': str(region), 'type': 'rid'}
            if isinstance(region, dict):
                myCommand['regions'].append(region)
        myCommand['user_pmapv_id'] = user_pmap_id

        self._send_command(myCommand)

    def _set_preference(self, preference, setting):
        self._logger.info("Received SETTING: %s, %s", preference, setting)
        try:
            val = int(setting)
        except ValueError:
            try:
                val = float(setting)
            except ValueError:
                val = setting

        # Parse boolean string
        if isinstance(setting, str):
            if setting.lower() == "true":
                val = True
            elif setting.lower() == "false":
                val = False
            else:
                try:
                    val = json.loads(setting)
                except ValueError:
                    pass

        Command = {"state": {preference: val}}
        myCommand = json.dumps(Command)
        self._logger.info(f"Publishing {self._config.name} Setting :{myCommand}")
        self.__robot_mqtt_client.publish("delta", myCommand)

    def _set_cleanSchedule(self, setting):
        self._logger.info("Received %s cleanSchedule", self._config.name)
        sched = "cleanSchedule"
        if self.is_setting("cleanSchedule2"):
            sched = "cleanSchedule2"
        Command = {"state": {sched: setting}}
        myCommand = json.dumps(Command)
        self._logger.info("Publishing %s %s : %s", self._config.name, sched, myCommand)
        self.__robot_mqtt_client.publish("delta", myCommand)

    def publish(self, topic, message):
        if self.__local_mqtt_client is not None and message is not None:
            topic = f"{self.brokerFeedback}/{topic}"
            self._logger.debug("Publishing item: %s: %s", topic, message)
            self.__local_mqtt_client.publish(topic, message)

    def set_callback(self, cb=None):
        self.cb = cb

    def set_options(self, raw=False, max_sqft=0):
        self.raw = raw
        self.max_sqft = int(max_sqft)
        if self.raw:
            self._logger.info("Posting RAW data")
        else:
            self._logger.info("Posting DECODED data")

    def totimestamp(self, dt):
        td = dt - datetime.datetime(1970, 1, 1)
        return int(td.total_seconds())

    def dict_merge(self, dct, merge_dct):
        '''
        Recursive dict merge. Inspired by :meth:``dict.update()``, instead
        of updating only top-level keys, dict_merge recurses down into dicts
        nested to an arbitrary depth, updating keys. The ``merge_dct`` is
        merged into ``dct``.
        :param dct: dict onto which the merge is executed
        :param merge_dct: dct merged into dct
        :return: None
        '''
        for k, v in merge_dct.items():
            if (k in dct and isinstance(dct[k], dict)
                    and isinstance(merge_dct[k], Mapping)):
                self.dict_merge(dct[k], merge_dct[k])
            else:
                dct[k] = merge_dct[k]

    def recursive_lookup(self, search_dict, key, cap=False):
        '''
        recursive dictionary lookup
        if cap is true, return key if it's in the 'cap' dictionary,
        else return the actual key value
        '''
        for k, v in search_dict.items():
            if cap:
                if k == 'cap':
                    return self.recursive_lookup(v, key, False)
            elif k == key:
                return v
            elif isinstance(v, dict) and k != 'cap':
                val = self.recursive_lookup(v, key, cap)
                if val is not None:
                    return val
        return None

    def is_setting(self, setting, search_dict=None):
        if search_dict is None:
            search_dict = self.master_state
        for k, v in search_dict.items():
            if k == setting:
                return True
            if isinstance(v, dict):
                if self.is_setting(setting, v):
                    return True
        return False

    def decode_payload(self, topic, payload):
        '''
        return a dict of the json data
        '''
        try:
            # if it's json data, decode it (use OrderedDict to preserve keys
            # order), else return as is...
            json_data = json.loads(
                payload.decode("utf-8").replace(":nan", ":NaN").
                replace(":inf", ":Infinity").replace(":-inf", ":-Infinity"))  # removed object_pairs_hook=OrderedDict
            # if it's not a dictionary, probably just a number
            if not isinstance(json_data, dict):
                return dict(json_data)

        except ValueError:
            pass

        return dict(json_data)

    def decode_topics(self, state: dict, prefix=None):
        '''
        decode json data dict, and publish as individual topics to
        brokerFeedback/topic the keys are concatenated with _ to make one unique
        topic name strings are expressly converted to strings to avoid unicode
        representations
        '''
        for k, v in state.items():
            if isinstance(v, dict):
                if prefix is None:
                    self.decode_topics(v, k)
                else:
                    self.decode_topics(v, prefix+"_"+k)
            else:
                if isinstance(v, list):
                    newlist = []
                    for i in v:
                        if isinstance(i, dict):
                            json_i = json.dumps(i)
                            self._logger.debug("json value for %s is %s", k, json_i)
                            newlist.append(json_i)
                        else:
                            if not isinstance(i, str):
                                i = str(i)
                            newlist.append(i)
                    v = json.dumps(newlist)
                if prefix is not None:
                    k = prefix+"_"+k
                # all data starts with this, so it's redundant
                k = k.replace("state_reported_", "")
                if not isinstance(v, str):
                    v = str(v)
                self.publish(k, v)

        if prefix is None:
            self.update_state_machine()

    async def get_settings(self, items):
        result = {}
        if not isinstance(items, list):
            items = [items]
        for item in items:
            value = await self._loop.run_in_executor(None, self.get_property, item)
            result[item] = value
        return result

    def get_error_message(self, error_num):
        try:
            error_message = self._ErrorMessages[error_num]
        except KeyError as e:
            self._logger.warning("Error looking up error message %s", e)
            error_message = f"Unknown Error number: {error_num}"
        return error_message

    def publish_error_message(self):
        self.publish("error_message", self.error_message)

    def get_property(self, property, cap=False):
        '''
        Only works correctly if property is a unique key
        '''
        if property in ['cleanSchedule', 'langs']:
            value = self.recursive_lookup(self.master_state, property+'2', cap)
            if value is not None:
                return value
        return self.recursive_lookup(self.master_state, property, cap)

    @property
    def error_num(self):
        try:
            return self.cleanMissionStatus.get('error')
        except AttributeError:
            pass
        return 0

    @property
    def error_message(self):
        return self.get_error_message(self.error_num)

    @property
    def pose(self):
        return self.get_property("pose")

    @property
    def batPct(self):
        return self.get_property("batPct")

    @property
    def bin_full(self):
        return self.get_property("bin_full")

    @property
    def tanklvl(self):
        return self.get_property("tankLvl")

    @property
    def rechrgM(self):
        return self.get_property("rechrgM")

    def calc_mssM(self):
        start_time = self.get_property("mssnStrtTm")
        if start_time:
            return int((datetime.datetime.now() - datetime.datetime.fromtimestamp(start_time)).total_seconds()//60)
        start = self.timers.get('start')
        if start:
            return int((time.time()-start)//60)
        return None

    @property
    def mssnM(self):
        mssM = self.get_property("mssnM")
        if not mssM:
            run_time = self.calc_mssM()
            return run_time if run_time else mssM
        return mssM

    @property
    def expireM(self):
        return self.get_property("expireM")

    @property
    def cap(self):
        return self.get_property("cap")

    @property
    def sku(self):
        return self.get_property("sku")

    @property
    def mission(self):
        return self.get_property("cycle")

    @property
    def phase(self):
        return self.get_property("phase")

    @property
    def cleanMissionStatus_phase(self):
        return self.phase

    @property
    def cleanMissionStatus(self):
        return self.get_property("cleanMissionStatus")

    @property
    def pmaps(self):
        return self.get_property("pmaps")

    @property
    def regions(self):
        return self.get_property("regions")

    @property
    def pcent_complete(self):
        return self.update_precent_complete()

    def set_flags(self, flags=None):
        self.handle_flags(flags, True)

    def clear_flags(self, flags=None):
        self.handle_flags(flags)

    def flag_set(self, flag):
        try:
            return self.master_state['state']['flags'].get(flag, False)
        except KeyError:
            pass
        return False

    def handle_flags(self, flags=None, set=False):
        self.master_state['state'].setdefault('flags', {})
        if isinstance(flags, str):
            flags = [flags]
        if flags:
            for flag in flags:
                if set:
                    if not self.flag_set(flag):
                        self.flags[flag] = True
                    self.master_state['state']['flags'].update(self.flags)
                else:
                    self.flags.pop(flag, None)
                    self.master_state['state']['flags'].pop(flag, None)
        else:
            self.flags = {}
            if not set:
                self.master_state['state']['flags'] = self.flags

    def update_precent_complete(self):
        try:
            sq_ft = self.get_property("sqft")
            if self.max_sqft and sq_ft is not None:
                percent_complete = int(sq_ft)*100//self.max_sqft
                self.publish("roomba_percent_complete", percent_complete)
                return percent_complete
        except (KeyError, TypeError):
            pass
        return None

    def update_history(self, property, value=None, cap=False):
        '''
        keep previous value
        '''
        if value is not None:
            current = value
        else:
            current = self.get_property(property, cap)
        if isinstance(current, dict):
            current = current.copy()
        previous = self.history.get(property, {}).get('current')
        if previous is None:
            previous = current
        self.history[property] = {'current': current,
                                  'previous': previous}
        return current

    def set_history(self, property, value=None):
        if isinstance(value, dict):
            value = value.copy()
        self.history[property] = {'current': value,
                                  'previous': value}

    def current(self, property):
        return self.history.get(property, {}).get('current')

    def previous(self, property):
        return self.history.get(property, {}).get('previous')

    def changed(self, property):
        changed = self.history.get(property, {}).get('current') != self.history.get(property, {}).get('previous')
        return changed

    def is_set(self, name):
        return self.timers.get(name, {}).get('value', False)

    def when_run(self, name):
        th = self.timers.get(name, {}).get('reset', None)
        if th:
            return max(0, int(th._when - self._loop.time()))
        return 0

    def timer(self, name, value=False, duration=10):
        self.timers.setdefault(name, {})
        self.timers[name]['value'] = value
        self._logger.debug('Set %s to: %s', name, value)
        if self.timers[name].get('reset'):
            self.timers[name]['reset'].cancel()
        if value:
            self.timers[name]['reset'] = self._loop.call_later(duration, self.timer, name)  # reset reset timer in duration seconds

    def roomba_type(self, type):
        '''
        returns True or False if the first letter of the sku is in type (a list)
        valid letters are:
        r   900 series
        e   e series
        i   i series
        s   s series
        '''
        if not isinstance(type, list):
            type = [type]
        if isinstance(self.sku, str):
            return self.sku[0].lower() in type
        return None

    def update_state_machine(self, new_state=None):
        '''
        iRobot progresses through states (phases), current identified states
        are:
        ""              : program started up, no state yet
        "run"           : running on a Cleaning Mission
        "hmUsrDock"     : returning to Dock
        "hmMidMsn"      : need to recharge
        "hmPostMsn"     : mission completed
        "charge"        : charging
        "stuck"         : robot is stuck
        "stop"          : Stopped
        "pause"         : paused
        "evac"          : emptying bin
        "chargingerror" : charging base is unplugged

        available states:
        states = {"charge"          : "Charging",
                  "new"             : "New Mission",
                  "run"             : "Running",
                  "resume"          : "Running",
                  "hmMidMsn"        : "Docking",
                  "recharge"        : "Recharging",
                  "stuck"           : "Stuck",
                  "hmUsrDock"       : "User Docking",
                  "completed"       : "Mission Completed",
                  "cancelled"       : "Cancelled",
                  "stop"            : "Stopped",
                  "pause"           : "Paused",
                  "evac"            : "Emptying",
                  "hmPostMsn"       : "Docking - End Mission",
                  "chargingerror"   : "Base Unplugged",
                  ""                :  None}

        Normal Sequence is "" -> charge -> run -> hmPostMsn -> charge
        Mid mission recharge is "" -> charge -> run -> hmMidMsn -> charge
                                   -> run -> hmPostMsn -> charge
        Stuck is "" -> charge -> run -> hmPostMsn -> stuck
                    -> run/charge/stop/hmUsrDock -> charge
        Start program during run is "" -> run -> hmPostMsn -> charge
        Note: Braava M6 goes run -> hmPostMsn -> run -> charge when docking
        Note: S9+ goes run -> hmPostMsn -> charge -> run -> charge on a training mission (ie cleanMissionStatus_cycle = 'train')
        Note: The first 3 "pose" (x, y) co-ordinate in the first 10 seconds during undocking at mission start seem to be wrong
              for example, during undocking:
              {"x": 0, "y": 0},
              {"x": -49, "y": 0},
              {"x": -47, "y": 0},
              {"x": -75, "y": -11}... then suddenly becomes normal co-ordinates
              {"x": -22, "y": 131}
              {"x": -91, "y": 211}
              also during "hmPostMsn","hmMidMsn", "hmUsrDock" the co-ordinates system also seems to change to bogus values
              For example, in "run" phase, co-ordinates are reported as:
              {"x": -324, "y": 824},
              {"x": -324, "y": 826} ... etc, then some time after hmMidMsn (for example) they change to:
              {"x": 417, "y": -787}, which continues for a while
              {"x": 498, "y": -679}, and then suddenly changes back to normal co-ordinates
              {"x": -348, "y": 787},
              {"x": -161, "y": 181},
              {"x": 0, "y": 0}

              For now use self.distance_betwwen() to ignore large changes in position

        Need to identify a new mission to initialize map, and end of mission to
        finalise map.
        mission goes from 'none' to 'clean' (or another mission name) at start of mission (init map)
        mission goes from 'clean' (or other mission) to 'none' at end of missions (finalize map)
        Anything else = continue with existing map
        '''
        if new_state is not None:
            self.current_state = self.states[new_state]
            self._logger.info("set current state to: %s", self.current_state)
            return

        self.publish_error_message()  # publish error messages
        self.update_precent_complete()
        mission = self.update_history("cycle")  # mission
        phase = self.update_history("phase")  # mission phase
        self.update_history("pose")  # update co-ordinates

        if self.cb is not None:  # call callback if set
            self.cb(self.master_state)

        if phase is None or mission is None:
            return

        if self._debug:
            self.timer('ignore_coordinates')

        self._logger.debug(
            '%s current_state: %s, current phase: %s, mission: %s, mission_min: %s, recharge_min: %s, co-ords changed: %s',
            self.name,
            self.current_state,
            phase,
            mission,
            self.mssnM,
            self.rechrgM,
            self.changed('pose')
        )

        if self.current_state == self.states["new"] and phase != 'run':
            self._logger.info('waiting for run state for New Missions')
            if time.time() - self.timers['start'] >= 20:
                self._logger.warning('Timeout waiting for run state')
                self.current_state = self.states[phase]

        elif phase == "run" and (self.is_set('ignore_run') or mission == 'none'):
            self._logger.info('Ignoring bogus run state')

        elif phase == "charge" and mission == 'none' and self.is_set('ignore_run'):
            self._logger.info('Ignoring bogus charge/mission state')
            self.update_history("cycle", self.previous('cycle'))

        elif phase in ["hmPostMsn", "hmMidMsn", "hmUsrDock"]:
            self.timer('ignore_run', True, 10)
            self.current_state = self.states[phase]

        elif self.changed('cycle'):  # if mission has changed
            if mission != 'none':
                self.current_state = self.states["new"]
                self.timers['start'] = time.time()
                if isinstance(self.sku, str) and self.sku[0].lower() in ['i', 's', 'm']:
                    # self.timer('ignore_coordinates', True, 30)  #ignore updates for 30 seconds at start of new mission
                    pass
            else:
                self.timers.pop('start', None)
                if self.bin_full:
                    self.current_state = self.states["cancelled"]
                else:
                    self.current_state = self.states["completed"]
                self.timer('ignore_run', True, 5)  # still get bogus 'run' states after mission complete.

        elif phase == "charge" and self.rechrgM:
            if self.bin_full:
                self.current_state = self.states["pause"]
            else:
                self.current_state = self.states["recharge"]

        else:
            try:
                self.current_state = self.states[phase]
            except KeyError:
                self._logger.warning('phase: %s not found in self.states', phase)

        self.publish("state", self.current_state)

        if self.is_set('ignore_coordinates') and self.current_state != self.states["new"]:
            self._logger.info('Ignoring co-ordinate updates')
