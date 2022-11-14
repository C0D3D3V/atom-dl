import re
import os
import json
import html

from pathlib import Path
from urllib.parse import urlparse

import asyncio
import aiofiles
import lxml.html

from lxml import etree


class MetadataExtrator:
    xml_ns = {'atom': 'http://www.w3.org/2005/Atom'}
    issues_patern = re.compile(r'(\d+-\d+)')
    issue_patern = re.compile(r'( \d+)$')

    def __init__(self, storage_path: str, categories: [str]):
        self.storage_path = storage_path
        self.categories = categories
        self.all_metadata = {}
        self.sem = asyncio.Semaphore(25)

        for category in categories:
            self.all_metadata[category] = []

    def get_key(self, name: str):
        def replace_insane(char):
            if char == '?' or ord(char) < 32 or ord(char) == 127:
                return ''
            if char in '1234567890-\\/|*<>":!&\'()[]{}$;`^,#\n' or char.isspace() or ord(char) > 127:
                return ''
            return char

        return ''.join(map(replace_insane, name))

    async def comixload_page_metadata_extractor(self, category, file_path):
        async with self.sem:
            if os.path.isfile(file_path) and file_path.endswith('.html'):
                async with aiofiles.open(file_path, mode='r') as f:
                    html_content = await f.read()
                root = lxml.html.fromstring(html_content)

                entry = root.xpath('//div[@id="content" and @role="main"]//article')
                if len(entry) != 1:
                    print(f"Error in {file_path}, no comic entry found!")
                    return
                comic = entry[0]
                title_nodes = comic.xpath('.//h1/text()')
                date_nodes = comic.xpath('.//time/@datetime')
                description_nodes = comic.xpath('.//div[@id="squelch-taas-toggle-shortcode-content-0"]//p/text()')
                crypt_download_link_nodes = comic.xpath('.//center//a/@href')
                crypt_download_link_alt_nodes = comic.xpath(
                    './/div[contains(@class, "squelch-taas-toggle-shortcode-content")]/text()'
                )
                image_link_nodes = comic.xpath('.//img[@width][@height]/@src')
                extra_info_nodes = comic.xpath('.//pre/text()')
                page_link_node = comic.xpath('.//a[@rel="bookmark"]/@href')

                if len(title_nodes) == 0:
                    print(f"Error in {file_path}, no title found")
                    return

                title = title_nodes[0]
                published_date = None
                if len(date_nodes) >= 1:
                    published_date = date_nodes[0]
                updated_date = None
                if len(date_nodes) >= 2:
                    updated_date = date_nodes[1]
                description = None
                if len(description_nodes) > 0:
                    description = "\n".join(line for line in description_nodes)
                    description = description.strip()
                    if description == '':
                        description = None

                space_info = None
                issues_info = None
                if len(extra_info_nodes) >= 1:
                    extra_info = extra_info_nodes[0]
                    if description is None:
                        description = extra_info
                    else:
                        description += '\n' + extra_info
                    description.strip()
                    for line in extra_info.split('\n'):
                        if line.startswith('Size'):
                            space_info = line.split('.')[-1].strip()
                            space_info = space_info.split(' in')[0]
                        if line.startswith('Issues'):
                            issues_info = line.split('.')[-1].replace(' ', '').strip()
                            if issues_info in ['', '-']:
                                issues_info = None

                crypt_download_links = []
                for link in crypt_download_link_nodes + crypt_download_link_alt_nodes:
                    if link not in crypt_download_links:
                        clean_link = link.strip()
                        if not clean_link.startswith('http'):
                            continue
                        if urlparse(clean_link).netloc not in [
                            'megacache.net',
                            'www.megacache.net',
                            'oboom.com',
                            'www.oboom.com',
                            'share-online.biz',
                            'www.share-online.biz',
                            'terafile.co',
                            'www.terafile.co',
                        ]:
                            crypt_download_links.append(clean_link)
                if len(crypt_download_links) == 0:
                    print(f"Error in {file_path} for {title}, no crypt link found")
                    return

                image_link = None
                if len(image_link_nodes) >= 1:
                    image_link = image_link_nodes[0]
                page_link = None
                if len(page_link_node) >= 1:
                    page_link = page_link_node[0]

                title = title.replace('– komplett', '')
                title = title.replace('– complete', '')
                title = title.strip()

                key = title.split('(')[0]
                key = self.get_key(key)
                key = key.strip()

                self.all_metadata[category].append(
                    {
                        "title": title,
                        "key": key,
                        "published_date": published_date,
                        "updated_date": updated_date,
                        "description": description,
                        "crypt_download_links": crypt_download_links,
                        "image_link": image_link,
                        "space_info": space_info,
                        "issues_info": issues_info,
                        "page_link": page_link,
                    }
                )
                print(f'Extracted: {file_path}')

    async def comixload_metadata_extractor(self):
        await asyncio.gather(
            *[
                asyncio.ensure_future(
                    self.comixload_page_metadata_extractor(
                        category, str(Path(self.storage_path) / 'comixload' / category / filename)
                    )
                )
                for category in self.categories
                for filename in os.listdir(str(Path(self.storage_path) / 'comixload' / category))
            ]
        )

    async def comicmafia_page_metadata_extractor(self, file_path):
        async with self.sem:
            if os.path.isfile(file_path) and file_path.endswith('.rss'):
                async with aiofiles.open(file_path, mode='rb') as f:
                    xml_content = await f.read()

                root = etree.fromstring(xml_content)

                entries = root.xpath('//atom:entry', namespaces=self.xml_ns)

                if len(entries) == 0:
                    print(f"Error in {file_path}, no comic entry found!")
                    return
                for comic_idx, comic in enumerate(entries):
                    title_nodes = comic.xpath('.//atom:title/text()', namespaces=self.xml_ns)

                    if len(title_nodes) == 0:
                        print(f"Error in {file_path}, no title found")
                        return

                    updated_date_nodes = comic.xpath('.//atom:updated/text()', namespaces=self.xml_ns)
                    published_date_nodes = comic.xpath('.//atom:published/text()', namespaces=self.xml_ns)
                    page_link_node = comic.xpath('.//atom:link[@rel="alternate"]/@href', namespaces=self.xml_ns)

                    html_content_nodes = comic.xpath('.//atom:content/text()', namespaces=self.xml_ns)

                    if len(html_content_nodes) == 0:
                        print(f"Error in {file_path} for idx {comic_idx}, no conent found")
                        continue
                    html_content = html_content_nodes[0].strip()
                    content_root = lxml.html.fromstring(html_content)

                    image_link_nodes = content_root.xpath('//div[@class="wp-block-image"]//img/@src')
                    image_link_srcset_nodes = content_root.xpath('//div[@class="wp-block-image"]//img/@srcset')

                    crypt_download_link_nodes = content_root.xpath('//a[contains(@rel, "noopener")]/@href')
                    extra_info_nodes = content_root.xpath('//a[contains(@rel, "noopener")]/text()')

                    title = html.unescape(title_nodes[0])
                    published_date = None
                    if len(published_date_nodes) >= 1:
                        published_date = published_date_nodes[0]
                    updated_date = None
                    if len(updated_date_nodes) >= 1:
                        updated_date = updated_date_nodes[0]
                    crypt_download_links = []
                    for link in crypt_download_link_nodes:
                        if link not in crypt_download_links:
                            clean_link = link.strip()
                            if not clean_link.startswith('http'):
                                continue
                            if urlparse(clean_link).netloc not in [
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
                            ]:
                                crypt_download_links.append(clean_link)
                    if len(crypt_download_links) == 0:
                        print(f"Error in {file_path} for {title}, no crypt link found")
                        return

                    image_link = None
                    if len(image_link_nodes) >= 1:
                        image_link = image_link_nodes[0]
                    elif len(image_link_srcset_nodes) >= 1:
                        image_link = image_link_srcset_nodes[0].split(' ')[0]
                    space_info = None
                    if len(extra_info_nodes) >= 1:
                        for extra_info_node in extra_info_nodes:
                            if extra_info_node.startswith('Download'):
                                space_split = extra_info_node.split('(')
                                if len(space_split) >= 2:
                                    space_info = space_split[1].split(')')[0]
                                    space_info = space_info.split(' in')[0]
                                    break
                    page_link = None
                    if len(page_link_node) >= 1:
                        page_link = page_link_node[0]

                    category = 'comic'
                    if title.lower().find('manga') >= 0:
                        category = 'manga'

                    if title.find('(Englisch)') >= 0:
                        continue
                    title = title.split('(')[0]
                    title = title.strip()

                    issue_min = None
                    issue_max = None
                    issues_info_matches = self.issues_patern.findall(title)
                    issue_title = title.split(' – ')[0]
                    issue_info_matches = self.issue_patern.findall(issue_title)
                    if issues_info_matches is not None and len(issues_info_matches) > 0:
                        issues_info_text = issues_info_matches[0]
                        issues_info_begin = int(issues_info_text.split('-')[0])
                        issues_info_end = int(issues_info_text.split('-')[1])
                        issue_min = issues_info_begin
                        issue_max = issues_info_end
                    elif issue_info_matches is not None and len(issue_info_matches) > 0:
                        issue_min = int(issue_info_matches[0])
                        issue_max = int(issue_info_matches[0])

                    key = self.get_key(title.split(' – ')[0])
                    key = key.strip()

                    if category in self.categories:
                        self.all_metadata[category].append(
                            {
                                "title": title,
                                "key": key,
                                "published_date": published_date,
                                "updated_date": updated_date,
                                "description": None,
                                "crypt_download_links": crypt_download_links,
                                "image_link": image_link,
                                "space_info": space_info,
                                "issue_min": issue_min,
                                "issue_max": issue_max,
                                "page_link": page_link,
                            }
                        )
                print(f'Extracted: {file_path}')

    async def comicmafia_metadata_extractor(self):
        await asyncio.gather(
            *[
                asyncio.ensure_future(
                    self.comicmafia_page_metadata_extractor(str(Path(self.storage_path) / 'comicmafia' / filename))
                )
                for filename in os.listdir(str(Path(self.storage_path) / 'comicmafia'))
            ]
        )

    def run(self):
        loop = asyncio.get_event_loop()

        # Extract comicmafia
        loop.run_until_complete(self.comicmafia_metadata_extractor())

        # Extract comixload
        # loop.run_until_complete(self.comixload_metadata_extractor())

        all_metadata_sorted = {}
        for category in self.categories:
            to_sort = self.all_metadata[category]
            all_metadata_sorted[category] = sorted(
                to_sort,
                key=lambda k: (
                    k['key'],
                    100000 if k['issue_min'] is None else k['issue_min'],
                    k['title'],
                    k['updated_date'],
                ),
            )

        out_file = open(str(Path(self.storage_path) / 'metadata.json'), "w", encoding='utf-8')
        json.dump(all_metadata_sorted, out_file, indent=6)
        out_file.close()
