import re
import time
import traceback

from datetime import datetime
from itertools import cycle
from typing import List, Dict

import asyncio
import aiohttp
import requests

from lxml import etree

from requests.exceptions import RequestException


class FeedDownloader:
    stdHeader = {
        'User-Agent': (
            'Mozilla/5.0 (Linux; Android 7.1.1; Moto G Play Build/NPIS26.48-43-2; wv) AppleWebKit/537.36'
            + ' (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.99 Mobile Safari/537.36'
        ),
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    xml_ns = {'atom': 'http://www.w3.org/2005/Atom'}
    default_time_format = "%Y-%m-%dT%H:%M:%S%z"  # works for atom and WordPress HTML
    size_pattern = re.compile(r"(\d+(?:[,.]\d+)?) ?([MGK]B|[mgk]b)")

    forbidden_hoster = [
        'megacache.net',
        'www.megacache.net',
        'oboom.com',
        'www.oboom.com',
        'share-online.biz',
        'www.share-online.biz',
        'terafile.co',
        'www.terafile.co',
        'comicmafia.to',
        'www.comicmafia.to',
    ]

    def __init__(self):
        self.sem = asyncio.Semaphore(10)
        self.until_date = datetime.fromtimestamp(0)

    def init(self, until_date: datetime):
        self.until_date = until_date

    async def fetch_page_and_extract(
        self, page_idx: int, link: str, extractor_method, result_list: List[Dict], status_dict: Dict
    ):
        async with self.sem:
            if status_dict['skip_after'] is not None and page_idx > status_dict['skip_after']:
                status_dict['skipped'] += 1
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(link, timeout=0) as response:
                    if response.ok:
                        page_text = await response.text()
                        result = extractor_method(page_idx, link, page_text, status_dict)
                        if result is not None:
                            if isinstance(result, list):
                                result_list += result
                            else:
                                result_list.append(result)
                            status_dict['done'] += 1
                        else:
                            print(f'\r\033[KFailed to extract {link}')
                            status_dict['failed'] += 1
                    else:
                        print(f'\r\033[KInvalid response ({response.status}) for {link}')
                        status_dict['failed'] += 1

    async def _real_fetch_all_pages_and_extract(
        self, page_links_list: List, extractor_method, result_list: List[Dict], status_dict: Dict
    ):
        try:
            await asyncio.gather(
                *[
                    self.fetch_page_and_extract(page_idx, page_link, extractor_method, result_list, status_dict)
                    for page_idx, page_link in enumerate(page_links_list)
                ],
                return_exceptions=True,
            )
        except Exception:
            traceback.print_exc()

    async def fetch_all_pages_and_extract(self, page_links_list: List, extractor_method, result_list: List[Dict]):
        max_links_num = len(page_links_list)
        status_dict = self.get_status_dict(max_links_num, 'Extracting metadata', 'All metadata are extracted!')

        await asyncio.wait(
            [
                asyncio.create_task(
                    self._real_fetch_all_pages_and_extract(page_links_list, extractor_method, result_list, status_dict)
                ),
                asyncio.create_task(self.display_status(status_dict)),
            ],
        )
        status_dict['stop'] = True

    def get_max_page_for(self, url, pattern):
        try:
            response = requests.get(
                url,
                headers=self.stdHeader,
                allow_redirects=True,
                timeout=60,
            )
        except RequestException as error:
            raise ConnectionError(f"Connection error: {str(error)}") from None

        result = pattern.findall(response.text)
        if len(result) <= 0:
            print(f'Error! Max page for {url} not found!')
            exit(1)

        return int(result[-1])

    async def crawl_atom_page_links(self, page_idx: int, link: str, page_links_list: List, status_dict: Dict):
        async with self.sem:
            if status_dict['skip_after'] is not None and page_idx > status_dict['skip_after']:
                status_dict['skipped'] += 1
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(link, timeout=0) as response:
                    if response.ok:
                        try:
                            xml = await response.read()
                            root = etree.fromstring(xml)

                            entry_nodes = root.xpath('//atom:entry', namespaces=self.xml_ns)
                            for idx, entry in enumerate(entry_nodes):
                                page_link_nodes = entry.xpath(
                                    './/atom:link[@rel="alternate"]/@href', namespaces=self.xml_ns
                                )
                                # updated_nodes = entry.xpath('.//atom:updated/text()', namespaces=self.xml_ns)
                                published_nodes = entry.xpath('.//atom:published/text()', namespaces=self.xml_ns)

                                parsed_published_date = None
                                if len(published_nodes) > 0:
                                    parsed_published_date = datetime.strptime(
                                        published_nodes[0], self.default_time_format
                                    )
                                else:
                                    print(f'Failed to parse date for entry on {link} idx {idx}')
                                    continue

                                if parsed_published_date <= self.until_date:
                                    if status_dict["skip_after"] is None or status_dict["skip_after"] > page_idx:
                                        status_dict['skip_after'] = page_idx
                                    continue

                                if len(page_link_nodes) == 0:
                                    print(f'Failed to find page link {link} on {link} idx {idx}')
                                    continue

                                page_link = page_link_nodes[0]
                                page_links_list.append(page_link)
                            status_dict['done'] += 1

                        except (FileNotFoundError, etree.XMLSyntaxError, ValueError) as error:
                            print(f'\r\033[KFailed to crawl {link}: {error}')
                            status_dict['failed'] += 1
                    else:
                        print(f'\r\033[KInvalid response ({response.status}) for {link}')
                        status_dict['failed'] += 1

    async def _real_crawl_all_atom_page_links(
        self, feed_url: str, max_page_num: int, page_links_list: List, status_dict: Dict
    ):
        try:
            await asyncio.gather(
                *[
                    self.crawl_atom_page_links(
                        page_idx, feed_url.format(page_id=page_idx), page_links_list, status_dict
                    )
                    for page_idx in range(1, int(max_page_num) + 1)
                ]
            )
        except Exception:
            traceback.print_exc()

    def get_status_dict(self, total: int, preamble: str, done_msg: str):
        return {
            'done': 0,
            'failed': 0,
            'skipped': 0,
            'total': total,
            'skip_after': None,
            'stop': False,
            'preamble': preamble,
            'done_msg': done_msg,
        }

    async def crawl_all_atom_page_links(self, feed_url: str, max_page_num: int, page_links_list: List):
        status_dict = self.get_status_dict(max_page_num, 'Crawling page links', 'All page links are crawled!')
        await asyncio.wait(
            [
                asyncio.create_task(
                    self._real_crawl_all_atom_page_links(feed_url, max_page_num, page_links_list, status_dict)
                ),
                asyncio.create_task(self.display_status(status_dict)),
            ],
        )
        status_dict['stop'] = True

    async def display_status(self, status_dict):
        spinner = cycle('/|\-')

        while (
            status_dict.get('done', 0) + status_dict.get('skipped', 0) + status_dict.get('failed', 0)
        ) < status_dict.get('total', 0) and not status_dict.get('stop', True):
            print(
                f"\r\033[K{status_dict.get('preamble', 'Done: ')}:"
                + f" {status_dict.get('done', 0):04}/{status_dict.get('total', 0):04}"
                + f" {next(spinner)}",
                end='',
            )
            await asyncio.sleep(0.3)
        print(
            f"\r\033[K{status_dict.get('done_msg', 'Done: ')} "
            + f" Successful: {status_dict.get('done', 0):04}/{status_dict.get('total', 0):04}"
            + f" Failed: {status_dict.get('failed', 0):04}/{status_dict.get('total', 0):04}"
            + f" Skipped: {status_dict.get('skipped', 0):04}/{status_dict.get('total', 0):04}"
        )

    @classmethod
    def fd_key(cls):
        """A string for getting the FeedDownloader with get_feed_downloader"""
        return cls.__name__[:-2]

    def download_latest_feed(self) -> List[Dict]:
        startTime = time.time()
        startTimeStr = time.strftime("%d.%m %H:%M:%S", time.localtime(startTime))
        print(f'{self.fd_key()} feed downloader started at {startTimeStr}')

        result_list = self._real_download_latest_feed()

        endTime = time.time()
        endTimeStr = time.strftime("%d%m %H:%M:%S", time.localtime(endTime))
        tookMs = endTime - startTime
        print(f'{self.fd_key()} feed downloader finished at {endTimeStr} and took {tookMs:.2f}s')

        return result_list

    def _real_download_latest_feed(self) -> List[Dict]:
        """Real download process. Redefine in subclasses."""
        raise NotImplementedError('This method must be implemented by subclasses')
