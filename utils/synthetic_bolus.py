import pydicom
from pathlib import Path
import numpy as np
from skimage.draw import polygon
from scipy import ndimage
import copy
from hashlib import blake2b
from shapely.geometry import Polygon

# Return a modified UID string
def uid_modifier(uid_str, prefix, suffix_length):
    parts = uid_str.split(".")

    return f"{prefix}.{'.'.join(parts[-suffix_length:])}"

# Load CT images and sort them by InstanceNumber
def load_ct_images(dcm_dir):
    ct_files = Path(dcm_dir).glob("*.dcm")

    ct_slices = []
    for file in ct_files:
        ds = pydicom.dcmread(file)
        if ds.Modality != 'CT':
            continue
        ct_slices.append(ds)    

    sorted_slices = sorted(ct_slices, key=lambda x: int(x.InstanceNumber))
        
    return sorted_slices

# Create a binary mask for a specified ROI from the RT Structure Set
def create_mask_from_structure(spacing, origin, rtstruct_path, margin, raw_mask, roi_number):
    rtstructure = pydicom.dcmread(rtstruct_path)

    roi_list = roi_number if isinstance(roi_number, list) else [roi_number]
    all_masks = {} 
    diff_list = []
    for roi in roi_list:
        mask_dict = {}
        mask_area_sum = 0
        polygon_area_sum = 0
        
        slice_area_accumulator = {}  # key: sop_instance_uid, value: list of areas

        for roi_contour in rtstructure.ROIContourSequence:            
            if roi_contour.ReferencedROINumber == roi:
                for contour in roi_contour.ContourSequence:              
                    points = np.array(contour.ContourData).reshape(-1, 3)
                    voxel_coords = (points - np.array(origin)) / np.array(spacing)

                    rr, cc = polygon(voxel_coords[:, 1], voxel_coords[:, 0], shape=(512, 512))
                    new_mask = np.zeros((512, 512), dtype=np.uint16)
                    new_mask[rr, cc] = 1

                    if margin > 0:
                        new_mask = ndimage.binary_dilation(new_mask, iterations=margin).astype(np.uint16)

                    sop_instance_uid = contour.ContourImageSequence[0].ReferencedSOPInstanceUID

                    # Combine masks on same slice
                    if sop_instance_uid in mask_dict:
                        mask_dict[sop_instance_uid] |= new_mask
                    else:
                        mask_dict[sop_instance_uid] = new_mask

                    # Accumulate polygon area for this slice
                    area = contour_area(points)
                    if sop_instance_uid in slice_area_accumulator:
                        slice_area_accumulator[sop_instance_uid] += area
                    else:
                        slice_area_accumulator[sop_instance_uid] = area

        # After building each slice mask
        for uid in mask_dict:
            mask = mask_dict[uid]
            mask_pixels = np.count_nonzero(mask)
            mask_area = mask_pixels * spacing[0] * spacing[1]
            mask_area_sum += mask_area

            poly_area = slice_area_accumulator.get(uid, 0)
            polygon_area_sum += poly_area

            if (mask_area + poly_area) > 0:
                diff = abs(poly_area - mask_area) * 100 / ((mask_area + poly_area) / 2)
                diff_list.append(diff)

            # Apply HU value
            mask_dict[uid] = (mask * raw_mask).astype(np.uint16)

        all_masks[roi] = mask_dict

    median = float(np.median(diff_list))
    percentile_95 = float(np.percentile(diff_list, 95))
    stats = [round(median, 3), round(percentile_95, 3), round(float(max(diff_list)), 3)]

    return all_masks, stats

# Merges mask if more than 1 is present
def merge_masks(all_masks):
    merged = {}

    for inner_dict in all_masks.values():
        for key, value in inner_dict.items():
            if key in merged:
                merged[key] = merged[key] + value
            else:
                merged[key] = value.copy()  # Copy to avoid modifying originals

    return merged

# Save the modifiecd CT series with the mask applied
def save_modified_ct_series(sorted_slices, raw_mask, mask_dict, rtstructure, prefix, suffix_length, output_dir):
    for i, ct_slice in enumerate(sorted_slices):
        intercept = ct_slice.RescaleIntercept
        slope = ct_slice.RescaleSlope
        raw_pixel_array = ct_slice.pixel_array.astype(np.float32)
        hu = raw_pixel_array * slope + intercept
       
        if ct_slice.SOPInstanceUID in mask_dict:
            pixel_hu_mod = np.where((mask_dict[ct_slice.SOPInstanceUID] == raw_mask) & (hu + mask_dict[ct_slice.SOPInstanceUID] > 20), raw_mask*slope+intercept, hu + mask_dict[ct_slice.SOPInstanceUID]) # Applies mask on array 
            pixel_array_mod = (pixel_hu_mod-intercept)/slope
            pixel_array_mod = pixel_array_mod.astype(np.uint16)
            ct_slice.PixelData = pixel_array_mod.tobytes()
        ct_slice.file_meta.MediaStorageSOPInstanceUID = uid_modifier(ct_slice.file_meta.MediaStorageSOPInstanceUID, prefix, suffix_length)
        ct_slice.SOPInstanceUID = uid_modifier(ct_slice.SOPInstanceUID, prefix, suffix_length)
        if "ReferencedImageSequence" in ct_slice:
            for ref_sop in ct_slice.ReferencedImageSequence:
                if "ReferencedSOPInstanceUID" in ref_sop:
                    ref_sop.ReferencedSOPInstanceUID = uid_modifier(
                        ref_sop.ReferencedSOPInstanceUID, prefix, suffix_length)
        ct_slice.IrradiationEventUID = uid_modifier(ct_slice.IrradiationEventUID, prefix, suffix_length)
        #ct_slice.StudyInstanceUID = uid_modifier(ct_slice.StudyInstanceUID, prefix, suffix_length) Removed to preserve registration with original
        ct_slice.SeriesInstanceUID = uid_modifier(ct_slice.SeriesInstanceUID, prefix, suffix_length)
        #ct_slice.FrameOfReferenceUID = uid_modifier(ct_slice.FrameOfReferenceUID, prefix, suffix_length) Removed to preserve registration with original
        output_path = output_dir / f"CT.slice_{i+1:03d}.dcm"
        ct_slice.save_as(output_path)         
    
    return 

