import logging
from datetime import datetime, timezone
from typing import Dict, List

from atom_dl.feed_extractor.common import FeedInfoExtractor
from atom_dl.utils import PathTools as PT
from atom_dl.utils import append_list_to_json, load_dict_from_json, write_to_json


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

        # Serializing json
        logging.info('Serializing feed json')
        path_of_feed_json = PT.get_path_of_feed_json(feed_name)
        append_list_to_json(path_of_feed_json, latest_feed_list)
        logging.info('Appended latest feed json to %s', path_of_feed_json)

        # Writing only latest feed to file
        # path_of_latest_feed_json = PT.get_path_of_new_feed_json(feed_name)
        # logging.info(f'Saving latest feed json to {path_of_latest_feed_json}')
        # json_object = orjson.dumps(latest_feed_list, option=orjson.OPT_INDENT_2)  # pylint: disable=maybe-no-member
        # with open(path_of_latest_feed_json, "wb") as output_file:
        #     output_file.write(json_object)

    def update(self) -> List[Dict]:
        """
        RSS Feeds are normally sorted after published date. If we would like to update our feed based on the updated
        date we would need to download the whole feed all the time. Thats why we only download the updated feed based
        on the published date.
        """
        path_of_last_feed_update_json = PT.get_path_of_last_feed_update_json()
        until_dates = load_dict_from_json(path_of_last_feed_update_json)
        feed_name = self.feed_extractor.fie_key()
        logging.debug("Downloading %r latest feed", feed_name)
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
        self.update_feed_json(feed_name, latest_feed_list)

        until_dates[feed_name] = started_time_str
        write_to_json(path_of_last_feed_update_json, until_dates)

        logging.info('Downloaded %r latest feed', feed_name)
        return latest_feed_list
