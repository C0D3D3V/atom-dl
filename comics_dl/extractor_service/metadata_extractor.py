import os
import lxml.html
import json
import asyncio
import aiofiles
from pathlib import Path


class MetadataExtrator:
    def __init__(self, storage_path: str, categories: [str]):
        self.storage_path = storage_path
        self.categories = categories
        self.all_metadata = {}
        self.sem = asyncio.Semaphore(25)

        for category in categories:
            self.all_metadata[category] = []

    async def page_metadata_extractor(self, category, file_path):
        async with self.sem:
            if os.path.isfile(file_path) and file_path.endswith('.html'):
                async with aiofiles.open(file_path, mode='r') as f:
                    html_content = await f.read()
                root = lxml.html.fromstring(html_content)

                books = root.xpath('//div[contains(@class, "post_box")]')
                for idx_book, book in enumerate(books):
                    title_nodes = book.xpath('.//div[@class="headline_area"]//h2//a')
                    date_nodes = book.xpath(
                        './/div[@class="headline_area"]//div[@class="byline small"]//span[@class="post_date"]'
                    )
                    description_nodes = book.xpath('.//div[@class="post_content"]//p')
                    crypt_download_link_nodes = book.xpath('.//div[@class="post_content"]//details//a')

                    if (
                        len(title_nodes) == 0
                        or len(date_nodes) == 0
                        or len(description_nodes) == 0
                        or len(crypt_download_link_nodes) <= 1
                    ):
                        print(f"Error in {file_path} for book {idx_book}")
                        continue_link_nodes = book.xpath('.//div[@class="post_content"]//a')
                        if len(continue_link_nodes) != 0:
                            print(f'You can find this collection here: {continue_link_nodes[0].get("href")}')
                        continue

                    title = title_nodes[0].text_content()
                    ibooks_link = title_nodes[0].get("href")
                    if title == '':
                        title = 'Title not defined'
                    upload_date = date_nodes[0].text
                    extra_info = description_nodes[0].text
                    description = ""
                    for idx, description_node in enumerate(description_nodes):
                        if idx < 2:
                            continue
                        if description_node.text_content() is not None and description_node.text_content() != '':
                            if idx > 2:
                                description += "\n"
                            description += description_node.text_content()
                    crypt_download_link = crypt_download_link_nodes[1].get("href")
                    if crypt_download_link is None:
                        print(f"Error in {file_path} for book {idx_book}, no crypto download link")
                        continue

                    image_link = "None"
                    image_link_nodes = book.xpath('.//a[@class="featured_image_link"]//img')
                    if len(image_link_nodes) != 0:
                        if image_link_nodes[0].get("srcset") is not None:
                            image_link = image_link_nodes[0].get("srcset").split(" ")[0]
                        else:
                            image_link = image_link_nodes[0].get("src")

                    self.all_metadata[category].append(
                        {
                            "title": title,
                            "upload_date": upload_date,
                            "extra_info": extra_info,
                            "description": description,
                            "crypt_download_link": crypt_download_link,
                            "image_link": image_link,
                            "ibooks_link": ibooks_link,
                        }
                    )
                print(f'Extracted: {file_path}')

    async def category_metadata_extractor(self, category: str):
        await asyncio.gather(
            *[
                asyncio.ensure_future(
                    self.page_metadata_extractor(category, str(Path(self.storage_path) / category / filename))
                )
                for filename in os.listdir(str(Path(self.storage_path) / category))
            ]
        )

    def run(self):
        loop = asyncio.get_event_loop()
        for category in self.categories:
            loop.run_until_complete(self.category_metadata_extractor(category))
            out_file = open(str(Path(self.storage_path) / category / 'metadata.json'), "w", encoding='utf-8')
            json.dump(self.all_metadata[category], out_file, indent=6)
            out_file.close()
        out_file = open(str(Path(self.storage_path) / 'combined_metadata.json'), "w", encoding='utf-8')
        json.dump(self.all_metadata, out_file, indent=6)
        out_file.close()
