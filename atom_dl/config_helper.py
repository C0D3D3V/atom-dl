import os
import json

from typing import Dict

from atom_dl.utils import PathTools


class Config:
    """
    Handles the saving, formatting and loading of the local configuration.
    """

    def __init__(self):
        self._whole_config = {}
        self.config_path = PathTools.get_path_of_config_json()
        if self.is_present():
            self.load()
        else:
            self._save()

    def is_present(self) -> bool:
        # Tests if a configuration file exists
        return os.path.isfile(self.config_path)

    def load(self):
        # Opens the configuration file and parse it to a JSON object
        try:
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                config_raw = config_file.read()
                self._whole_config = json.loads(config_raw)
        except IOError:
            raise ValueError(f'No config found in "{self.config_path}"!')

    def _save(self):
        # Saves the JSON object back to file
        with open(self.config_path, 'w+', encoding='utf-8') as config_file:
            config_formatted = json.dumps(self._whole_config, indent=4)
            config_file.write(config_formatted)

    def get_property(self, key: str) -> any:
        # returns a property if configured
        try:
            return self._whole_config[key]
        except KeyError:
            raise ValueError(f'The Property {key} is not yet configured!')

    def set_property(self, key: str, value: any):
        # sets a property in the JSON object
        self._whole_config.update({key: value})
        self._save()

    def remove_property(self, key):
        # removes a property from the JSON object
        self._whole_config.pop(key, None)
        #                           ^ behavior if the key is not present
        self._save()

    # ---------------------------- GETTERS ------------------------------------

    def get_my_jd_username(self) -> str:
        return self.get_property('my_jd_username')

    def get_my_jd_password(self) -> str:
        return self.get_property('my_jd_password')

    def get_my_jd_device(self) -> str:
        return self.get_property('my_jd_device')

    def get_last_feed_update_dates(self) -> Dict:
        try:
            return self.get_property('last_feed_update_dates')
        except ValueError:
            return {}

    def get_last_feed_job_definitions(self) -> Dict:
        try:
            return self.get_property('last_feed_job_definitions')
        except ValueError:
            return []

    # ---------------------------- SETTERS ------------------------------------

    def set_last_feed_update_dates(self, feed: str, date_Str: str):
        last_feed_update_dates = self.get_last_feed_update_dates()
        last_feed_update_dates[feed] = date_Str
        self.set_property('last_feed_update_dates', last_feed_update_dates)
