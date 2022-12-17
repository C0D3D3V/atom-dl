import asyncio
import re

from typing import List, Dict
from urllib.parse import urlparse

import lxml.html

from atom_dl.feed_extractor.common import FeedInfoExtractor


class LanguagelearningFIE(FeedInfoExtractor):
    max_page_url = 'https://languagelearning.site/'
    max_page_pattern = re.compile(r'<a class="page-numbers" href="https://languagelearning.site/page/(\d+)/">')
    feed_url = 'https://languagelearning.site/feed/atom/?paged={page_id}'

    def page_metadata_extractor(self, page_idx: int, page_link: str, page_text: str, status_dict: Dict):
        """
        Date filtering is done in crawl_all_atom_page_links
        thats why we do not need to use page_idx and status_dict here
        """
        try:
            root = lxml.html.fromstring(page_text)
        except ValueError as error:
            print(f"\r\033[KError in {page_link}, could not parse html! {error}")
            return None

        page_id_nodes = root.xpath('//link[@rel="shortlink"]/@href')
        page_id = None
        if len(page_id_nodes) > 0:
            page_id = page_id_nodes[0]

        entry_nodes = root.xpath('//main//article//div[@class="inside-article"]')
        if len(entry_nodes) != 1:
            print(f"\r\033[KError in {page_link}, no entry found!")
            return None

        entry = entry_nodes[0]
        title_nodes = entry.xpath('.//h1/text()')
        updated_date_nodes = entry.xpath('.//time[@class="updated"]/@datetime')
        published_date_nodes = entry.xpath('.//time[@class="entry-date published"]/@datetime')
        image_link_nodes = entry.xpath('.//img[@width][@height]/@src')
        description_nodes = entry.xpath('.//blockquote//p')
        extra_info_nodes = entry.xpath('.//div[@class="entry-content"]//p//strong')

        download_link_nodes = entry.xpath('.//a[@target="_blank"]/@href')
        category_nodes = entry.xpath('.//a[@rel="category tag"]/text()')

        if len(title_nodes) == 0:
            print(f"\r\033[KError in {page_link}, no title found")
            return None
        title = title_nodes[0]

        published_date = None
        if len(published_date_nodes) >= 1:
            published_date = published_date_nodes[0]
        updated_date = published_date
        if len(updated_date_nodes) >= 1:
            updated_date = updated_date_nodes[0]

        image_link = None
        if len(image_link_nodes) >= 1:
            image_link = image_link_nodes[0]
            if image_link.startswith('/'):
                image_link = 'https://languagelearning.site' + image_link

        description = None
        if len(description_nodes) > 0:
            description = "\n\n".join(
                '\n'.join([elm.strip() for elm in p_node.xpath('.//text()')]) for p_node in description_nodes
            )
            description = description.strip()
            if description == '':
                description = None

        extra_info = None
        if len(extra_info_nodes) > 0:
            extra_info = extra_info_nodes[0].getparent().text_content()
            if description is None:
                description = extra_info
            else:
                description += '\n' + extra_info
            description.strip()

        size_info = None
        if extra_info is not None:
            for line in extra_info.split('\n'):
                if line.startswith('Size'):
                    size_info = line.split('Size:')[-1].strip()

        size_in_mb = None
        if size_info is not None:
            size_parts = size_info.split(', ')  # multiple parts
            total = 0
            for size_part in size_parts:
                try:
                    only_size = size_part.split(' (')[0]  # (rarred xMB) or (xMB rarred)
                    only_size = only_size.replace(',', '.')  # fix dezimal point
                    only_size = only_size.replace(' ', '')  # remove spaces
                    only_size = only_size.upper().strip()
                    if only_size.endswith('KB'):
                        only_size = only_size[:-2]
                        total += float(only_size) / 1000
                    if only_size.endswith('MB'):
                        only_size = only_size[:-2]
                        total += float(only_size)
                    elif only_size.endswith('GB'):
                        only_size = only_size[:-2]
                        total += float(only_size) * 1000
                except ValueError:
                    pass
            if total > 0:
                size_in_mb = total

        # It would be possible to detect child package names:
        # Example view-source:https://languagelearning.site/french/les-loustics-2/
        # Packages: "livre, guide, audio" and "cahier"

        download_links = []
        for link in download_link_nodes:
            if link not in download_links:
                clean_link = link.strip()
                if not clean_link.startswith('http'):
                    continue
                if urlparse(clean_link).netloc not in self.forbidden_hoster:
                    download_links.append(clean_link)
        if len(download_links) == 0:
            print(f"\r\033[KError in {page_link} for {title}, no download link found")
            return None

        return {
            "title": title,
            "page_link": page_link,
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

    def _real_download_latest_feed(self) -> List[Dict]:
        loop = asyncio.get_event_loop()

        # On the WordPress side there are 5 entries per page and in rss there are also 5 entries per page
        max_page = self.get_max_page_for(self.max_page_url, self.max_page_pattern)

        # Collect all links that needs to be downloaded for metadata extraction
        page_links_list = []
        loop.run_until_complete(self.crawl_all_atom_page_links(self.feed_url, max_page, page_links_list))

        # Download and extract all pages
        result_list = []
        if len(page_links_list) > 0:
            loop.run_until_complete(
                self.fetch_all_pages_and_extract(page_links_list, self.page_metadata_extractor, result_list)
            )

        return result_list