# Modifies the RTSRUCT file
def rtstructure(rtstruct_path, prefix, suffix_length, roi_list):
    ds = pydicom.dcmread(rtstruct_path)
    ds_mod = copy.deepcopy(ds)
    ds_mod.file_meta.MediaStorageSOPInstanceUID = uid_modifier(ds_mod.file_meta.MediaStorageSOPInstanceUID, prefix, suffix_length)
    ds_mod.SOPInstanceUID = uid_modifier(ds_mod.SOPInstanceUID, prefix, suffix_length)
    #ds_mod.StudyInstanceUID = uid_modifier(ds_mod.StudyInstanceUID, prefix, suffix_length) Removed to preserve registration with original
    ds_mod.SeriesInstanceUID = uid_modifier(ds_mod.SeriesInstanceUID, prefix, suffix_length)
    ds_mod.FrameOfReferenceUID = uid_modifier(ds_mod.FrameOfReferenceUID, prefix, suffix_length)

    # Replace in Referenced Frame of Reference Sequence 
    for ref_for in ds_mod.ReferencedFrameOfReferenceSequence:
        ref_for.FrameOfReferenceUID = uid_modifier(ref_for.FrameOfReferenceUID, prefix, suffix_length)

        for study in ref_for.RTReferencedStudySequence:
            #study.ReferencedSOPInstanceUID = uid_modifier(study.ReferencedSOPInstanceUID, prefix, suffix_length) Removed to preserve registration with original

            for series in study.RTReferencedSeriesSequence:
                series.SeriesInstanceUID = uid_modifier(series.SeriesInstanceUID, prefix, suffix_length)

                for img in series.ContourImageSequence:
                    img.ReferencedSOPInstanceUID = uid_modifier(img.ReferencedSOPInstanceUID, prefix, suffix_length)

    # Replace in StructureSetROISequence
    for roi in ds_mod.StructureSetROISequence:
        roi_number = roi.ROINumber
        roi.ReferencedFrameOfReferenceUID = uid_modifier(roi.ReferencedFrameOfReferenceUID, prefix, suffix_length)

        # Replace UIDs in ROIContourSequence
        for contour_seq in ds_mod.ROIContourSequence:
            if contour_seq.ReferencedROINumber == roi_number:
                for contour in contour_seq.ContourSequence:
                    for img in contour.ContourImageSequence:
                        img.ReferencedSOPInstanceUID = uid_modifier(img.ReferencedSOPInstanceUID, prefix, suffix_length)

    # Replace bolus type
    for roi in ds_mod.RTROIObservationsSequence:
        if roi.ReferencedROINumber in roi_list:            
            roi.RTROIInterpretedType = 'CONTROL'            
            del roi.ROIPhysicalPropertiesSequence
          
    return ds_mod

# Compares the hash between the original and modified pixel data
def integrity(dcm, dcm_mod):
    integrity_ok = []
    integrity_ko = []
    
    for dcma in dcm:       
        for i, dcmb in enumerate(dcm_mod):
            if dcma.InstanceNumber== dcmb.InstanceNumber:
                dcma_hash = blake2b(dcma.PixelData, digest_size=30).hexdigest()
                dcmb_hash = blake2b(dcmb.PixelData, digest_size=30).hexdigest()
                if dcma_hash == dcmb_hash:
                    integrity_ok.append(dcmb.SOPInstanceUID)
                else : 
                    integrity_ko.append(dcmb.SOPInstanceUID)
    return integrity_ok, integrity_ko

# Returns a summarized version of a list 
def summarize(nums):
    if not nums:
        return ""

    ranges = []
    start = nums[0]
    end = nums[0]

    for n in nums[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = n

    ranges.append(f"{start}-{end}" if start != end else str(start))

    return ", ".join(ranges)

# Calculates area of a polygon
def contour_area(points):
    try:
        poly = Polygon(points[:, :2])

        return poly.area if poly.is_valid else 0
    except:
        return 0