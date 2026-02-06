import sys
from rapidfuzz.distance import DamerauLevenshtein
import wordninja
import csv
import json
import re
from unidecode import unidecode
csv.field_size_limit(sys.maxsize)


def remove_unicode_text_patterns(text_list):
    if isinstance(text_list, str):
        text_split_ = text_list.split()
    else:
        text_split_ = text_list
    
    patterns = ['200b', '200c', '200d', '2060', 'feff', '200e', '200f', '061c', '00ad']
    result = []
    for text in text_split_:
        for pattern in patterns:
            text = text.replace(f'<{pattern}>', '').replace(f'<{pattern.upper()}>', '')
        result.append(text.lower())
    return result


def normalize_unicode_text(text_list):
    
    if isinstance(text_list, str):
        text_split_ = text_list.split()
    else:
        text_split_ = text_list
    
    result = []
    for text in text_split_:
        ascii_text = unidecode(text).lower()
        if ascii_text:
            result.append(ascii_text)
    return result


def remove_special_characters(text_list):
    
    if isinstance(text_list, str):
        text_split_ = text_list.split()
    else:
        text_split_ = text_list
    
    result = []
    for text in text_split_:
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', text)
        if cleaned:
            result.append(cleaned.lower())
    return result


def get_distance_levenshtein_typosquatting(my_brand, my_word):
    return DamerauLevenshtein.distance(my_brand, my_word)


def get_word(my_list, my_first, my_last):
    return ' '.join(my_list[my_first:my_last])


def _empty_result_box():
    return {
        'raw_direct': 0, 'raw_typo': 0, 'raw_combo': 0, 'raw_fuzzy': 0,
        'invisible_direct': 0, 'invisible_typo': 0, 'invisible_combo': 0, 'invisible_fuzzy': 0,
        'normalized_direct': 0, 'normalized_typo': 0, 'normalized_combo': 0, 'normalized_fuzzy': 0,
        'special_direct': 0, 'special_typo': 0, 'special_combo': 0, 'special_fuzzy': 0,
        'substring_match': 0
    }


def _check_substring_fallback(result_box, my_brand, original_text):
    all_zero = all(v == 0 for k, v in result_box.items() if k != 'substring_match')
    if all_zero:
        text_no_space = original_text.replace(' ', '')
        brand_no_space = my_brand.replace(' ', '')
        if brand_no_space and brand_no_space in text_no_space:
            result_box['substring_match'] = 1


# ONE-WORD BRAND FUNCTIONS

def seperate_word_check_one_word_with_origin(my_list):
    tracked = []
    for orig_idx, orig_token in enumerate(my_list):
        parts = wordninja.split(orig_token)
        for sub_token in parts:
            tracked.append((orig_idx, orig_token, sub_token))
    return tracked


def process_detection_oneword(text_split_, my_brand, result_box, prefix):
    # ---------------- STEP 1: direct / typo ----------------
    remaining = []

    for tok in text_split_:
        dist = get_distance_levenshtein_typosquatting(my_brand, tok)

        if dist == 0:
            result_box[f'{prefix}direct'] += 1
        elif dist == 1:
            result_box[f'{prefix}typo'] += 1
        else:
            remaining.append(tok)

    if not remaining:
        return ""

    tracked = seperate_word_check_one_word_with_origin(remaining)

    remove_orig = set()
    for orig_idx, orig_token, sub_token in tracked:
        if orig_idx in remove_orig:
            continue

        dist = get_distance_levenshtein_typosquatting(my_brand, sub_token)

        if dist == 0:
            result_box[f'{prefix}combo'] += 1
            remove_orig.add(orig_idx)
        elif 1 <= dist <= 2:
            result_box[f'{prefix}fuzzy'] += 1
            remove_orig.add(orig_idx)

    remaining = [tok for i, tok in enumerate(remaining) if i not in remove_orig]
    return " ".join(remaining)


