import os
import re
from pathlib import Path

from datetime import datetime, timedelta

from comics_dl.config_service.config_helper import ConfigHelper


class LastDateExtractor:
    def __init__(self, storage_path: str, categories: [str]):
        self.storage_path = storage_path
        self.categories = categories

        # Options to find the last upload date:
        # Option 1:
        # r"\d+\. \w+ 20\d\d"
        # Option 2:
        # r'<span class="post_date" title="([\d-]+)">'

    def get_last_upload_date(self, category: str):
        last_html_path = str(Path(self.storage_path) / category / '0001.html')

        if not os.path.isfile(last_html_path):
            return None

        with open(last_html_path, 'r', encoding='utf-8') as last_html:
            last_html_content = last_html.read()
        found_dates = re.findall(r'<span class="post_date" title="([\d-]+)">', last_html_content, flags=0)
        last_date = None
        for date in found_dates:
            parsed_date = datetime.strptime(date, "%Y-%m-%d")
            if last_date is None or last_date < parsed_date:
                last_date = parsed_date

        if last_date is not None:
            print(last_date.strftime("%d.%m.%Y"))
        return last_date

    def run(self):
        last_date = None
        for category in self.categories:
            print(f'Last upload day of category: {category}')
            parsed_date = self.get_last_upload_date(category)
            if last_date is None or (parsed_date is not None and last_date < parsed_date):
                last_date = parsed_date

        if last_date is not None:
            one_day_before = last_date - timedelta(days=1)
            print(f'Setting last date to {one_day_before.strftime("%Y-%m-%d")}')
            config = ConfigHelper()
            config.set_property('last_crawled_date', one_day_before.strftime("%Y-%m-%d"))
