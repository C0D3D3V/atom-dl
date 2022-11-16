import os
import csv
import json
import hashlib

from pathlib import Path

import zipfile
import rarfile

from atom_dl.utils.path_tools import PathTools


class HashGenerator:
    def __init__(self, storage_path: str, metadata_json_path: str, categories: [str]):
        self.storage_path = storage_path
        self.metadata_json_path = metadata_json_path
        self.categories = categories

        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            self.metadata = json.load(json_file)
        self.all_hashes = []

    def gen_hashes_in_category(self, category):
        BLOCK_SIZE = 4096
        if category not in self.metadata:
            print(f'Missing {category} in metadata')
            return

        metadata_category = self.metadata[category]

        all_hash_list = []

        for book in metadata_category:
            if book['description'] is None or book['description'] == '':
                continue
            book_title = book['title']
            if book_title is None or book_title == '':
                book_title = 'Title not defined'
            book_path = PathTools.path_of_download_book(self.storage_path, category, book_title)
            if not os.path.isdir(book_path):
                continue

            file_list = os.listdir(book_path)

            for filename in file_list:
                file_path = str(Path(book_path) / filename)
                ext = filename.split('.')[-1].lower()

                if ext not in ['zip', 'rar']:
                    continue

                md5 = hashlib.md5()

                try:
                    container = None
                    if ext == 'zip':
                        container = zipfile.ZipFile(file_path)
                    elif ext == 'rar':
                        container = rarfile.RarFile(file_path)

                    if container is None:
                        print(f'Could not open: {file_path}')
                        continue

                    for compressed_file in container.infolist():
                        if compressed_file.is_dir():
                            continue
                        ext = compressed_file.filename.split('.')[-1]
                        if ext in ['.txt', 'png', 'jpg', 'jpeg', 'gif']:
                            continue
                        with container.open(compressed_file.filename) as opend_file:
                            while True:
                                data = opend_file.read(BLOCK_SIZE)
                                if not data:
                                    break
                                md5.update(data)
                        final_md5 = md5.hexdigest()
                        all_hash_list.append(
                            {
                                'filename': compressed_file.filename,
                                'md5': final_md5,
                                'file_size': str(compressed_file.file_size),
                            }
                        )
                        self.all_hashes.append(final_md5)
                except Exception as error:
                    print(f"Error on: {file_path}")
                    print(error)
        return all_hash_list

    def run(self):
        for category in self.categories:
            print(f'Handeling category {category}')
            all_hash_list = self.gen_hashes_in_category(category)

            with open(
                str(Path(self.storage_path) / f'{category}_hashs.csv'), "w", newline='', encoding='utf-8'
            ) as csvfile:
                fieldnames = ['filename', 'md5', 'file_size']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for hash_entry in all_hash_list:
                    writer.writerow(hash_entry)
        with open(str(Path(self.storage_path) / 'all_hashs.txt'), "w", encoding='utf-8') as all_hashes_file:
            all_hashes_file.writelines(f"{line}\n" for line in self.all_hashes)
