from pathlib import Path

prefix = '1.2.826.0.1.3680043.8.498' # Pydicom prefix
suffix_length = 1

margin = 0 # Bolus margin
hu_mask = 0 # HU Value for mask

dicom_original_path = Path(__file__).parent.parent / 'uploads' / 'original'
dicom_original_path.mkdir(parents=True, exist_ok=True)

dicom_modified_path = Path(__file__).parent.parent / 'uploads' / 'modified'
dicom_modified_path.mkdir(parents=True, exist_ok=True)


