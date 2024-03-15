#################################################################################
# WaterTAP Copyright (c) 2020-2024, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory,
# National Renewable Energy Laboratory, and National Energy Technology
# Laboratory (subject to receipt of any required approvals from the U.S. Dept.
# of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#################################################################################

__author__ = "Paul Vecchiarelli"

import logging

from copy import deepcopy

import json
import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

from pyomo.common.dependencies import attempt_import

cryptography, cryptography_available = attempt_import("cryptography", defer_check=False)
if cryptography_available:
    from cryptography.fernet import Fernet

_logger = logging.getLogger(__name__)
# set to info level, so user can see what is going on
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "OLIAPI - %(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"
)
handler.setFormatter(formatter)
_logger.addHandler(handler)
_logger.setLevel(logging.DEBUG)

# TODO: consider letting user set logging level instead of using interactive mode
class CredentialManager:
    """
    A class to handle credentials for OLI Cloud.
    """

    def __init__(
        self,
        username="",
        password="",
        root_url="",
        auth_url="",
        config_file="./credentials.txt",
        encryption_key="",
        access_keys=[],
        test=False,
        interactive_mode=True,
    ):
        """
        Manages credentials for OLIApi authentication requests.

        :param username: user's username
        :param password: user's password
        :param root_url: root url
        :param auth_url: authorization url
        :param config_file: existing/desired path (absolute, or relative to the working directory) to encrypted oli_config_file
        :param encryption_key: fernet key generated by credential manager object
        :param access_keys: list of access keys generated by user
        :param test: bool switch for automation during tests
        :param interactive_mode: bool to switch level of logging display from info to debug only
        """

        self.test = test
        self.access_key = ""
        self.encryption_key = encryption_key
        self.config_file = Path(config_file).resolve()
        self._manage_credentials(
            username,
            password,
            root_url,
            auth_url,
            access_keys,
        )
        if interactive_mode:
            _logger.setLevel(logging.INFO)
        else:
            _logger.setLevel(logging.DEBUG)
        self.set_headers()

    def set_headers(self):
        """
        Creates OLI Cloud API headers and performs initial login.
        """

        if self.access_key:
            self.headers = {"authorization": "API-KEY " + self.access_key}
            self.login()
        else:
            self.login()
            self.headers = {"authorization": "Bearer " + self.jwt_token}

    def update_headers(self, new_header):
        """
        Updates existing headers with new header.

        :param new_header: dict containing new header key and value

        :return updated_headers: dict containing updated headers
        """

        updated_headers = deepcopy(self.headers)
        updated_headers.update(new_header)
        return updated_headers

    def _manage_credentials(self, username, password, root_url, auth_url, access_keys):
        """
        Method to save/load OLI credentials.

        :param username: user's username
        :param password: user's password
        :param root_url: root url
        :param auth_url: authorization url
        :param access_keys: list of access keys generated by user
        """

        if not cryptography_available:
            raise ModuleNotFoundError("Module 'cryptography' not available.")

        if self.encryption_key:
            if self.config_file.is_file():
                self.credentials = self._decrypt_credentials()
            else:
                raise OSError(
                    f" Config file {self.config_file} does not exist."
                    + " Provide login credentials to generate encrypted file."
                )
        else:
            self.credentials = {
                "username": username,
                "password": password,
                "root_url": root_url,
                "auth_url": auth_url,
                "access_keys": access_keys,
            }
            if not access_keys:
                self._check_credentials(
                    ["username", "password", "root_url", "auth_url"]
                )
            else:
                self._check_credentials(["root_url", "access_keys"])

            if self._write_permission():
                self.encryption_key = self._encrypt_credentials()

        self.access_key = self.set_access_key()

        self.dbs_url = self.credentials["root_url"] + "/channel/dbs"
        self.upload_dbs_url = self.credentials["root_url"] + "/channel/upload/dbs"
        self.access_key_url = self.credentials["root_url"] + "/user/api-key"
        self.engine_url = self.credentials["root_url"] + "/engine/"
        self._delete_dbs_url = self.credentials["root_url"] + "/channel/file/"

    def _decrypt_credentials(self):
        """
        Basic decryption method for credentials.

        :return credentials: login credentials for OLI Cloud
        """

        try:
            with open(self.config_file, "rb") as f:
                encrypted_credentials = f.read()

            cipher = Fernet(self.encryption_key)
            decrypted_credentials = cipher.decrypt(encrypted_credentials).decode()
            credentials = json.loads(decrypted_credentials)
            return credentials

        except:
            raise RuntimeError(" Failed decryption.")

    def _check_credentials(self, keys):
        """
        Check to see if required credentials are missing.

        :param keys: keys required for login method
        """
        e = [k for k, v in self.credentials.items() if k in keys if not v]
        if e:
            raise IOError(f" Incomplete credentials for the following keys: {e}.")

    def _write_permission(self):
        """
        Ensures user permits deletion of specified files.

        :return bool: status of user permission (to write encrypted config_file to disk)
        """

        if self.test:
            return True
        else:
            r = input(
                "WaterTAP will write encrypted file to store OLI Cloud credentials: [y]/n: "
            )
            if (r.lower() == "y") or (r == ""):
                return True
            return False

    # TODO: consider updating credentials when writing, rather than resetting blank ones
    def _encrypt_credentials(self):
        """
        Basic encryption method for credentials.
        """

        encryption_key = Fernet.generate_key()
        _logger.info(f" Secret key is {encryption_key.decode()}")

        try:
            cipher = Fernet(encryption_key)
            encrypted_credentials = cipher.encrypt(
                json.dumps(self.credentials).encode()
            )
            with open(self.config_file, "wb") as f:
                f.write(encrypted_credentials)
            return encryption_key

        except:
            raise RuntimeError(f" Failed encryption.")

    def set_access_key(self):
        """
        Allows access key to be selected from list if more than one is provided.
        """
        if len(self.credentials["access_keys"]) == 0:
            return ""
        elif len(self.credentials["access_keys"]) == 1:
            return self.credentials["access_keys"][0]
        else:
            _logger.info("Specify an access key: ")
            for i in range(len(self.credentials["access_keys"])):
                _logger.info(f"{i}\t{self.credentials['access_keys'][i]}")
                if self.test:
                    r = 0
                else:
                    r = int(input(" "))
            return self.credentials["access_keys"][r]

    # TODO: possibly save api keys as objects with expiry and other attributes
    def generate_oliapi_access_key(self, key_lifetime=365):
        """
        Generate an access key for OLI Cloud.

        :param key_lifetime: integer number of days key will be valid

        :return string: Response text containing the access key information or an error message
        """

        def _set_expiry_timestamp(key_lifetime):
            """
            Set expiry date for OLI Cloud access key.

            :param key_lifetime: integer number of days key will be valid (up to 365)

            :return unix_timestamp_ms: unix timestamp (in ms) for when key will expire
            """

            if key_lifetime < 1 or key_lifetime > 365:
                key_lifetime = 365

            _logger.debug(f"Maximum key lifetime is 365 days, {key_lifetime} provided.")
            current_time = datetime.now(timezone.utc)
            expiry_timestamp = (current_time + timedelta(days=key_lifetime)).timestamp()
            unix_timestamp_ms = int(expiry_timestamp * 1000)
            return unix_timestamp_ms

        response = requests.post(
            self.access_key_url,
            headers=self.update_headers({"Content-Type": "application/json"}),
            data=json.dumps({"expiry": _set_expiry_timestamp(key_lifetime)}),
        )

        self.credentials["access_keys"].append(
            json.loads(response.text)["data"]["apiKey"]
        )
        _logger.info(response.text)
        return response.text

    def delete_oliapi_access_key(self, api_key):
        """
        Delete an access key for OLI Cloud.

        :param api_key: The access key to delete

        :return string: Response text containing the success message or an error message
        """

        response = requests.delete(
            self.access_key_url,
            headers=self.update_headers({"Content-Type": "application/json"}),
            data=json.dumps({"apiKey": api_key}),
        )
        _logger.info(response.text)
        return response.text

    def login(self, refresh=False):
        """
        Log in to OLI Cloud using access key or credentials.

        :param refresh: bool to get refresh token

        :return status: bool indicating success or failure
        """

        req_result = ""
        if self.access_key:
            _logger.info("Logging into OLI API using access key")
            req_result = requests.get(
                self.dbs_url,
                headers=self.update_headers(
                    {"Content-Type": "application/x-www-form-urlencoded"}
                ),
            )
        else:
            _logger.info("Logging into OLI API using username and password")
            if refresh:
                body = {
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                    "client_id": "apiclient",
                }
            else:
                body = {
                    "username": self.credentials["username"],
                    "password": self.credentials["password"],
                    "grant_type": "password",
                    "client_id": "apiclient",
                }
            status = self.auth_status(body, req_result)
            return status

    def auth_status(self, body, req_result=None):
        """
        Posts authorization request to OLI Cloud.

        :param body: dictionary containing authorization data

        :return bool: bool indicating success or failure
        """

        if not req_result:
            req_result = requests.post(
                self.credentials["auth_url"],
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=body,
            )
        if req_result.status_code == 200:
            _logger.debug(f"Status code is {req_result.status_code}")
            _logger.info("Log in successful")
            if self.access_key:
                return True
            else:
                req_result = req_result.json()
                if "access_token" in req_result:
                    _logger.debug(f"Login access token: {req_result['access_token']}")
                    self.jwt_token = req_result["access_token"]
                    if "refresh_token" in req_result:
                        _logger.debug(
                            f"Login refresh token: {req_result['refresh_token']}"
                        )
                        self.refresh_token = req_result["refresh_token"]
                        return True
        else:
            raise ConnectionError(
                f" OLI login failed. Status code is {req_result.status_code}.\n"
            )
