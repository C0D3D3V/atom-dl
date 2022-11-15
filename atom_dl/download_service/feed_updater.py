from datetime import datetime

from atom_dl.config_service.config_helper import ConfigHelper
from atom_dl.download_service.feed_downloader import gen_downloaders


class FeedUpdater:
    def __init__(
        self,
        storage_path: str,
        skip_cert_verify: bool,
    ):
        self.storage_path = storage_path
        self.skip_cert_verify = skip_cert_verify

    def update(self):
        config = ConfigHelper()
        until_date = config.get_last_crawled_date()
        all_downloaders = gen_downloaders()
        for downloader in all_downloaders:
            print(downloader.fd_key())
            # until_date = datetime.strptime("2022-11-13T18:51:01+00:00", "%Y-%m-%dT%H:%M:%S%z")
            until_date = datetime.fromtimestamp(0)
            downloader.init(until_date)
            downloader.download_feed()
