import re
import json
import asyncio

from urllib.parse import urlparse

import lxml.html

from atom_dl.download_service.feed_downloader.common import FeedDownloader


class LanguagelearningFD(FeedDownloader):

    languagelearning_max_page_url = 'https://languagelearning.site/'
    languagelearning_max_page_patern = re.compile(
        r'<a class="page-numbers" href="https://languagelearning.site/page/(\d+)/">'
    )
    languagelearning_feed_url = 'https://languagelearning.site/feed/atom/?paged={page_id}'

    def page_metadata_extractor(self, page_link, page_text):
        try:
            root = lxml.html.fromstring(page_text)
        except ValueError:
            return None

        entry_nodes = root.xpath('//main//article//div[@class="inside-article"]')
        if len(entry_nodes) != 1:
            print(f"Error in {page_link}, entry found!")
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
            print(f"Error in {page_link}, no title found")
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

        description = None
        if len(description_nodes) > 0:
            description = "\n\n".join(p_node.text_content() for p_node in description_nodes)
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
                    size_info = line.split(':')[-1].strip()
                    size_info = size_info.split(' in')[0]

        download_links = []
        for link in download_link_nodes:
            if link not in download_links:
                clean_link = link.strip()
                if not clean_link.startswith('http'):
                    continue
                if urlparse(clean_link).netloc not in self.forbidden_hoster:
                    download_links.append(clean_link)
        if len(download_links) == 0:
            print(f"Error in {page_link} for {title}, no download link found")
            return None

        return {
            "title": title,
            "page_link": page_link,
            "published_date": published_date,
            "updated_date": updated_date,
            "description": description,
            "image_link": image_link,
            "size_info": size_info,
            "download_links": download_links,
            "categories": category_nodes,
        }

    def _real_download_feed(self):
        loop = asyncio.get_event_loop()

        # On the wordpress side there are 5 entries per page and in rss there are also 5 entries per page
        max_page_languagelearning = self.get_max_page_for(
            self.languagelearning_max_page_url, self.languagelearning_max_page_patern
        )

        # Collect all links that needs to be downloaded for metadata extraction
        page_links_list = []
        loop.run_until_complete(
            self.crawl_all_atom_page_links(self.languagelearning_feed_url, max_page_languagelearning, page_links_list)
        )

        # Download and extract all pages
        result_list = []
        loop.run_until_complete(
            self.fetch_all_pages_and_extract(page_links_list, self.page_metadata_extractor, result_list)
        )

        # Serializing json
        json_object = json.dumps(result_list, indent=4)

        # Writing to sample.json
        with open("languagelearning.json", "w", encoding='utf-8') as outfile:
            outfile.write(json_object)
        print(len(result_list))

        # one_day_before = date.today() - timedelta(days=1)
        # print(f'Setting last date to {one_day_before.strftime("%Y-%m-%d")}')
        # config = ConfigHelper()
        # config.set_property('last_crawled_date', one_day_before.strftime("%Y-%m-%d"))
