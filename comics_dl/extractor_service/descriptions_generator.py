import os
import json

from comics_dl.download_service.path_tools import PathTools


class DescriptionsGenerator:
    def __init__(self, storage_path: str, metadata_json_path: str, categories: [str]):
        self.storage_path = storage_path
        self.metadata_json_path = metadata_json_path
        self.categories = categories
        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            self.metadata = json.load(json_file)

    def generate_descriptions_in_category(self, category):
        if category not in self.metadata:
            print(f'Missing {category} in metadata')
            return

        metadata_category = self.metadata[category]

        for book in metadata_category:
            if book['description'] is None or book['description'] == '':
                continue
            book_title = book['title']
            if book_title is None or book_title == '':
                book_title = 'Title not defined'
            book_path = PathTools.path_of_download_book(self.storage_path, category, book_title)
            if not os.path.isdir(book_path):
                continue
            description_path = PathTools.path_of_download_description(self.storage_path, category, book_title)
            if os.path.isfile(description_path) and os.path.getsize(description_path) > 0:
                continue
            description_to_save = book['description'].strip("\n").strip("\r")
            if len(description_to_save) > 0 and description_to_save != '':
                with open(description_path, 'w', encoding='utf-8') as desc_file:
                    desc_file.write(description_to_save)

    def run(self):
        for category in self.categories:
            print(f'Handeling category {category}')
            self.generate_descriptions_in_category(category)
