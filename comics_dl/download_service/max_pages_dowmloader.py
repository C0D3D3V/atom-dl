import os
import re
import asyncio
import aiohttp

from pathlib import Path


class MaxPagesDownloader:
    max_page_patern = re.compile(r"Seite 2 von (\d+)")

    def __init__(
        self,
        storage_path: str,
        categories: [str],
    ):
        self.storage_path = storage_path
        self.categories = categories
        self.max_pages = {}
        for category in categories:
            self.max_pages[category] = 0
        self.sem = asyncio.Semaphore(5)

    async def fetch_max_pages(self, link, category):
        async with self.sem:
            async with aiohttp.ClientSession() as session:
                async with session.get(link, timeout=0) as response:
                    try:
                        html = await response.read()

                        result = self.max_page_patern.search(html.decode(encoding='utf-8'))
                        try:
                            max_page = int(result.group(1))
                        except Exception as e:
                            if category in ['zeitungen', 'magazine-zeitschriften']:
                                max_page = 100
                            else:
                                max_page = 0
                                print(link, category, e)

                        self.max_pages[category] = max_page
                        print(f'Loaded max pages of {category}: {max_page}')
                    except FileNotFoundError:
                        print(f'Failed to load max pages of {category}')

    async def get_max_pages_numbers(self):
        await asyncio.gather(
            *[
                self.fetch_max_pages(
                    f'https://ibooks.to/cat/ebooks/{category}/page/2/',
                    category,
                )
                for category in self.categories
            ]
        )

    async def fetch_page(self, session, link, directory_path, file_path, category):
        async with session.get(link, timeout=0) as response:
            try:
                if not os.path.exists(directory_path):
                    try:
                        os.makedirs(directory_path)
                    except FileExistsError:
                        pass

                with open(file_path, 'wb') as fd:
                    async for chunk in response.content.iter_chunked(8192):
                        fd.write(chunk)

                print(f'Downlaoded {link}')
            except FileNotFoundError:
                print(f'Failed to download {link}')

    async def download_all_pages(self):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *[
                    self.fetch_page(
                        session,
                        f'https://ibooks.to/cat/ebooks/{category}/page/{page_id}',
                        str(Path(self.storage_path) / category),
                        str(Path(self.storage_path) / category / f'{page_id:04}.html'),
                        category,
                    )
                    for category in self.categories
                    for page_id in range(1, int(self.max_pages[category]) + 1)
                ]
            )

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.get_max_pages_numbers())
        return self.max_pages