def check_impersonation_one_word(input_my_brand, input_text_split_, original_text):
    my_brand = input_my_brand

    result_box = _empty_result_box()

    text_after_raw = process_detection_oneword(input_text_split_.copy(), my_brand, result_box, prefix='raw_')

    if not text_after_raw:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_clean = remove_unicode_text_patterns(text_after_raw)
    text_after_invisible = process_detection_oneword(text_clean, my_brand, result_box, prefix='invisible_')

    if not text_after_invisible:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_normalized = normalize_unicode_text(text_after_invisible)
    text_after_normalized = process_detection_oneword(text_normalized, my_brand, result_box, prefix='normalized_')

    if not text_after_normalized:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_special = remove_special_characters(text_after_normalized)
    process_detection_oneword(text_special, my_brand, result_box, prefix='special_')

    _check_substring_fallback(result_box, my_brand, original_text)

    return result_box

# MULTIPLE-WORD BRAND FUNCTIONS

def seperate_word_check_multiword_with_origin(my_list):
    tracked = []
    child_parent_dict = {}
    child_idx = 0
    
    for orig_idx, orig_token in enumerate(my_list):
        parts = wordninja.split(orig_token)
        for sub_token in parts:
            tracked.append((orig_idx, orig_token, sub_token, child_idx))
            child_parent_dict[child_idx] = orig_idx
            child_idx += 1
    
    return tracked, child_parent_dict



def process_detection_multiword(text_split_, my_brand, brand_count, result_box, prefix):
    remove_token = [False] * len(text_split_)
    index = 0
    
    while index <= len(text_split_) - brand_count:
        if any(remove_token[i] for i in range(index, index + brand_count)):
            index += 1
            continue
        
        word_extracted = get_word(text_split_, index, index + brand_count)
        dist = get_distance_levenshtein_typosquatting(my_brand, word_extracted)
        
        if dist == 0:
            result_box[f'{prefix}direct'] += 1
            for i in range(index, index + brand_count):
                remove_token[i] = True
            index += brand_count
        elif dist == 1:
            result_box[f'{prefix}typo'] += 1
            for i in range(index, index + brand_count):
                remove_token[i] = True
            index += brand_count
        else:
            index += 1
    
    text_split_ = [tok for i, tok in enumerate(text_split_) if not remove_token[i]]
    
    if not text_split_:
        return ""
    
    tracked, child_parent_dict = seperate_word_check_multiword_with_origin(text_split_)
    ninja_tokens = [t[2] for t in tracked]
    
    if len(ninja_tokens) < brand_count:
        return " ".join(text_split_)
    
    remove_orig = set()
    remove_child = set()
    max_child_idx = len(ninja_tokens) - 1
    
    index = 0
    while index <= len(ninja_tokens) - brand_count:
        if any(i in remove_child for i in range(index, index + brand_count)):
            index += 1
            continue
        
        word_extracted = get_word(ninja_tokens, index, index + brand_count)
        dist = get_distance_levenshtein_typosquatting(my_brand, word_extracted)
        
        if dist == 0 or (1 <= dist <= 2):
            first_index = index
            last_index = index + brand_count - 1
            
            if len(ninja_tokens) == brand_count:
                label = 'typo'
            else:
                is_boundary_shared = False
                if first_index == 0:
                    last_index_inspect = last_index + 1
                    if last_index_inspect <= max_child_idx and \
                       child_parent_dict[last_index_inspect] == child_parent_dict[last_index]:
                        is_boundary_shared = True
                elif last_index == max_child_idx:
                    first_index_inspect = first_index - 1
                    if first_index_inspect >= 0 and \
                       child_parent_dict[first_index_inspect] == child_parent_dict[first_index]:
                        is_boundary_shared = True
                else:
                    first_index_inspect = first_index - 1
                    last_index_inspect = last_index + 1
                    if (first_index_inspect >= 0 and
                        child_parent_dict[first_index_inspect] == child_parent_dict[first_index]) or \
                       (last_index_inspect <= max_child_idx and
                        child_parent_dict[last_index_inspect] == child_parent_dict[last_index]):
                        is_boundary_shared = True
                
                if is_boundary_shared:
                    label = 'combo' if dist == 0 else 'fuzzy'
                else:
                    label = 'typo'
            
            result_box[f'{prefix}{label}'] += 1
            
            for i in range(first_index, last_index + 1):
                remove_child.add(i)
                remove_orig.add(child_parent_dict[i])
            
            index = last_index + 1
        else:
            index += 1
    
    text_split_ = [tok for i, tok in enumerate(text_split_) if i not in remove_orig]
    return " ".join(text_split_)



