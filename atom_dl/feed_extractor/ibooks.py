import asyncio
import html
import re
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

import lxml.html
from lxml import etree

from atom_dl.feed_extractor.common import FeedInfoExtractor, TopCategory
from atom_dl.utils import float_or_none


class IbooksFIE(FeedInfoExtractor):
    max_page_url = 'https://ibooks.to/page/2/'
    max_page_pattern = re.compile(r'Seite 2 von (\d+)')
    feed_url = 'https://ibooks.to/feed/atom/?paged={page_id}'

    def page_metadata_extractor(self, page_idx: int, page_link: str, page_text: str, status_dict: Dict):
        root = self.load_xml_from_string(page_link, page_text)
        if root is None:
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

            image_link_nodes = content_root.xpath('.//img[contains(@class, "wp-post-image")]/@src')
            download_link_nodes = content_root.xpath('.//a[@target="_blank"]/@href')

            description = ''
            for node in content_root:
                if node.tag == 'p':
                    if len(node.xpath('.//a')) > 0:
                        break
                    text_elements = node.xpath('.//text()')
                    if len(text_elements) > 0:
                        description += '\n'.join([elm.strip() for elm in text_elements]) + '\n\n'
            description = description.strip()
            if description == '':
                description = None

            size_info = None
            size_in_mb = None
            if description is not None:
                # This size information is not always correct
                # It is 100% wrong for magazines
                # In very few cases the size is noted like: 89.21 + 124 MB (only the last part is captured)
                matches = self.size_pattern.findall(description)
                if len(matches) > 0:
                    match = matches[0]
                    only_size = match[0].replace(',', '.')
                    only_unit = match[1].upper()
                    size_info = f'{only_size} {only_unit}'
                    if only_unit.endswith('KB'):
                        size_in_mb = float_or_none(only_size, scale=1000)
                    if only_unit.endswith('MB'):
                        size_in_mb = float_or_none(only_size)
                    elif only_unit.endswith('GB'):
                        size_in_mb = float_or_none(only_size, invscale=1000)

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
                if image_link.startswith('/'):
                    image_link = 'https://ibooks.to' + image_link

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

            password = 'ibooks.to'

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
                    "password": password,
                    "extractor_key": self.fie_key(),
                }
            )
        return result_list

    def _real_download_latest_feed(self) -> List[Dict]:
        # On the WordPress side there are 10 entries per page and in rss there are also 10 entries per page
        max_page = self.get_max_page_for(self.max_page_url, self.max_page_pattern)

        # Collect all links that needs to be downloaded for metadata extraction
        page_links_list = []
        for page_id in range(1, max_page + 1):
            page_links_list.append(self.feed_url.format(page_id=page_id))

        # Download and extract all pages
        result_list = []
        asyncio.run(self.fetch_all_pages_and_extract(page_links_list, self.page_metadata_extractor, result_list))

        return result_list

    def get_top_category(self, post: Dict) -> TopCategory:
        """
        Categories on ibooks.to:
        - Bücher
            - Action & Horror
            - Bestseller & Sammelpacks
            - Erotik
            - Fantasy & Science Fiction
            - Historisch
            - Horror
            - Humor & Satire
            - Kinderbuch
            - Krimi & Thriller
            - Roman & Drama
        - Fachbücher
        - Magazine
        - Zeitungen
        - Comics
        - Mangas
        - Videos

        ibooks.to categories we want to handle:
        [
            "Action & Horror",
            "Bestseller / Ebook-Pakete / Sammelpacks",
            "Comic & Manga",
            "E-Learning Videos",
            "Ebooks",
            "Englisch",
            "Erotik",
            "Fantasy & Science Fiction",
            "Historisch",
            "Horror",
            "Humor & Satire",
            "Kinderbuch",
            "Krimi & Thriller",
            "Magazine & Zeitschriften",
            "Neuerscheinungen",
            "Neuigkeiten",
            "Perry Rhodan",
            "Roman & Drama",
            "Sachbuch & Fachbuch",
            "Zeitungen",
        ]
        """

        # Handle for special top category
        category_map = {
            "E-Learning Videos": TopCategory.videos,
            "Manga": TopCategory.manga,
            "Comic & Manga": TopCategory.comics,
            "Zeitungen": TopCategory.newspapers,
            "Magazine & Zeitschriften": TopCategory.magazines,
            "Sachbuch & Fachbuch": TopCategory.textbooks,
        }

        post_categories = post.get('categories', [])
        for category_check, top_category in category_map.items():
            for category in post_categories:
                if category == category_check:
                    return top_category

        # All others are in top category Ebooks
        return TopCategory.books

    def get_package_name(self, post: Dict) -> str:
        """
        Example Names:
        Manga:
            Gleipnir (EMA, 2018-…) 01 – 06
            Sprite (Carlsen, 2013-2017) 01 – 15
        Comics:
            Die verlorene Armee (Bunte Dimensionen, 2014-…) 01 – 04
        Zeitungen:
            Tageszeitungen vom 27.09.2020
            Frankfurter Allgemeine Sonntagszeitung vom 10. Juli 2022
        E-Learning Videos:
            LinkedIn – Rust lernen 2021
        Magazine & Zeitschriften:
            Simply Häkeln Magazin – aktuelle Ausgabe 2021-02
            ORF Nachlese – aktuelle Ausgabe 2021-05 + Sonderheft Garten 2021
        Sachbuch & Fachbuch:
            Daniela Katzenberger – Die Katze kocht!
        Bestseller / Ebook-Pakete / Sammelpacks:
            Charlotte Byrd – Gefährliche Verlobung – Band 1-3
            Susanna Schober – Mondlicht Saga (Reihe in 3 Bänden)
            Alica H. White – Liebe passiert 1+2
            The New York Times’ 100 Notable Books of (2020) – Sammelpack (99 eBooks) [Englisch]

        Magazines and newspapers need special treatment.
        """
        post_top_category = self.get_top_category(post)
        post_title = post.get('title', '')
        if post_top_category == TopCategory.magazines:
            return post_title.rsplit(' – aktuelle Ausgabe', 1)[0].strip()
        elif post_top_category == TopCategory.newspapers:
            return post_title.rsplit(' vom ')[0].strip()
        elif post_top_category in [TopCategory.comics, TopCategory.manga]:
            return self.brackets_pattern.sub('', post_title).strip()
        else:
            return post_title.strip()
