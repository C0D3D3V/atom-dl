import re
import html
import asyncio

from typing import List, Dict
from datetime import datetime
from urllib.parse import urlparse

import lxml.html

from lxml import etree

from atom_dl.feed_extractor.common import FeedInfoExtractor


class ComicmafiaFIE(FeedInfoExtractor):

    max_page_url = 'https://comicmafia.to/'
    max_page_pattern = re.compile(r'<a class="page-numbers" href="https://comicmafia.to/page/(\d+)/">')
    feed_url = 'https://comicmafia.to/feed/atom/?paged={page_id}'

    def page_metadata_extractor(self, page_idx: int, page_link: str, page_text: str, status_dict: Dict):
        try:
            root = etree.fromstring(bytes(page_text, encoding='utf8'))
        except ValueError as error:
            print(f"\r\033[KError in {page_link}, could not parse xml! {error}")
            return None

        entry_nodes = root.xpath('//atom:entry', namespaces=self.xml_ns)
        if len(entry_nodes) == 0:
            print(f"\r\033[KError in {page_link}, no entry found!")
            return None

        result_list = []
        for idx, entry in enumerate(entry_nodes):
            title_nodes = entry.xpath('.//atom:title/text()', namespaces=self.xml_ns)
            updated_date_nodes = entry.xpath('.//atom:updated/text()', namespaces=self.xml_ns)
            published_date_nodes = entry.xpath('.//atom:published/text()', namespaces=self.xml_ns)
            page_link_nodes = entry.xpath('.//atom:link[@rel="alternate"]/@href', namespaces=self.xml_ns)
            page_id_nodes = entry.xpath('.//atom:id/text()', namespaces=self.xml_ns)
            category_nodes = entry.xpath('.//atom:category/@term', namespaces=self.xml_ns)
            html_content_nodes = entry.xpath('.//atom:content/text()', namespaces=self.xml_ns)

            if len(html_content_nodes) == 0:
                print(f"Error in {page_link} for idx {idx}, no content found")
                continue
            html_content = html_content_nodes[0].strip()
            content_root = lxml.html.fromstring(html_content)

            image_link_nodes = content_root.xpath('.//div[@class="wp-block-image"]//img/@src')
            image_link_srcset_nodes = content_root.xpath('//div[@class="wp-block-image"]//img/@srcset')
            download_link_nodes = content_root.xpath('.//a[@target="_blank"]/@href')
            extra_info_nodes = content_root.xpath('//a[@target="_blank"]/text()')
            package_content_list_nodes = content_root.xpath('.//strong//span')
            description = None
            if len(package_content_list_nodes) > 0:
                description = '\n\n'.join(
                    '\n'.join([elm.strip() for elm in description_node.xpath('.//text()')])
                    for description_node in package_content_list_nodes
                )

            if len(title_nodes) == 0:
                print(f"\r\033[KError in {page_link} idx {idx}, no title found")
                continue
            title = html.unescape(title_nodes[0])

            published_date = None
            if len(published_date_nodes) >= 1:
                published_date = published_date_nodes[0]
            updated_date = published_date
            if len(updated_date_nodes) >= 1:
                updated_date = updated_date_nodes[0]

            # Stop downloading old feed (that we have already downloaded)
            parsed_published_date = datetime.strptime(published_date, self.default_time_format)
            if parsed_published_date <= self.until_date:
                if status_dict["skip_after"] is None or status_dict["skip_after"] > page_idx:
                    status_dict["skip_after"] = page_idx
                continue

            image_link = None
            if len(image_link_nodes) >= 1:
                image_link = image_link_nodes[0]
            elif len(image_link_srcset_nodes) >= 1:
                image_link = image_link_srcset_nodes[0].split(' ')[0]
            if image_link is not None and image_link.startswith('/'):
                image_link = 'https://comicmafia.to' + image_link

            download_links = []
            for link in download_link_nodes:
                if link not in download_links:
                    clean_link = link.strip()
                    if not clean_link.startswith('http'):
                        continue
                    if urlparse(clean_link).netloc not in self.forbidden_hoster:
                        download_links.append(clean_link)
            if len(download_links) == 0:
                print(f"\r\033[KError in {page_link} idx {idx} for {title}, no download link found")
                continue

            that_page_link = None
            if len(page_link_nodes) > 0:
                that_page_link = page_link_nodes[0]

            page_id = None
            if len(page_id_nodes) > 0:
                page_id = page_id_nodes[0]

            size_info = None
            size_in_mb = None
            if len(extra_info_nodes) >= 1:
                for extra_info_node in extra_info_nodes:
                    if extra_info_node.startswith('Download'):  # Download Nitroflare (950 MB)
                        space_split = extra_info_node.split('(')
                        if len(space_split) >= 2:
                            size_info = space_split[1].split(')')[0]
                            only_size = size_info.split('in')[0]  # 25338 MB in 1GB-Parts
                            only_size = only_size.replace(' ', '')  # remove spaces
                            only_size = only_size.upper().strip()
                            if only_size.endswith('MB'):
                                only_size = only_size[:-2]
                                size_in_mb = int(only_size)
                            break

            result_list.append(
                {
                    "title": title,
                    "page_link": that_page_link,
                    "page_id": page_id,
                    "published_date": published_date,
                    "updated_date": updated_date,
                    "description": description,
                    "image_link": image_link,
                    "size_info": size_info,
                    "size_in_mb": size_in_mb,
                    "download_links": download_links,
                    "categories": category_nodes,
                    "extractor_key": self.fie_key(),
                }
            )
        return result_list

    def _real_download_latest_feed(self) -> List[Dict]:
        loop = asyncio.get_event_loop()

        # On the WordPress side there are 40 entries per page but in rss there are only 10
        max_page = self.get_max_page_for(self.max_page_url, self.max_page_pattern) * 4

        # Collect all links that needs to be downloaded for metadata extraction
        page_links_list = []
        for page_id in range(1, max_page + 1):
            page_links_list.append(self.feed_url.format(page_id=page_id))

        # Download and extract all pages
        result_list = []
        loop.run_until_complete(
            self.fetch_all_pages_and_extract(page_links_list, self.page_metadata_extractor, result_list)
        )

        return result_list
