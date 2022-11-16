import json

from datetime import datetime, timezone

from atom_dl.utils.path_tools import PathTools
from atom_dl.config_service.config_helper import ConfigHelper
from atom_dl.download_service.feed_downloader import gen_downloaders


class FeedUpdater:
    default_time_format = "%Y-%m-%dT%H:%M:%S%z"  # works for atom and WordPress HTML

    def __init__(
        self,
        storage_path: str,
        skip_cert_verify: bool,
    ):
        self.storage_path = storage_path
        self.skip_cert_verify = skip_cert_verify

    def update_feed_json(self, downloader_name, latest_feed_list):
        if len(latest_feed_list) == 0:
            return

        path_of_feed_json = PathTools.get_path_of_new_feed_json(downloader_name)

        # Serializing json
        print('Serializing feed json')
        json_object = json.dumps(latest_feed_list, indent=4)  # ensure_ascii=False

        # Writing to sample.json
        print(f'Saving latest feed json to {path_of_feed_json}')
        with open(path_of_feed_json, "w", encoding='utf-8') as output_file:
            output_file.write(json_object)

    def update(self):
        """
        RSS Feeds are normally sorted after published date. If we would like to update our feed based on the updated
        date we would need to download the whole feed all the time. Thats why we only download the updated feed based
        on the published date.
        """
        config = ConfigHelper()
        until_dates = config.get_last_feed_update_dates()
        all_downloaders = gen_downloaders()
        for downloader in all_downloaders:
            downloader_name = downloader.fd_key()
            print(downloader_name)
            started_time = datetime.now(timezone.utc)
            started_time_str = datetime.strftime(started_time, self.default_time_format)

            # get last feed update date
            if downloader_name in until_dates:
                until_date = datetime.strptime(until_dates[downloader_name], self.default_time_format)
            else:
                # download everything
                until_date = datetime.strptime("1970-01-01T01:00:00+00:00", self.default_time_format)

            downloader.init(until_date)
            latest_feed_list = downloader.download_latest_feed()

            # update json
            self.update_feed_json(downloader_name, latest_feed_list)

            config.set_last_feed_update_dates(downloader_name, started_time_str)
