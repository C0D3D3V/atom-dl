import os
import re
import shutil
import hashlib

from pathlib import Path

import zipfile
import rarfile

from atom_dl.download_service.path_tools import PathTools


class ArchiveExtractor:

    part_patern = re.compile(r'^part(\d+)$')
    without_part_patern = re.compile(r'^(.+\.part)\d+(\.\w+)$')

    def __init__(self, storage_path: str, categories: [str]):
        self.storage_path = storage_path
        self.categories = categories

        self.file_hash_map = {}
        self.hash_file_map = {}
        self.file_size_map = {}

    def extract_archvives_in_category(self, category):

        category_path = PathTools.path_of_download_category(self.storage_path, category)

        if not os.path.isdir(category_path):
            print(f'{category_path} not found')
            return

        book_title_list = os.listdir(category_path)
        for book_title in book_title_list:
            book_path = str(Path(category_path) / book_title)
            book_file_list = os.listdir(book_path)
            init_message = False
            files_to_delete = []
            for filename in book_file_list:
                file_path = str(Path(category_path) / book_title / filename)
                filename_split = filename.split('.')
                ext = filename_split[-1].lower()
                ext2 = filename_split[-2].lower()

                if ext not in ['zip', 'rar']:
                    continue
                if not init_message:
                    print(f'Start working on `{book_path}`...')
                    init_message = True
                part_num_result = self.part_patern.findall(ext2)
                part_num = 0
                if len(part_num_result) == 1:
                    part_num = int(part_num_result[0])
                if part_num > 1:
                    continue

                if part_num == 1:
                    filename_pattern = self.without_part_patern.findall(filename)
                    if len(filename_pattern) != 1:
                        print(f'Error, could not find filename pattern for {file_path}')

                try:
                    container = None
                    if ext == 'zip':
                        container = zipfile.ZipFile(file_path)
                    elif ext == 'rar':
                        container = rarfile.RarFile(file_path)

                    if container is None:
                        print(f'Could not open: {file_path}')
                        continue

                    compressed_paths = {}
                    for compressed_file_info in container.infolist():
                        if compressed_file_info.is_dir():
                            continue
                        compressed_file_path = Path(compressed_file_info.filename)
                        if compressed_file_path.suffix in ['.txt', '.png', '.jpg', '.jpeg', '.gif']:
                            continue

                        compressed_path = str(compressed_file_path.parent)
                        if compressed_path in compressed_paths:
                            compressed_paths[compressed_path] += 1
                        else:
                            compressed_paths[compressed_path] = 1

                    if len(compressed_paths) != 1:
                        print(f'Skipping {file_path}, because of missing extraction implementation.')
                        print(compressed_paths)
                        continue

                    extracted_counter = 0
                    for compressed_file_info in container.infolist():
                        if compressed_file_info.is_dir():
                            continue
                        compressed_file_path = Path(compressed_file_info.filename)
                        if compressed_file_path.suffix in ['.txt', '.png', '.jpg', '.jpeg', '.gif']:
                            continue

                        check_for_duplication, target_path = self.get_path_of_non_existent_file(
                            str(Path(category_path) / book_title / compressed_file_path.name)
                        )

                        # precheck if it does already exist
                        if check_for_duplication:
                            CHUNCK_SIZE = 8192
                            md = hashlib.sha1()
                            with container.open(compressed_file_info.filename) as precheck_source:
                                chunk = precheck_source.read(CHUNCK_SIZE)
                                md.update(chunk)
                            header_hash = md.hexdigest()
                            file_size = compressed_file_info.file_size
                            is_duplicate = False
                            if header_hash in self.hash_file_map:
                                for hashed_file_path in self.hash_file_map[header_hash]:
                                    if self.file_size_map[hashed_file_path] == file_size:
                                        print(f'Already exitsts: `{compressed_file_path.name}`')
                                        is_duplicate = True
                                        break
                            if is_duplicate:
                                continue

                        source = container.open(compressed_file_info.filename)
                        target = open(target_path, "wb")

                        with source, target:
                            shutil.copyfileobj(source, target)
                        extracted_counter += 1

                        if check_for_duplication:
                            if not self.gen_hash_of_file(target_path):
                                print(f'Info: Deleting `{target_path}`')
                                try:
                                    os.remove(target_path)
                                except OSError as error_inner:
                                    print(f'Failed to remove {target_path} - Error: {error_inner}')

                    print(f'INFO: Extracted {extracted_counter} file(s)')

                    if part_num == 0:
                        files_to_delete.append(filename)
                    elif part_num == 1:
                        filename_beginning = filename_pattern[0][0]
                        filename_ending = filename_pattern[0][1]
                        for filename in book_file_list:
                            if filename.startswith(filename_beginning) and filename.endswith(filename_ending):
                                files_to_delete.append(filename)

                except Exception as error:
                    print(f"Error on: {file_path}")
                    print(error)
                print(f'Finished `{file_path}`')

            for file_to_delete in files_to_delete:
                file_to_delete_path = str(Path(category_path) / book_title / file_to_delete)
                print(f'Info: Deleting {file_to_delete_path}')
                try:
                    os.remove(file_to_delete_path)
                except OSError as error_inner:
                    print(f'Failed to remove `{file_to_delete_path}` - Error: {error_inner}')
            if init_message:
                print(f'Finished `{book_path}`')

    def gen_hash_of_file(self, path: str):
        """
        Returns False if it is duplicate
        """
        CHUNCK_SIZE = 8192
        md = hashlib.sha1()
        with open(path, 'rb') as istr:
            chunk = istr.read(CHUNCK_SIZE)
            md.update(chunk)

        header_hash = md.hexdigest()
        file_size = os.path.getsize(path)
        if header_hash in self.hash_file_map:
            for file_path in self.hash_file_map[header_hash]:
                if self.file_size_map[file_path] == file_size:
                    print(f'Info: {path} is duplication of {file_path}!')
                    return False
        else:
            self.hash_file_map[header_hash] = []
        self.hash_file_map[header_hash].append(path)
        self.file_hash_map[path] = header_hash
        self.file_size_map[path] = file_size
        return True

    def get_path_of_non_existent_file(self, wish_path: str) -> (bool, str):
        """
        Returns check_for_duplication, save_path
        """
        new_path = wish_path

        count = 0
        content_filename = os.path.basename(wish_path)
        destination = os.path.dirname(wish_path)
        filename, file_extension = os.path.splitext(content_filename)

        check_for_duplication = False
        while os.path.exists(new_path):
            check_for_duplication = True
            if new_path not in self.file_hash_map:
                self.gen_hash_of_file(new_path)
            count += 1
            new_filename = f'{filename}_{count:02d}{file_extension}'
            new_path = str(Path(destination) / new_filename)

        return (check_for_duplication, new_path)

    def run(self):
        for category in self.categories:
            print(f'Extract archives in category {category}')
            self.extract_archvives_in_category(category)
