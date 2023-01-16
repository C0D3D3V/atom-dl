import os
import re
import zipfile

from pathlib import Path
from typing import List, Union
from zipfile import ZipInfo

import rarfile

from rarfile import RarInfo

from atom_dl.config_helper import Config
from atom_dl.feed_extractor.common import TopCategory
from atom_dl.utils import PathTools as PT, Log


class ArchiveExtractor:
    part_pattern = re.compile(r'^part(\d+)$')
    without_part_num_pattern = re.compile(r'^(.+\.part)\d+(\.\w+)$')
    dir_name_part_pattern = re.compile(r'^(.+)(\d+)$')

    def __init__(self):
        config = Config()
        self.storage_path = config.get_storage_path()

    def process(self):
        # Currently not all top categories are supported
        extract_file_types_per_category = {
            TopCategory.books: ['epub', 'pdf'],
            TopCategory.textbooks: ['epub', 'pdf'],
            TopCategory.magazines: ['pdf'],
        }
        self.blocked_file_types = ['txt', 'png', 'jpg', 'jpeg', 'gif', 'opf', 'xlsx', 'inf']

        for category, extract_file_types in extract_file_types_per_category.items():
            self.extract_all_archives(category, extract_file_types)

    def get_part_num(self, pre_ext: str) -> int:
        part_num = 0
        if pre_ext is not None:
            part_match = self.part_pattern.fullmatch(pre_ext)
            if part_match is not None:
                part_groups = part_match.groups()
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
        else:
            multipart_arc_filenames.append(first_part_filename)
        return multipart_arc_filenames

    def get_base_path_pattern(self, container_infolist: List[Union[ZipInfo, RarInfo]]) -> str:
        # First get the parts of all unique dir paths in the archive
        all_dir_paths_parts = []
        for file_info in container_infolist:
            if file_info.is_dir():
                # We build the base dir based on the files we want to extract
                continue
            ext = PT.get_file_ext(file_info.filename)
            if ext in self.blocked_file_types:
                # We ignore all file that we do not want, because they may be in a top folder
                continue

            dir_path_parts = Path(file_info.filename).parent.parts
            if dir_path_parts not in all_dir_paths_parts:
                all_dir_paths_parts.append(dir_path_parts)

        base_path_pattern = r'^'
        if len(all_dir_paths_parts) == 0:
            return base_path_pattern

        # Get base dir of all the directors inside the archive
        base_idx = 0
        found_base = False
        base_path_next_part_pattern = ''
        while not found_base:
            for idx_path, dir_path_parts in enumerate(all_dir_paths_parts):
                if len(dir_path_parts) < base_idx + 1:
                    # If the is as long as the pattern, the base dir is found
                    found_base = True
                    break

                if idx_path == 0:
                    next_path_part = dir_path_parts[base_idx]

                    # parted dir names are added to the pattern - every dir in that level needs to have a part num
                    parted_dir_name_match = self.dir_name_part_pattern.fullmatch(next_path_part)
                    if parted_dir_name_match is not None:
                        parted_dir_name_groups = parted_dir_name_match.groups()
                        base_path_next_part_pattern = fr'{parted_dir_name_groups[0]}\d+'
                    else:
                        base_path_next_part_pattern = fr'{next_path_part}'

                if re.fullmatch(base_path_next_part_pattern, dir_path_parts[base_idx]) is None:
                    # If the part does not match the pattern, the base dir is found
                    found_base = True
                    break
                if idx_path == len(all_dir_paths_parts) - 1:
                    # Pattern matched all paths, so add it to the whole pattern
                    base_path_pattern += base_path_next_part_pattern + r'/'
            if not found_base:
                base_idx += 1

        if base_path_pattern != r'^':
            # Make last path separator optional
            base_path_pattern += r'?'
        return base_path_pattern

    def get_files_to_extract(
        self,
        arc_path: str,
        container_infolist: List[Union[ZipInfo, RarInfo]],
        extract_file_types: List[str],
    ) -> List[str]:
        # Collect all file stems with file types that are not blocked
        file_stems_to_extract = {}
        for file_info in container_infolist:
            if file_info.is_dir():
                continue
            stem, ext = PT.get_file_stem_and_ext(file_info.filename)
            ext_lower = ext.lower()
            if ext_lower in self.blocked_file_types:
                continue

            if stem not in file_stems_to_extract:
                file_stems_to_extract[stem] = []
            if ext_lower in extract_file_types:
                # Add file extensions of wanted file types
                file_stems_to_extract[stem].append(ext)

        for stem_to_extract, exts_to_extract in file_stems_to_extract.items():
            # Check if there is a file inside the archive that missis a wanted file type
            if len(exts_to_extract) > 0:
                continue
            Log.warning(f'WARNING: Missing wanted file type for `{stem_to_extract}` in `{arc_path}`')
            for file_info in container_infolist:
                if file_info.is_dir():
                    continue
                stem, ext = PT.get_file_stem_and_ext(file_info.filename)
                if ext.lower() in self.blocked_file_types:
                    continue

                if stem == stem_to_extract:
                    Log.info(f'Extracting instead `{ext}` for `{stem}`')
                    file_stems_to_extract[stem].append(ext)

        return [
            f'{stem_to_extract}.{ext}'
            for stem_to_extract, exts_to_extract in file_stems_to_extract.items()
            for ext in exts_to_extract
        ]

    def extract_all_archives(
        self,
        category: TopCategory,
        extract_file_types: List[str],
    ):
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
                    container = None
                    if ext == 'zip':
                        container = zipfile.ZipFile(package_file_path)
                    elif ext == 'rar':
                        container = rarfile.RarFile(package_file_path)
                    if container is None:
                        Log.warning(f'Could not open: {package_file_path}')
                        continue

                    # container.setpassword(b'ibooks.to')
                    container_infolist = container.infolist()

                    base_path_pattern = self.get_base_path_pattern(container_infolist)
                    files_to_extract = self.get_files_to_extract(
                        package_file_path,
                        container_infolist,
                        extract_file_types,
                    )

                    for file_to_extract in files_to_extract:
                        storage_folder = str(Path(category_path) / book_title)

                        # Create subfolder and target file inside it
                        compressed_file_path_without_base = re.sub(
                            base_string, '', str(compressed_file_path.parent), count=1
                        )
                        storage_folder = str(Path(category_path) / book_title / str(compressed_file_path_without_base))

                        if not os.path.isdir(storage_folder):
                            os.makedirs(storage_folder, exist_ok=True)

                        check_for_duplication, target_path = self.get_path_of_non_existent_file(
                            str(Path(storage_folder) / compressed_file_path.name)
                        )

                        source = container.open(compressed_file_filename)
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