def check_impersonation_multiple_words(input_my_brand, input_brand_count, input_text_split_, original_text):
    my_brand = input_my_brand
    brand_count = input_brand_count

    result_box = _empty_result_box()

    text_after_raw = process_detection_multiword(
        input_text_split_.copy(), my_brand, brand_count, result_box, prefix='raw_'
    )
    
    if not text_after_raw:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_clean = remove_unicode_text_patterns(text_after_raw)
    text_after_invisible = process_detection_multiword(text_clean, my_brand, brand_count, result_box, prefix='invisible_')

    if not text_after_invisible:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_normalized = normalize_unicode_text(text_after_invisible)
    text_after_normalized = process_detection_multiword(text_normalized, my_brand, brand_count, result_box, prefix='normalized_')

    if not text_after_normalized:
        _check_substring_fallback(result_box, my_brand, original_text)
        return result_box

    text_special = remove_special_characters(text_after_normalized)
    process_detection_multiword(text_special, my_brand, brand_count, result_box, prefix='special_')

    _check_substring_fallback(result_box, my_brand, original_text)

    return result_box


# MAIN FUNCTION

def main(my_brand, my_text):
    if not my_brand or not my_brand.strip():
        return _empty_result_box()

    brand_words = my_brand.split()
    brand_count = len(brand_words)
    text_split_ = my_text.split()
    
    if brand_count == 1:
        return check_impersonation_one_word(my_brand, text_split_, my_text)
    else:
        return check_impersonation_multiple_words(my_brand, brand_count, text_split_, my_text)

if __name__ == "__main__":
    # ONE-WORD BRAND TESTS
    print("=" * 60)
    print("Test 1: Microsoft (one-word)")
    print("=" * 60)
    brand_ = "Microsoft"
    text_ = "contact support-Microsoft support-Microsoft support-Micro<200c>soft Microsoft Microosoft Micr<200b>osoft support team for help"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 2: PayPal (one-word)")
    print("=" * 60)
    brand_ = "PayPal"
    text_ = "Paypal support-PayPal PayPaI support-Paypal Pay<200b>Pal"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 3: Harbor Freight (unicode normalization test)")
    print("=" * 60)
    brand_ = "Harbor Freight"
    text_ = "𝐇𝐚𝐫𝐛𝐨𝐫 𝐅𝐫𝐞𝐢𝐠𝐡𝐭 Harbor Freight support"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 4: Costco (special character test)")
    print("=" * 60)
    brand_ = "Costco"
    text_ = "C.O.S.T.C.O Latest News Need your Feedback To win"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    # ============================================================
    # MULTIPLE-WORD BRAND TESTS
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 5: Capital One (multiple-word)")
    print("=" * 60)
    brand_ = "Capital One"
    text_ = "Your Capital OneR document is ready. CapitalOne support Capital<200b>One"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 6: American Express (multiple-word)")
    print("=" * 60)
    brand_ = "American Express"
    text_ = "American Expresss American Express supportAmericanExpress AmericanExpress American<200c>Express"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 7: Bank of America (multiple-word)")
    print("=" * 60)
    brand_ = "Bank of America"
    text_ = "BankofAmerica Bank of America Bank<200b>of<200b>America Bankof America"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 8: Wells Fargo (multiple-word)")
    print("=" * 60)
    brand_ = "Wells Fargo"
    text_ = "Wells Fargo support WellsFargo Wells<200c>Fargo Wellss Fargo"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 9: American Express (unicode normalization)")
    print("=" * 60)
    brand_ = "American Express"
    text_ = "𝐀𝐦𝐞𝐫𝐢𝐜𝐚𝐧 𝐄𝐱𝐩𝐫𝐞𝐬𝐬 card support"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 10: Wells Fargo (special character)")
    print("=" * 60)
    brand_ = "Wells Fargo"
    text_ = "W.E.L.L.S F.A.R.G.O support team"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 11: State Farm (homoglyph test)")
    print("=" * 60)
    brand_ = "State Farm"
    text_ = "Stɑte Fɑrm insurance support"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)
    
    print("\n" + "=" * 60)
    print("Test 12: PayPal (Cyrillic homoglyph)")
    print("=" * 60)
    brand_ = "PayPal"
    text_ = "Pаypal account verification"
    print(f"Text: {text_}")
    print(f"Brand: {brand_}")
    result = main(brand_.lower(), text_.lower())
    print("Result:", result)

