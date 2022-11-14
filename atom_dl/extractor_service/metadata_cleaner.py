import csv
import json

from pathlib import Path


class MetadataCleaner:
    def __init__(self, storage_path: str, metadata_json_path: str):
        self.metadata_json_path = metadata_json_path
        self.storage_path = storage_path

    def run(self):
        with open(self.metadata_json_path, encoding='utf-8') as json_file:
            data = json.load(json_file)

        categories = [
            "comic",
            "manga",
        ]
        new_data = {}
        for category in categories:
            new_data[category] = []

        search_terms = [
            "micky maus",
            "asterix ",
            "art of",
            "donald duck",
            "lustige taschenb",
            "lustiges taschenb",
            "sherlock",
        ]
        for current_category in categories:
            if current_category not in data:
                continue
            summe_size = 0
            for current_comic in data[current_category]:
                wanted_comic = False

                title_lower = current_comic['title'].lower()
                for term in search_terms:
                    if title_lower.find(term) >= 0:
                        wanted_comic = True
                        break
                if not wanted_comic:
                    continue

                for added_comic in new_data[current_category]:
                    if added_comic['title'] == current_comic['title']:
                        added_size = int(added_comic['space_info'].split(' ')[0])
                        current_size = int(current_comic['space_info'].split(' ')[0])

                        if added_size < current_size:
                            wanted_comic = False
                            break
                        else:
                            summe_size -= added_size
                            new_data[current_category].remove(added_comic)
                            break

                if not wanted_comic:
                    continue

                new_data[current_category].append(current_comic)

                comic_size = int(current_comic['space_info'].split(' ')[0])
                summe_size += comic_size

            print(f"{current_category} Size: {summe_size} MB")

        csv_linex = []
        for current_category in categories:
            if current_category not in new_data:
                continue
            for current_comic in new_data[current_category]:
                comic_size = int(current_comic['space_info'].split(' ')[0])
                csv_linex.append(
                    {
                        'title': current_comic['title'],
                        'size': comic_size,
                    }
                )

        total_books = 0
        for category in categories:
            print(f"{category} before: {len(data[category])} after: {len(new_data[category]) }")
            total_books += len(new_data[category])

        print(f'In total: {total_books} books')

        all_metadata_sorted = {}
        for category in categories:
            to_sort = new_data[category]
            all_metadata_sorted[category] = sorted(
                to_sort,
                key=lambda k: (
                    int(k['space_info'].split(' ')[0]),
                    k['key'],
                    100000 if k['issue_min'] is None else k['issue_min'],
                    k['title'],
                    k['updated_date'],
                ),
            )
        out_file = open(str(Path(self.storage_path) / 'cleaned_metadata.json'), "w", encoding='utf-8')
        json.dump(all_metadata_sorted, out_file, indent=6)
        out_file.close()

        with open(str(Path(self.storage_path) / 'file_list.csv'), "w", newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'size']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for entry in csv_linex:
                writer.writerow(entry)
