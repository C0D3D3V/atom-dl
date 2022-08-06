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
            "action-horror",
            "erotik",
            "fantasy-science-fiction",
            "historisch",
            "horror",
            "humor-satire",
            "kinderbuch",
            "krimi-thriller",
            "magazine-zeitschriften",
            "roman-drama",
            "fachbuecher-sachbuecher",
            "zeitungen",
            "ebooks",
        ]
        new_data = {}
        for category in categories:
            new_data[category] = []

        for current_category in categories:
            if current_category not in data:
                continue
            for current_book in data[current_category]:
                found_match = False
                for check_category in categories:
                    if check_category not in new_data:
                        continue
                    for check_book in new_data[check_category]:
                        if check_book['crypt_download_link'] == current_book['crypt_download_link']:
                            found_match = True
                            break
                    if found_match:
                        break
                if not found_match:
                    new_data[current_category].append(current_book)

        total_books = 0
        for category in categories:
            print(f"{category} before: {len(data[category])} after: {len(new_data[category]) }")
            total_books += len(new_data[category])

        print(f'In total: {total_books} books')

        out_file = open(str(Path(self.storage_path) / 'combined_cleaned_metadata.json'), "w", encoding='utf-8')
        json.dump(new_data, out_file, indent=6)
        out_file.close()
