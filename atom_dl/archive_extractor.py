import os

from typing import List

from atom_dl.config_helper import Config
from atom_dl.feed_extractor.common import TopCategory
from atom_dl.utils import PathTools as PT  # , Log


class ArchiveExtractor:
    def __init__(self):
        config = Config()
        self.storage_path = config.get_storage_path()

    def process(self):
        # Currently not all top categories are supported
        extract_file_types_per_category = {
            TopCategory.books: ['.epub', '.pdf'],
            TopCategory.textbooks: ['.epub', '.pdf'],
            TopCategory.magazines: ['.pdf'],
        }
        blocked_file_types = ['.txt', '.png', '.jpg', '.jpeg', '.gif', '.opf', '.xlsx']

        for category, extract_file_types in extract_file_types_per_category.items():
            self.extract_all_archives(category, extract_file_types, blocked_file_types)

    def extract_all_archives(self, category: TopCategory, extract_file_types: List[str], blocked_file_types: List[str]):
        category_path = PT.make_path(self.storage_path, category.value)

        if not os.path.isdir(category_path):
            # Nothing to do, category folder does not exist
            return

        package_names = os.listdir(category_path)
        for package_name in package_names:
            package_path = PT.make_path(category_path, package_name)

            package_files = os.listdir(package_path)
            for package_file in package_files:
                package_file_path = PT.make_path(package_path, package_file)

                print(package_file_path)
