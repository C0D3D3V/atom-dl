import os
import re
import asyncio

from pathlib import Path
from datetime import date, datetime, timedelta

import aiohttp

from lxml import etree

from atom_dl.config_service.config_helper import ConfigHelper
from atom_dl.download_service.feed_downloader.common import FeedDownloader


class ComixloadFD(FeedDownloader):

    comixload_max_page_url_german_comics = 'https://comix-load.in/category/comic/german-comics/'
    comixload_max_page_patern_german_comics = re.compile(
        r"<a href='https://comix-load.in/category/comic/german-comics/page/(\d+)/'>"
    )
    comixload_feed_url_german_comics = 'https://comix-load.in/category/comic/german-comics/feed/?feed=atom&paged='

    comixload_max_page_url_german_manga = 'https://comix-load.in/category/manga/german-manga/'
    comixload_max_page_patern_german_manga = re.compile(
        r"<a href='https://comix-load.in/category/manga/german-manga/page/(\d+)/'>"
    )
    comixload_feed_url_german_manga = 'https://comix-load.in/category/comic/german-manga/feed/?feed=atom&paged='

    comixload_max_page_url_english_comics = 'https://comix-load.in/category/comic/english-comics/'
    comixload_max_page_patern_english_comics = re.compile(
        r"<a href='https://comix-load.in/category/comic/english-comics/page/(\d+)/'>"
    )
    comixload_feed_url_english_comics = 'https://comix-load.in/category/comic/english-comics/feed/?feed=atom&paged='

    def __init__(
        self,
        storage_path: str,
        until_date: datetime,
        skip_cert_verify: bool,
    ):
        self.categories = ['comic', 'manga']
        self.comixload_page_links = {}
        for category in self.categories:
            self.comixload_page_links[category] = []

        super().__init__(storage_path, until_date, skip_cert_verify)

    async def crawl_comixload_page_links(self, link: str, category: str, is_english: bool):
        # crawl english comics only if it contains "Art of"
        async with self.sem:
            async with aiohttp.ClientSession() as session:
                async with session.get(link, timeout=0) as response:
                    if response.ok:
                        try:
                            xml = await response.read()
                            root = etree.fromstring(xml)

                            comic_links = root.xpath('//atom:entry//atom:link/@href', namespaces=self.xml_ns)

                            if is_english:
                                for comic_link in comic_links:
                                    if comic_link.find('art-of') >= 0:
                                        self.comixload_page_links[category].append(comic_link)
                            else:
                                for comic_link in comic_links:
                                    self.comixload_page_links[category].append(comic_link)

                            print(f'Crawled {link}')
                        except FileNotFoundError:
                            print(f'Failed to crawl {link}')

    async def crawl_all_comixload_page_links(
        self, feed_url: str, category: str, max_page_comixload: int, is_english: bool
    ):
        await asyncio.gather(
            *[
                self.crawl_comixload_page_links(
                    f'{feed_url}{page_id}',
                    category,
                    is_english,
                )
                for page_id in range(1, int(max_page_comixload) + 1)
            ]
        )

    async def download_comixload_pages(self):
        for category in self.categories:
            download_folder = str(Path(self.storage_path) / 'comixload' / category)
            if not os.path.exists(download_folder):
                try:
                    os.makedirs(download_folder)
                except FileExistsError:
                    pass

        await asyncio.gather(
            *[
                self.fetch_page(
                    page_link,
                    str(Path(self.storage_path) / 'comixload' / category / f'{page_id:04}.html'),
                )
                for category in self.categories
                for page_id, page_link in enumerate(self.comixload_page_links[category])
            ]
        )

    def _real_download_feed(self):
        loop = asyncio.get_event_loop()
        # Downlaod comix-load.in pages
        # On the wordpress side there are only 5 entries per page but in rss there are 50

        # comic
        web_max_page_comixload_german_comics = self.get_max_page_for(
            self.comixload_max_page_url_german_comics, self.comixload_max_page_patern_german_comics
        )
        max_page_comixload_german_comics = int(web_max_page_comixload_german_comics / 10) + 1

        loop.run_until_complete(
            self.crawl_all_comixload_page_links(
                self.comixload_feed_url_german_comics, 'comic', max_page_comixload_german_comics, False
            )
        )

        web_max_page_comixload_english_comics = self.get_max_page_for(
            self.comixload_max_page_url_english_comics, self.comixload_max_page_patern_english_comics
        )
        max_page_comixload_english_comics = int(web_max_page_comixload_english_comics / 10) + 1

        loop.run_until_complete(
            self.crawl_all_comixload_page_links(
                self.comixload_feed_url_english_comics, 'comic', max_page_comixload_english_comics, True
            )
        )

        # manga
        web_max_page_comixload_german_manga = self.get_max_page_for(
            self.comixload_max_page_url_german_manga, self.comixload_max_page_patern_german_manga
        )
        max_page_comixload_german_manga = int(web_max_page_comixload_german_manga / 10) + 1

        loop.run_until_complete(
            self.crawl_all_comixload_page_links(
                self.comixload_feed_url_german_manga, 'manga', max_page_comixload_german_manga, False
            )
        )

        loop.run_until_complete(self.download_comixload_pages())

        one_day_before = date.today() - timedelta(days=1)
        print(f'Setting last date to {one_day_before.strftime("%Y-%m-%d")}')
        config = ConfigHelper()
        config.set_property('last_crawled_date', one_day_before.strftime("%Y-%m-%d"))
