import os
import re
import asyncio

from pathlib import Path
from datetime import date, timedelta

from atom_dl.config_service.config_helper import ConfigHelper
from atom_dl.download_service.feed_downloader.common import FeedDownloader


class ComicmafiaFD(FeedDownloader):
    stdHeader = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 7.1.1; Moto G Play Build/NPIS26.48-43-2; wv) AppleWebKit/537.36'
            + ' (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.99 Mobile Safari/537.36'
        ),
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    comicmafia_max_page_url = 'https://comicmafia.to/'
    comicmafia_max_page_patern = re.compile(r'<a class="page-numbers" href="https://comicmafia.to/page/(\d+)/">')

    # comicmafia_page_link_patern = re.compile(r'<a class="animsition-link" href="(https://comicmafia.to/[^"]+)">')

    async def download_comicmafia_pages(self, max_page_comicmafia: int):
        download_folder = str(Path(self.storage_path) / 'comicmafia')
        if not os.path.exists(download_folder):
            try:
                os.makedirs(download_folder)
            except FileExistsError:
                pass

        await asyncio.gather(
            *[
                self.fetch_page(
                    f'https://comicmafia.to/feed/atom/?paged={page_id}',
                    str(Path(self.storage_path) / 'comicmafia' / f'{page_id:04}.rss'),
                )
                for page_id in range(1, int(max_page_comicmafia) + 1)
            ]
        )

    def _real_download_feed(self):
        loop = asyncio.get_event_loop()
        # Downlaod comicmafia.to pages
        # On the wordpress side there are 40 entries per page but in rss there are only 10
        web_max_page_comicmafia = self.get_max_page_for(self.comicmafia_max_page_url, self.comicmafia_max_page_patern)
        max_page_comicmafia = web_max_page_comicmafia * 4

        loop.run_until_complete(self.download_comicmafia_pages(max_page_comicmafia))

        one_day_before = date.today() - timedelta(days=1)
        print(f'Setting last date to {one_day_before.strftime("%Y-%m-%d")}')
        config = ConfigHelper()
        config.set_property('last_crawled_date', one_day_before.strftime("%Y-%m-%d"))
