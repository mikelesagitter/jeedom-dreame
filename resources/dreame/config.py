from jeedomdaemon.base_config import BaseConfig


class iRobotConfig(BaseConfig):
    def __init__(self):
        super().__init__()

        self.add_argument("--host", help="mqtt host ip", type=str, default='127.0.0.1')
        self.add_argument("--port", help="mqtt host port", type=int, default=1883)
        self.add_argument("--user", help="mqtt username", type=str)
        self.add_argument("--password", help="mqtt password", type=str)
        self.add_argument("--topic_prefix", help="topic_prefix", type=str, default='dreame')
        self.add_argument("--excluded_blid", type=str)

    @property
    def host(self):
        return str(self._args.host)

    @property
    def port(self):
        return int(self._args.port)

    @property
    def user(self):
        return str(self._args.user)

    @property
    def password(self):
        return str(self._args.password)

    @property
    def topic_prefix(self):
        return str(self._args.topic_prefix)

    @property
    def excluded_blid(self):
        blids = str(self._args.excluded_blid)
        return [str(x) for x in blids.split(',') if x != '']
