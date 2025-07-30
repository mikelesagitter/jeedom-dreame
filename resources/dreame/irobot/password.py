from __future__ import annotations

import logging
import socket
import struct
import requests

from .utils import generate_tls_context

from .const import ERROR_CONNECTION_REFUSED, ERROR_NO_ROUTE_TO_HOST, ROBOT_PORT

PASSWORD_REQUEST = bytes.fromhex("f005efcc3b2900")
UNSUPPORTED_MAGIC = bytes.fromhex("f005efcc3b2903")


class iRobotPassword:
    """Main class to get a password."""

    _logger = logging.getLogger()

    def __init__(self, ip: str) -> None:
        """Init default values."""
        self._ip = ip
        self._server_socket = self._get_socket()

    """
    Robot have to be on Home Base powered on.
    Press and hold HOME button until you hear series of tones.
    Release button, Wi-Fi LED should be flashing
    After that execute get_password method
    """

    @staticmethod
    def get_passwords_from_cloud(login: str, password: str) -> dict | None:
        try:
            r = requests.get("https://disc-prod.iot.irobotapi.com/v1/discover/endpoints?country_code=US")
            r.raise_for_status()
            response = r.json()
            deployment = response['deployments'][next(iter(response['deployments']))]
            httpBase = deployment['httpBase']
            # iotBase = deployment['httpBaseAuth']
            # iotUrl = urllib.parse.urlparse(iotBase)
            # iotHost = iotUrl.netloc
            # region = deployment['awsRegion']

            apikey = response['gigya']['api_key']
            gigyaBase = response['gigya']['datacenter_domain']

            data = {"apiKey": apikey,
                    "targetenv": "mobile",
                    "loginID": login,
                    "password": password,
                    "format": "json",
                    "targetEnv": "mobile",
                    }

            iRobotPassword._logger.debug("Post accounts.login request")
            r = requests.post(f"https://accounts.{gigyaBase}/accounts.login", data=data)
            r.raise_for_status()
            response = r.json()
            iRobotPassword._logger.debug("response: %s", response)
            '''
            data = {"timestamp": int(time.time()),
                    "nonce": "%d_%d" % (int(time.time()), random.randint(0, 2147483647)),
                    "oauth_token": response.get('sessionInfo', {}).get('sessionToken', ''),
                    "targetEnv": "mobile"}
            '''
            uid = response['UID']
            uidSig = response['UIDSignature']
            sigTime = response['signatureTimestamp']

            data = {
                "app_id": "ANDROID-C7FB240E-DF34-42D7-AE4E-A8C17079A294",
                "assume_robot_ownership": "0",
                "gigya": {
                    "signature": uidSig,
                    "timestamp": sigTime,
                    "uid": uid,
                }
            }

            header = {
                "Content-Type": "application/json",
                "host": "unauth1.prod.iot.irobotapi.com"
            }

            iRobotPassword._logger.debug("Post login request to %s with data %s", httpBase, data)
            r = requests.post(f"{httpBase}/v2/login", json=data, headers=header)
            r.raise_for_status()
            response = r.json()
            iRobotPassword._logger.debug("response: %s", response)
            # access_key = response['credentials']['AccessKeyId']
            # secret_key = response['credentials']['SecretKey']
            # session_token = response['credentials']['SessionToken']

            return response['robots']
        except requests.HTTPError as e:
            iRobotPassword._logger.error("Error getting cloud data: %s", e)
        return None

    def get_password_from_robot(self) -> str | None:
        """Get password for robot."""
        try:
            self._connect()
        except (ConnectionRefusedError, OSError) as e:
            if e.errno == 111:  # errno.ECONNREFUSED
                self._logger.error(ERROR_CONNECTION_REFUSED, self._ip)
            elif e.errno == 113:  # errno.No Route to Host
                self._logger.error(ERROR_NO_ROUTE_TO_HOST, self._ip)
            else:
                self._logger.error("Connection Error (for %s): %s", self._ip, e)
            return None
        self._send_message()
        response = self._get_response()
        if response:
            return self._decode_password(response)
        return None

    def _connect(self) -> None:
        self._server_socket.connect((self._ip, ROBOT_PORT))
        self._logger.debug("Connected to %s to get password", self._ip)

    def _send_message(self) -> None:
        self._server_socket.send(PASSWORD_REQUEST)
        self._logger.debug("Password request sent to %s", self._ip)

    def _get_response(self) -> bytes | None:
        try:
            raw_data = b""
            response_length = 35
            while True:
                if len(raw_data) >= response_length + 2:
                    break

                response = self._server_socket.recv(1024)

                if len(response) == 0:
                    break

                if response == UNSUPPORTED_MAGIC:
                    self._logger.warning('Password for this model (%s) can be obtained only from cloud', self._ip)
                    break

                raw_data += response
                if len(raw_data) >= 2:
                    response_length = struct.unpack("B", raw_data[1:2])[0]
            self._server_socket.shutdown(socket.SHUT_RDWR)
            self._server_socket.close()
        except socket.timeout:
            self._logger.warning("Socket timeout for %s", self._ip)
            return None
        except OSError as e:
            self._logger.debug("Socket error for %s: %s", self._ip, e)
            return None
        else:
            return raw_data

    def _decode_password(self, data: bytes) -> str:
        return str(data[7:].decode().rstrip("\x00"))

    def _get_socket(self) -> socket.socket:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(10)
        context = generate_tls_context()
        return context.wrap_socket(server_socket)
