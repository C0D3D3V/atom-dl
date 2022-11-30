import json

from typing import List, Dict
from datetime import datetime, timezone

from atom_dl.utils.logger import Log
from atom_dl.utils.path_tools import PathTools
from atom_dl.config_helper import Config
from atom_dl.feed_extractor.common import FeedInfoExtractor


class FeedUpdater:
    default_time_format = "%Y-%m-%dT%H:%M:%S%z"  # works for atom and WordPress HTML

    def __init__(
        self,
        feed_extractor: FeedInfoExtractor,
    ):
        self.feed_extractor = feed_extractor

    def update_feed_json(self, feed_name: str, latest_feed_list: List[Dict]):
        if len(latest_feed_list) == 0:
            return

        path_of_feed_json = PathTools.get_path_of_new_feed_json(feed_name)

        # Serializing json
        print('Serializing feed json')
        json_object = json.dumps(latest_feed_list, indent=4)  # ensure_ascii=False

        # Writing to sample.json
        print(f'Saving latest feed json to {path_of_feed_json}')
        with open(path_of_feed_json, "w", encoding='utf-8') as output_file:
            output_file.write(json_object)

    def update(self) -> List[Dict]:
        """
        RSS Feeds are normally sorted after published date. If we would like to update our feed based on the updated
        date we would need to download the whole feed all the time. Thats why we only download the updated feed based
        on the published date.
        """
        config = Config()
        until_dates = config.get_last_feed_update_dates()
        feed_name = self.feed_extractor.fie_key()
        Log.debug(f"Downloading {feed_name} latest feed")
        started_time = datetime.now(timezone.utc)
        started_time_str = datetime.strftime(started_time, self.default_time_format)

        # get last feed update date
        if feed_name in until_dates:
            until_date = datetime.strptime(until_dates[feed_name], self.default_time_format)
        else:
            # download everything
            until_date = datetime.strptime("1970-01-01T01:00:00+00:00", self.default_time_format)

        self.feed_extractor.init(until_date)
        latest_feed_list = self.feed_extractor.download_latest_feed()

        # update json
        # self.update_feed_json(feed_name, latest_feed_list)

        # config.set_last_feed_update_dates(feed_name, started_time_str)

        Log.success(f'Downloaded {feed_name} latest feed')
        return latest_feed_list
