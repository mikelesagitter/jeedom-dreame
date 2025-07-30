import asyncio
import os
from pathlib import Path

from irobot.irobot import iRobot
from irobot.configs import iRobotConfigs

from jeedomdaemon.base_daemon import BaseDaemon
from jeedomdaemon.base_config import BaseConfig


class DaemonConfig(BaseConfig):
    def __init__(self):
        super().__init__()

        self.add_argument("--host", help="mqtt host ip", type=str, default='127.0.0.1')
        self.add_argument("--port", help="mqtt host port", type=int, default=1883)
        self.add_argument("--user", help="mqtt username", type=str)
        self.add_argument("--password", help="mqtt password", type=str)
        self.add_argument("--topic_prefix", help="topic_prefix", type=str, default='iRobot')
        self.add_argument("--excluded_blid", type=str)

    @property
    def mqtt_host(self):
        return str(self._args.host)

    @property
    def mqtt_port(self):
        return int(self._args.port)

    @property
    def mqtt_user(self):
        return str(self._args.user)

    @property
    def mqtt_password(self):
        return str(self._args.password)

    @property
    def topic_prefix(self):
        return str(self._args.topic_prefix)

    @property
    def excluded_blid(self):
        blids = str(self._args.excluded_blid)
        return [str(x) for x in blids.split(',') if x != '']


class dreame(BaseDaemon):
    def __init__(self) -> None:
        self._config = DaemonConfig()
        super().__init__(self._config, self.on_start, self.on_message, self.on_stop)

        # self.set_logger_log_level('iRobot')

        self._robot_configs: iRobotConfigs = None
        self._robots: list[iRobot] = []

    async def on_start(self):
        basedir = os.path.dirname(__file__)
        configFile = Path(os.path.abspath(basedir + '/../../data'))
        self._robot_configs = iRobotConfigs(path=configFile)

        if len(self._robot_configs.robots) == 0:
            self._logger.info('No robot configured, trying auto discovery')
            await self._robot_configs.discover()

        if len(self._robot_configs.robots) == 0:
            self._logger.warning('No robot configured, please run discovery from plugin page')
            await self.send_to_jeedom({'msg': "NO_ROBOT"})
        else:
            asyncio.create_task(self.__connect_robots())

    async def on_stop(self):
        await self.__disconnect_robots()

    async def on_message(self, message: list):
        if message['action'] == 'discover':
            try:
                result = await self._robot_configs.discover(message['address'], message['login'], message['password'])
                if result:
                    await self.__connect_robots()
                await self.send_to_jeedom({'discover': result})
            except Exception as e:
                self._logger.error('Exception during discovery: %s', e)
                await self.send_to_jeedom({'discover': False})

    async def __connect_robots(self):
        await self.__disconnect_robots()

        coros_connect = []

        for robot_config in self._robot_configs.robots.values():
            try:
                if robot_config.blid in self._config.excluded_blid:
                    self._logger.debug("Exclude robot: %s", robot_config.name)
                    continue

                new_robot = iRobot(robot_config)
                new_robot.setup_mqtt_client(
                    self._config.mqtt_host,
                    self._config.mqtt_port,
                    self._config.mqtt_user,
                    self._config.mqtt_password,
                    brokerFeedback=self._config.topic_prefix+'/feedback',
                    brokerCommand=self._config.topic_prefix+'/command',
                    brokerSetting=self._config.topic_prefix+'/setting'
                )

                coros_connect.append(new_robot.async_connect())
                self._robots.append(new_robot)
            except Exception as e:
                self._logger.error('Exception during connection of robot %s: %s', robot_config.name, e)

        if len(coros_connect) > 0:
            await asyncio.gather(*coros_connect)

    async def __disconnect_robots(self):
        for robot in self._robots:
            await robot.disconnect()
        self._robots.clear()
        await asyncio.sleep(1)


dreame().run()
