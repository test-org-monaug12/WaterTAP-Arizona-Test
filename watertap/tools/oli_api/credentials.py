#################################################################################
# WaterTAP Copyright (c) 2020-2023, The Regents of the University of California,
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

import json
import requests
from pathlib import Path

from pyomo.common.dependencies import attempt_import

cryptography, cryptography_available = attempt_import("cryptography", defer_check=False)
if cryptography_available:
    from cryptography.fernet import Fernet


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
        if not self.test:
            self.login()

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

        :return boolean: status of user permission (to write encrypted config_file to disk)
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

    def _encrypt_credentials(self):
        """
        Basic encryption method for credentials
        """

        encryption_key = Fernet.generate_key()

        if not self.test:
            print(f"Your secret key is:\n{encryption_key.decode()}\nKeep it safe.\n")

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
            print(" Specify an access key:")
            for i in range(len(self.credentials["access_keys"])):
                print(f"{i}\t{self.credentials['access_keys'][i]}")
            return self.credentials["access_keys"][int(input(" "))]

    # TODO: improve header management for class
    def generate_oliapi_access_key(self):
        """
        Generate an access key for OLI Cloud.

        :return string: Response text containing the access key information or an error message.
        """

        if self.access_key:
            headers = {"authorization": "API-KEY " + self.access_key}
        else:
            headers = {"authorization": "Bearer " + self.jwt_token}
        headers.update({"Content-Type": "application/json"})
        payload = json.dumps({})
        response = requests.post(self.access_key_url, headers=headers, data=payload)
        self.credentials["access_keys"].append(
            json.loads(response.text)["data"]["apiKey"]
        )
        if not self.test:
            print(response.text)
        return response.text

    def delete_oliapi_access_key(self, api_key):
        """
        Delete an access key for OLI Cloud.

        :param api_key: The access key to delete.
        :return string: Response text containing the success message or an error message.
        """

        if self.access_key:
            headers = {"authorization": "API-KEY " + self.access_key}
        else:
            headers = {"authorization": "Bearer " + self.jwt_token}
        headers.update({"Content-Type": "application/json"})
        payload = json.dumps({"apiKey": api_key})
        response = requests.delete(self.access_key_url, headers=headers, data=payload)
        if not self.test:
            print(response.text)
        return response.text

    def login(self):
        """
        Login into user credentials for the OLI Cloud.

        :return boolean: True on success, False on failure
        """

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self.access_key:
            headers.update({"authorization": "API-KEY " + self.access_key})
            req_result = requests.get(self.dbs_url, headers=headers)
            if req_result.status_code == 200:
                if not self.test:
                    print(f"Status code is {req_result.status_code}.\n")
                return True
        else:
            body = {
                "username": self.credentials["username"],
                "password": self.credentials["password"],
                "grant_type": "password",
                "client_id": "apiclient",
            }
            req_result = requests.post(
                self.credentials["auth_url"], headers=headers, data=body
            )
            if req_result.status_code == 200:
                if not self.test:
                    print(f"Status code is {req_result.status_code}.\n")
                req_result = req_result.json()
                if "access_token" in req_result:
                    self.jwt_token = req_result["access_token"]
                    if "refresh_token" in req_result:
                        self.refresh_token = req_result["refresh_token"]
                        return True
        if not self.test:
            raise ConnectionError(
                f" OLI login failed. Status code is {req_result.status_code}."
            )
        else:
            return False

    def get_refresh_token(self):
        """
        Uses refresh token to update access token.

        :return boolean: True on success, False on failure
        """

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        body = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_id": "apiclient",
        }

        req_result = requests.post(
            self.credentials["auth_url"], headers=headers, data=body
        )
        if req_result.status_code == 200:
            if not self.test:
                print(f"Status code is {req_result.status_code}.\n")
            req_result = req_result.json()
            if bool(req_result):
                if "access_token" in req_result:
                    self.jwt_token = req_result["access_token"]
                    if "refresh_token" in req_result:
                        self.refresh_token = req_result["refresh_token"]
                        return True
        if not self.test:
            raise ConnectionError(
                f" OLI login failed. Status code is {req_result.status_code}.\n"
            )
        else:
            return False

    def request_auto_login(self, req_func=None):
        """
        Gets a new access token if the request returns with an expired token error.

        :param req_func: function to call

        :return boolean: True on success, False on failure
        """

        num_tries = 1
        while num_tries <= 3:
            if self.access_key:
                headers = {"authorization": "API-KEY " + self.access_key}
            else:
                headers = {"authorization": "Bearer " + self.jwt_token}
            req_result = req_func(headers)
            if req_result.status_code == 200:
                return json.loads(req_result.text)
            elif num_tries >= 1 and req_result.status_code == 400 and self.access_key:
                req_result = req_result.json()
                if not self.login():
                    raise RuntimeError(
                        "Login failed. Please check your API access key.\n"
                    )
            elif num_tries >= 1 and req_result.status_code == 401:
                req_result = req_result.json()
                if not self.get_refresh_token():
                    if not self.login():
                        break
            else:
                break
            num_tries = num_tries + 1

        if not self.test:
            raise ConnectionError(
                f" OLI request failed. Status code is {req_result.status_code}.\n"
            )
        else:
            return False
