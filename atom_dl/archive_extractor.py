import os
import re

from typing import List

from atom_dl.config_helper import Config
from atom_dl.feed_extractor.common import TopCategory
from atom_dl.utils import PathTools as PT  # , Log


class ArchiveExtractor:
    part_pattern = re.compile(r'^part(\d+)$')
    without_part_num_pattern = re.compile(r'^(.+\.part)\d+(\.\w+)$')

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

    def get_part_num(self, pre_ext: str) -> int:
        part_num = 0
        if pre_ext is not None:
            part_match = self.part_pattern.fullmatch(pre_ext)
            if part_match is not None:
                part_groups = part_match.groups()
                if len(part_groups) >= 1:
                    part_num = int(part_groups[0])
        return part_num

    def get_all_multipart_arc_filenames(self, first_part_filename: str, package_files: str) -> List[str]:
        multipart_arc_filenames = []
        multipart_name_pattern_match = self.without_part_num_pattern.fullmatch(first_part_filename)
        if multipart_name_pattern_match is not None:
            multipart_name_pattern = multipart_name_pattern_match.groups()
            name_start = multipart_name_pattern[0]
            name_end = multipart_name_pattern[1]
            for name_to_check in package_files:
                if name_to_check.startswith(name_start) and name_to_check.endswith(name_end):
                    multipart_arc_filenames.append(name_to_check)
        return multipart_arc_filenames

    def extract_all_archives(self, category: TopCategory, extract_file_types: List[str], blocked_file_types: List[str]):
        category_path = PT.make_path(self.storage_path, category.value)

        if not os.path.isdir(category_path):
            # Nothing to do, category folder does not exist
            return

        package_names = os.listdir(category_path)
        for package_name in package_names:
            package_path = PT.make_path(category_path, package_name)

            # We collect a list of all files that we have extracted, so we can delete them later
            extracted_files_in_package = []

            package_files = os.listdir(package_path)
            for package_file in package_files:
                package_file_path = PT.make_path(package_path, package_file)

                # Skip all files that are not archives
                pre_ext, ext = PT.get_file_exts(package_file)
                if ext not in ['zip', 'rar']:
                    continue

                # Check if it is a multipart archive, we start extracting only with the first part
                part_num = self.get_part_num(pre_ext)
                if part_num > 1:
                    continue

                # Start extraction
                try:
                    # Do stuff

                    # Great stuff

                    if part_num == 0:
                        # For single part archives we just want to delete this file
                        extracted_files_in_package.append(package_file)
                    elif part_num == 1:
                        # For multipart archives we want to remove all files that are part of the multipart archive
                        multipart_arc_filenames = self.get_all_multipart_arc_filenames(package_file, package_files)
                        extracted_files_in_package.extend(multipart_arc_filenames)
                except Exception as extract_err:
                    print(f"Error on: {package_file_path}")
                    print(extract_err)

            # Remove all extracted archives
            for file_to_delete in extracted_files_in_package:
                file_to_delete_path = PT.make_path(package_path, file_to_delete)
                print(f'Info: Deleting {file_to_delete_path}')
                try:
                    os.remove(file_to_delete_path)
                except OSError as delete_err:
                    print(f'Failed to remove: {file_to_delete_path} - Error: {delete_err}')
