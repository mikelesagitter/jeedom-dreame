#!/usr/bin/env python3
# -*- coding: utf-8 -*-


__version__ = "3.0.0"

import asyncio
from collections.abc import Mapping
from roomba.password import Password
import datetime
import json
import logging
import socket
import ssl
import sys
import time
import paho.mqtt.client as mqtt
from functools import cache

if sys.version_info < (3, 7):
    sys.exit("Python 3.7.0 or later required")


class Roomba(object):
    '''
    This is a Class for Roomba WiFi connected Vacuum cleaners and mops
    Requires firmware version 2.0 and above (not V1.0). Tested with Roomba 980, s9
    and braava M6.
    username (blid) and password are required, and can be found using the
    Password() class (in password.py - or can be auto discovered)
    Most of the underlying info was obtained from here:
    https://github.com/koalazak/dorita980 many thanks!
    The values received from the Roomba as stored in a dictionary called
    master_state, and can be accessed at any time, the contents are live, and
    will build with time after connection.
    This is not needed if the forward to mqtt option is used, as the events will
    be decoded and published on the designated mqtt client topic.
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
        65: "Hardware problem detected",
        66: "Low memory",
        68: "Hardware problem detected",
        73: "Pad type changed",
        74: "Max area reached",
        75: "Navigation problem",
        76: "Hardware problem detected",
        88: "Back-up refused",
        89: "Mission runtime too long",
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
        122: "Charging system error",
        123: "Battery not initialized",
        216: "Charging base bag full",
    }

    def __init__(self, address=None, blid=None, password=None, topic="#",
                 roombaName="", file="./config.ini", log=None):
        '''
        address is the IP address of the Roomba,
        leave topic as is, unless debugging (# = all messages).
        if a python standard logging object called 'Roomba' exists,
        it will be used for logging,
        or pass a logging object
        '''
        self.loop = asyncio.get_running_loop()
        self.debug = False
        if log:
            self.log = log
        else:
            self.log = logging.getLogger(f"Roomba.{roombaName if roombaName else __name__}")
        if self.log.getEffectiveLevel() == logging.DEBUG:
            self.debug = True
        self.address = address
        self.roomba_port = 8883
        self.blid = blid
        self.password = password
        self.roombaName = roombaName
        self.file = file
        self.get_passwd = Password(file=file)
        self.topic = topic
        self.mqttc = None
        self.local_mqtt = False
        self.exclude = ""
        self.roomba_connected = False
        self.raw = False
        self.mapSize = None
        self.current_state = None
        self.simulation = False
        self.simulation_reset = False
        self.master_state = {}
        self.update_seconds = 300  # update with all values every 5 minutes
        self.client = None  # Roomba MQTT client
        self.roombas_config = {}  # Roomba configuration loaded from config file
        self.history = {}
        self.timers = {}
        self.flags = {}
        self.max_sqft = None
        self.cb = None

        self.is_connected = asyncio.Event()
        self.q = asyncio.Queue()
        self.command_q = asyncio.Queue()
        self.loop.create_task(self.process_q())
        self.loop.create_task(self.process_command_q())
        self.update = self.loop.create_task(self.periodic_update())

        if not all([self.address, self.blid, self.password]):
            if not self.configure_roomba():
                self.log.critical('Could not configure Roomba')
        else:
            self.roombas_config = {self.address: {
                                   "blid": self.blid,
                                   "password": self.password,
                                   "roomba_name": self.roombaName}}

    async def event_wait(self, evt, timeout):
        '''
        Event.wait() with timeout
        '''
        try:
            await asyncio.wait_for(evt.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        return evt.is_set()

    def configure_roomba(self):
        self.log.info('configuring Roomba from file %s', self.file)
        self.roombas_config = self.get_passwd.get_roombas()
        for ip, roomba in self.roombas_config.items():
            if any([self.address == ip, self.blid == roomba['blid'], roomba['roomba_name'] == self.roombaName]):
                self.roombaName = roomba['roomba_name']
                self.address = ip
                self.blid = roomba['blid']
                self.password = roomba['password']
                self.max_sqft = roomba.get('max_sqft', 0)
                return True

        self.log.warning('No Roomba specified, or found, exiting')
        return False

    @cache
    def generate_tls_context(self) -> ssl.SSLContext:
        """Generate TLS context.

        We only want to do this once ever because it's expensive.
        """
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers("DEFAULT:!DH")
        ssl_context.load_default_certs()
        # ssl.OP_LEGACY_SERVER_CONNECT is only available in Python 3.12a4+
        ssl_context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        return ssl_context

    def setup_client(self):
        if self.client is None:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.blid,
                clean_session=True,
                protocol=mqtt.MQTTv311)
            # Assign event callbacks
            self.client.on_message = self.on_message
            self.client.on_connect = self.on_connect
            self.client.on_subscribe = self.on_subscribe
            self.client.on_disconnect = self.on_disconnect

            # Uncomment to enable debug messages
            #self.client.on_log = self.on_log

            self.log.info("Setting TLS")
            try:
                ssl_context = self.generate_tls_context()
                self.client.tls_set_context(ssl_context)
                self.client.tls_insecure_set(True)
            except Exception as e:
                self.log.exception("Error setting TLS: %s", e)

            # disables peer verification
            self.client.tls_insecure_set(True)
            self.client.username_pw_set(self.blid, self.password)
            self.log.info("Setting TLS - OK")
            return True
        return False

    def connect(self):
        '''
        just create async_connect task
        '''
        return self.loop.create_task(self.async_connect())

    async def async_connect(self):
        '''
        Connect to Roomba MQTT server
        '''
        if not all([self.address, self.blid, self.password]):
            self.log.critical("Invalid address, blid, or password! All these "
                              "must be specified!")
            return False
        count = 0
        max_retries = 3
        retry_timeout = 1
        while not self.roomba_connected:
            try:
                if self.client is None:
                    self.log.info("Connecting...")
                    self.setup_client()
                    await self.loop.run_in_executor(None, self.client.connect, self.address, self.roomba_port, 60)
                else:
                    self.log.info("Attempting to Reconnect...")
                    self.client.loop_stop()
                    await self.loop.run_in_executor(None, self.client.reconnect)
                self.client.loop_start()
                await self.event_wait(self.is_connected, 1)  # wait for MQTT on_connect to fire (timeout 1 second)
            except (ConnectionRefusedError, OSError) as e:
                if e.errno == 111:  # errno.ECONNREFUSED
                    self.log.error('Unable to Connect to roomba %s, make sure nothing else is connected (app?), as only one connection at a time is allowed', self.roombaName)
                elif e.errno == 113:  # errno.No Route to Host
                    self.log.error('Unable to contact roomba %s on ip %s', self.roombaName, self.address)
                else:
                    self.log.error("Connection Error: %s ", e)

                self.log.debug("sleeping %is", retry_timeout)
                await asyncio.sleep(retry_timeout)
                retry_timeout = retry_timeout * 2
                self.log.error("Attempting retry Connection# %i", count)

                count += 1
                if count >= max_retries:
                    retry_timeout = 60

            except asyncio.CancelledError:
                self.log.error('Connection Cancelled')
                break
            except Exception as e:
                self.log.exception(e)
                if count >= max_retries:
                    break

        if not self.roomba_connected:
            self.log.error("Unable to connect to %s", self.roombaName)
        return self.roomba_connected

    def disconnect(self):
        self.loop.create_task(self._disconnect())

    async def _disconnect(self):
        try:
            self.client.disconnect()
            if self.local_mqtt:
                self.mqttc.loop_stop()
        except Exception as e:
            self.log.warning("Some exception occured during mqtt disconnect: %s", e)
        self.log.info('%s disconnected', self.roombaName)

    def connected(self, state):
        self.roomba_connected = state
        self.publish('status', 'Online' if self.roomba_connected else f"Offline at {time.ctime()}")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.log.info("Roomba Connected")
        if reason_code == 0:
            self.connected(True)
            self.client.subscribe(self.topic)
            self.client.subscribe("$SYS/#")
        else:
            self.log.error("Connected with result code %s", reason_code)
            self.log.error("Please make sure your blid and password are correct for Roomba %s", self.roombaName)
            self.connected(False)
            self.client.disconnect()
        self.loop.call_soon_threadsafe(self.is_connected.set)

    def on_message(self, client, userdata, message: mqtt.MQTTMessage):
        if self.exclude != "" and self.exclude in message.topic:
            return

        if not self.simulation:
            asyncio.run_coroutine_threadsafe(self.q.put(message), self.loop)

    async def process_q(self):
        '''
        Main processing loop, run until program exit
        '''
        while True:
            try:
                if self.q.qsize() > 0:
                    self.log.warning('Pending event queue size is: %i', self.q.qsize())
                msg = await self.q.get()

                if not self.command_q.empty():
                    self.log.info('Command waiting in queue')
                    await asyncio.sleep(1)

                json_data = self.decode_payload(msg.topic, msg.payload)
                self.dict_merge(self.master_state, json_data)

                self.log.info("Received Roomba Data: %s, %s", str(msg.topic), str(msg.payload))

                if self.raw:
                    self.publish(msg.topic, msg.payload)
                else:
                    await self.loop.run_in_executor(None, self.decode_topics, json_data)

                self.q.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.exception(e)

    async def periodic_update(self):
        '''
        publish status peridically
        '''
        while True:
            # default every 5 minutes
            await asyncio.sleep(self.update_seconds)
            if self.roomba_connected:
                self.log.info("Publishing master_state")
                await self.loop.run_in_executor(None, self.decode_topics, self.master_state)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        self.log.debug("Subscribed: %s %s", mid, reason_codes)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.loop.call_soon_threadsafe(self.is_connected.clear)
        self.connected(False)
        if reason_code != 0:
            self.log.warning("Unexpected Disconnect! - reconnecting")
        else:
            self.log.info("Disconnected")

    def on_log(self, client, userdata, level, buf):
        self.log.info(buf)

    def set_mqtt_client(self, mqttc=None, brokerFeedback='/roomba/feedback'):
        self.mqttc = mqttc
        if self.mqttc is not None:
            self.brokerFeedback = self.set_mqtt_topic(brokerFeedback)

    def set_mqtt_topic(self, topic, subscribe=False):
        if self.blid:
            topic = f"{topic}/{self.blid}{'/#' if subscribe else ''}"
        return topic

    def setup_mqtt_client(self, broker=None,
                          port=1883,
                          user=None,
                          passwd=None,
                          brokerFeedback='/roomba/feedback',
                          brokerCommand='/roomba/command',
                          brokerSetting='/roomba/setting'):
        # returns an awaitable future

        return self.loop.run_in_executor(None, self._setup_mqtt_client, broker,
                                         port, user, passwd,
                                         brokerFeedback, brokerCommand,
                                         brokerSetting)

    def _setup_mqtt_client(self, broker=None,
                           port=1883,
                           user=None,
                           passwd=None,
                           brokerFeedback='/roomba/feedback',
                           brokerCommand='/roomba/command',
                           brokerSetting='/roomba/setting'):
        '''
        setup local mqtt connection to broker for feedback,
        commands and settings
        '''
        try:
            # connect to broker
            self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            # Assign event callbacks
            self.mqttc.on_message = self.broker_on_message
            self.mqttc.on_connect = self.broker_on_connect
            self.mqttc.on_disconnect = self.broker_on_disconnect
            if user and passwd:
                self.mqttc.username_pw_set(user, passwd)
            self.mqttc.connect(broker, port, 60)
            self.brokerFeedback = self.set_mqtt_topic(brokerFeedback)
            self.brokerCommand = self.set_mqtt_topic(brokerCommand, True)
            self.brokerSetting = self.set_mqtt_topic(brokerSetting, True)
            self.mqttc.loop_start()
            self.local_mqtt = True
        except socket.error:
            self.log.error("Unable to connect to MQTT Broker")
            self.mqttc = None
        return self.mqttc

    def broker_on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties):
        self.log.debug("Broker Connected with result code %s", reason_code)
        # subscribe to roomba commands and settings messages
        if reason_code == 0:
            client.subscribe(self.brokerCommand)
            client.subscribe(self.brokerSetting)
            client.subscribe(self.brokerCommand.replace('command', 'simulate'))
            self.log.info('subscribed to %s, %s', self.brokerCommand, self.brokerSetting)

    def broker_on_message(self, client, userdata, message: mqtt.MQTTMessage):
        # receive commands and settings from broker
        payload = message.payload.decode("utf-8")
        if "command" in message.topic:
            self.log.info("Received COMMAND from broker: %s", payload)
            self.send_command(payload)
        elif "setting" in message.topic:
            self.log.info("Received SETTING from broker: %s", payload)
            cmd = str(payload).split(None, 1)
            self.set_preference(cmd[0], cmd[1])
        elif 'simulate' in message.topic:
            self.log.info('received simulate command from broker: %s', payload)
            self.set_simulate(True)
            asyncio.run_coroutine_threadsafe(self.q.put(message), self.loop)
        else:
            self.log.warn("Unknown topic: %s", message.topic)

    def set_simulate(self, value=False):
        if self.simulation != value:
            self.log.info('Set simulation to: %s', value)
        self.simulation = value
        if self.simulation_reset:
            self.simulation_reset.cancel()
        if value:
            self.simulation_reset = self.loop.call_later(10, self.set_simulate)  # reset simulation in 10s

    def broker_on_disconnect(self, client: mqtt.Client, userdata, flags, reason_code, properties):
        self.log.debug("Broker disconnected")

    async def async_send_command(self, command):
        await self.command_q.put({'command': command})

    async def async_set_preference(self, preference, setting):
        await self.command_q.put({'setting': (preference, setting)})

    async def async_set_cleanSchedule(self, setting):
        await self.command_q.put({'schedule': setting})

    def send_command(self, command):
        asyncio.run_coroutine_threadsafe(self.command_q.put({'command': command}), self.loop)

    def set_preference(self, preference, setting):
        asyncio.run_coroutine_threadsafe(self.command_q.put({'setting': (preference, setting)}), self.loop)

    def set_cleanSchedule(self, setting):
        asyncio.run_coroutine_threadsafe(self.command_q.put({'schedule': setting}), self.loop)

    async def process_command_q(self):
        '''
        Command processing loop, run until program exit
        '''
        while True:
            value = await self.command_q.get()
            command = value.get('command')
            setting = value.get('setting')
            schedule = value.get('schedule')
            if command:
                await self.loop.run_in_executor(None, self._send_command, command)
            if setting:
                await self.loop.run_in_executor(None, self._set_preference, *setting)
            if schedule:
                await self.loop.run_in_executor(None, self._set_cleanSchedule, schedule)
            self.command_q.task_done()

    def _send_command(self, command):
        '''
        eg
        {"command": "reset", "initiator": "admin", "time": 1609950197}
        {"command": "find", "initiator": "rmtApp", "time": 1612462418, "robot_id": null, "select_all": null}}}}'
        '''
        self.log.info("Processing COMMAND: %s", command)
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
        self.log.info("Sending Command: %s", myCommand)
        self.client.publish("cmd", myCommand)

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
        if 'pmap_id' is not specified, the first pmap_id found in roombas list is used.
        '''
        pmaps = self.get_property('pmaps')
        self.log.info('pmaps: %s', pmaps)
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

    def is_json(self, myjson):
        try:
            json.loads(myjson)
        except ValueError as e:
            return False
        return True

    def _set_preference(self, preference, setting):
        self.log.info("Received SETTING: %s, %s", preference, setting)
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
            elif self.is_json(setting):
                val = json.loads(setting)
        Command = {"state": {preference: val}}
        myCommand = json.dumps(Command)
        self.log.info(f"Publishing Roomba {self.roombaName} Setting :{myCommand}")
        self.client.publish("delta", myCommand)

    def _set_cleanSchedule(self, setting):
        self.log.info("Received Roomba %s cleanSchedule:", self.roombaName)
        sched = "cleanSchedule"
        if self.is_setting("cleanSchedule2"):
            sched = "cleanSchedule2"
        Command = {"state": {sched: setting}}
        myCommand = json.dumps(Command)
        self.log.info("Publishing Roomba %s %s : %s", self.roombaName, sched, myCommand)
        self.client.publish("delta", myCommand)

    def publish(self, topic, message):
        if self.mqttc is not None and message is not None:
            topic = f"{self.brokerFeedback}/{topic}"
            self.log.debug("Publishing item: %s: %s", topic, message)
            self.mqttc.publish(topic, message)

    def set_callback(self, cb=None):
        self.cb = cb

    def set_options(self, raw=False, max_sqft=0):
        self.raw = raw
        self.max_sqft = int(max_sqft)
        if self.raw:
            self.log.info("Posting RAW data")
        else:
            self.log.info("Posting DECODED data")

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

    def decode_topics(self, state, prefix=None):
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
                            self.log.debug("json value for %s is %s", k, json_i)
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
            value = await self.loop.run_in_executor(None, self.get_property, item)
            result[item] = value
        return result

    def get_error_message(self, error_num):
        try:
            error_message = self._ErrorMessages[error_num]
        except KeyError as e:
            self.log.warning("Error looking up error message %s", e)
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
    def cleanMissionStatus(self):
        return self.get_property("cleanMissionStatus")

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
            return max(0, int(th._when - self.loop.time()))
        return 0

    def timer(self, name, value=False, duration=10):
        self.timers.setdefault(name, {})
        self.timers[name]['value'] = value
        self.log.info('Set %s to: %s', name, value)
        if self.timers[name].get('reset'):
            self.timers[name]['reset'].cancel()
        if value:
            self.timers[name]['reset'] = self.loop.call_later(duration, self.timer, name)  # reset reset timer in duration seconds

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
        Roomba progresses through states (phases), current identified states
        are:
        ""              : program started up, no state yet
        "run"           : running on a Cleaning Mission
        "hmUsrDock"     : returning to Dock
        "hmMidMsn"      : need to recharge
        "hmPostMsn"     : mission completed
        "charge"        : charging
        "stuck"         : Roomba is stuck
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
            self.log.info("set current state to: %s", self.current_state)
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

        current_mission = self.current_state

        if self.debug:
            self.timer('ignore_coordinates')
            current_mission = None  # force update of map

        self.log.info('current_state: %s, current phase: %s, mission: %s, mission_min: %s, recharge_min: %s, co-ords changed: %s',
                      self.current_state,
                      phase,
                      mission,
                      self.mssnM,
                      self.rechrgM,
                      self.changed('pose'))

        if phase == "charge":
            current_mission = None

        if self.current_state == self.states["new"] and phase != 'run':
            self.log.info('waiting for run state for New Missions')
            if time.time() - self.timers['start'] >= 20:
                self.log.warning('Timeout waiting for run state')
                self.current_state = self.states[phase]

        elif phase == "run" and (self.is_set('ignore_run') or mission == 'none'):
            self.log.info('Ignoring bogus run state')

        elif phase == "charge" and mission == 'none' and self.is_set('ignore_run'):
            self.log.info('Ignoring bogus charge/mission state')
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
                self.log.warning('phase: %s not found in self.states', phase)

        if self.current_state != current_mission:
            self.log.info("updated state to: %s", self.current_state)

        self.publish("state", self.current_state)

        if self.is_set('ignore_coordinates') and self.current_state != self.states["new"]:
            self.log.info('Ignoring co-ordinate updates')
