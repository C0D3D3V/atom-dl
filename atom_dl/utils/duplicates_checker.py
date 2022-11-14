import os
import json
import shutil
import hashlib

from pathlib import Path

from atom_dl.download_service.path_tools import PathTools


class DuplicatesChecker:
    def __init__(self, storage_path: str, metadata_json_path: str, categories: [str]):
        self.storage_path = storage_path
        self.metadata_json_path = metadata_json_path
        self.categories = categories

        self.deleted_counter = 0
        self.deleted_file_counter = 0

        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            self.metadata = json.load(json_file)

    def get_duplicates_in_category(self, category):
        BLOCK_SIZE = 4096
        if category not in self.metadata:
            print(f'Missing {category} in metadata')
            return

        metadata_category = self.metadata[category]

        for book in metadata_category:
            book_title = book['title']
            if book_title is None or book_title == '':
                book_title = 'Title not defined'
            book_path = PathTools.path_of_download_book(self.storage_path, category, book_title)
            if not os.path.isdir(book_path):
                continue

            file_list = os.listdir(book_path)
            # check for empty directory
            if len(file_list) == 0:
                os.rmdir(book_path)
                self.deleted_counter += 1
                print(f'{self.deleted_counter:03} Deleted empty directory: {book_path}')

            extensions_in_folder = []
            hash_map = {}

            for filename in file_list:
                file_path = str(Path(book_path) / filename)
                ext = filename.split('.')[-1].lower()
                if ext not in extensions_in_folder:
                    extensions_in_folder.append(ext)

                # Remove empty .part files
                if ext == 'part' and os.path.getsize(file_path) == 0:
                    os.remove(file_path)
                    self.deleted_file_counter += 1
                    print(f'{self.deleted_file_counter:03} Deleted empty path file: {file_path}')
                    continue

                # Images have jpg, png, jpeg or gif extension
                if ext not in [
                    'png',
                    'jpg',
                    'jpeg',
                    'gif',
                    'zip',
                    'rar',
                    'epub',
                    'pdf',
                    'z01',
                    'z02',
                    'z03',
                    'z04',
                    'txt',
                ]:
                    print(f'Found unexpected file type: {file_path}, size: {os.path.getsize(file_path)}')
                    continue

                md5 = hashlib.md5()
                with open(file_path, 'rb') as opend_file:
                    data = opend_file.read(BLOCK_SIZE)
                    if data:
                        md5.update(data)
                final_md5 = md5.hexdigest()
                if final_md5 in hash_map:
                    hash_map[final_md5].append(file_path)
                else:
                    hash_map[final_md5] = [file_path]

            only_images = True
            for ext in extensions_in_folder:
                if ext not in ['png', 'jpg', 'jpeg', 'gif']:
                    only_images = False
            if only_images:
                self.deleted_counter += 1
                print(f'{self.deleted_counter:03} Deleted folder because it only contains images: {book_path}')
                for filename in file_list:
                    print(f'Deleted: {filename}')
                shutil.rmtree(book_path)
                continue
            for _md5_key, duplicates in hash_map.items():
                if len(duplicates) > 1:
                    full_hash_map = {}
                    # print(f'Test for duplicates: {duplicates}')
                    for duplicate_path in duplicates:
                        md5 = hashlib.md5()
                        with open(duplicate_path, 'rb') as opend_file:
                            while True:
                                data = opend_file.read(BLOCK_SIZE)
                                if not data:
                                    break
                                md5.update(data)
                        final_md5 = md5.hexdigest()
                        if final_md5 in full_hash_map:
                            full_hash_map[final_md5].append(duplicate_path)
                        else:
                            full_hash_map[final_md5] = [duplicate_path]
                    for _md5_key, real_duplicates in full_hash_map.items():
                        if len(real_duplicates) > 1:
                            print(f'Found duplicates: {duplicates}')
                            longest_path = ""
                            longest_path_special_count = 0
                            for real_duplicate in real_duplicates:
                                if len(real_duplicate) > len(longest_path):
                                    longest_path = real_duplicate
                                    longest_path_special_count = longest_path.count('_') + real_duplicate.count('.')
                                elif len(real_duplicate) == len(longest_path):
                                    special_count = real_duplicate.count('_') + real_duplicate.count('.')
                                    if special_count < longest_path_special_count:
                                        longest_path = real_duplicate
                                        longest_path_special_count = special_count

                            for real_duplicate in real_duplicates:
                                if longest_path != real_duplicate:
                                    os.remove(real_duplicate)
                                    self.deleted_file_counter += 1
                                    print(f'{self.deleted_file_counter:03} Deleted duplicate: {real_duplicate}')

    def run(self):
        for category in self.categories:
            print(f'Checking in category {category}')
            self.get_duplicates_in_category(category)
