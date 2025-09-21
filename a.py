import json
import re
import os
import requests # For fetching the online wordlist

# --- Configuration ---
INPUT_FILE = "game_list.json"
OUTPUT_FILE = "games.json"
# URL for a large English wordlist. This one is from dwyl/english-words on GitHub.
WORDLIST_URL = "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt"

# --- Wordlist Loading ---
def load_online_wordlist(url):
    """
    Loads words from an online URL, one word per line, into a lowercase set.
    Includes a fallback to a small built-in list if fetching fails.
    """
    # Small fallback wordlist if online fetch fails
    fallback_wordlist = {
        "backyard", "baseball", "soccer", "bacon", "maydie", "another", "game",
        "html", "parser", "first", "the", "word", "just", "a", "and", "is",
        "it", "in", "on", "for", "of", "to", "with", "at", "by", "from", "up",
        "down", "out", "off", "over", "under", "new", "old", "big", "small",
        "good", "bad", "great", "best", "all", "any", "some", "no", "my",
        "your", "his", "her", "its", "our", "their", "this", "that", "these",
        "those", "can", "will", "would", "should", "could", "have", "has",
        "had", "do", "does", "did", "am", "are", "is", "was", "were", "be",
        "been", "being", "man", "super", "returns", "spider", "homecoming"
    }

    try:
        print(f"Attempting to download wordlist from: {url}")
        response = requests.get(url, timeout=10) # 10-second timeout
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

        # Decode content, split by lines, filter empty ones, convert to lowercase set
        word_list_set = {word.strip().lower() for word in response.text.splitlines() if word.strip()}
        print(f"Successfully loaded {len(word_list_set)} words from online wordlist.")
        return word_list_set

    except requests.exceptions.RequestException as e:
        print(f"Error downloading wordlist from {url}: {e}")
        print("Falling back to built-in wordlist for word segmentation.")
        return fallback_wordlist
    except Exception as e:
        print(f"An unexpected error occurred while loading wordlist: {e}")
        print("Falling back to built-in wordlist for word segmentation.")
        return fallback_wordlist

# --- Core Word Separation Logic ---
def separate_words_enhanced(text, word_list_set):
    """
    Separates words in a concatenated string using general rules (CamelCase, digits)
    and then tries to further segment remaining concatenated parts using a wordlist.
    """
    if not text:
        return ""

    # Step 1: Initial splitting based on CamelCase and digit transitions
    # This handles "HTMLParser" -> "HTML Parser", "Game2000" -> "Game 2000" etc.
    temp_processed = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text) # myVar -> my Var
    temp_processed = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', temp_processed) # HTMLParser -> HTML Parser
    temp_processed = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', temp_processed) # version1 -> version 1
    temp_processed = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', temp_processed) # 1stPlace -> 1 st Place
    
    # Clean up multiple spaces and split into individual potential "words"
    initial_parts = re.sub(r' +', ' ', temp_processed).strip().split(' ')
    
    final_parts = []

    # Step 2: Iterate through initial parts and try to split further using the wordlist
    for part in initial_parts:
        if not part:
            continue

        # If the part is already a known word (case-insensitive) from the wordlist, just add it.
        # This prevents unnecessary re-segmentation of already perfect words.
        if part.lower() in word_list_set:
            final_parts.append(part)
            continue

        # Otherwise, try to segment the 'part' using the wordlist
        segmented_sub_parts = []
        current_pos = 0
        while current_pos < len(part):
            best_match_end = -1
            best_match_word = ""

            # Try to find the longest matching word from the current position
            for i in range(current_pos, len(part)):
                sub = part[current_pos : i+1]
                if sub.lower() in word_list_set:
                    # Prioritize longer matches to avoid over-splitting (e.g., "the" vs "them")
                    if len(sub) > len(best_match_word):
                        best_match_word = sub
                        best_match_end = i + 1
            
            if best_match_end != -1:
                # Found a word
                segmented_sub_parts.append(best_match_word)
                current_pos = best_match_end
            else:
                # No wordlist match found from current_pos.
                # Add the remainder of the 'part' as a single block and stop for this 'part'.
                # This prevents splitting 'unknownword' into 'u n k n o w n w o r d'.
                segmented_sub_parts.append(part[current_pos:])
                break
        
        # If the wordlist segmentation found multiple words, join them with spaces.
        # Otherwise, if it couldn't segment (e.g., 'nonewword' if not in wordlist),
        # or found only one word, add the original part (or the single segmented word).
        if segmented_sub_parts and len(segmented_sub_parts) > 1:
            final_parts.extend(segmented_sub_parts)
        else:
            final_parts.append(part) # Add the part as is if no effective segmentation occurred

    # Clean up and join all final parts
    return ' '.join(final_parts).strip()


def process_data_from_file(input_filepath, output_filepath, word_list_set):
    """
    Reads JSON data from an input file, processes 'alt' and 'title' fields
    to separate words using enhanced logic including a wordlist,
    and writes the modified data to an output file.
    """
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{input_filepath}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{input_filepath}'. Please ensure it's valid JSON.")
        return

    processed_data = []
    for item in data:
        new_item = item.copy()


        # Process 'title' field:
        # 1. Apply enhanced word separation directly. Title fields usually have existing capitalization.
        # 2. Ensure the *very first letter* of the resulting string is capitalized,
        #    preserving internal casing determined by the splitting logic.
        title_text = new_item.get("title", "")
        separated_title = separate_words_enhanced(title_text, word_list_set)
        if separated_title:
            new_item["title"] = separated_title[0].upper() + separated_title[1:]
        else:
            new_item["title"] = ""

        processed_data.append(new_item)

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=4, ensure_ascii=False) # ensure_ascii=False for proper UTF-8 output
        print(f"Processed data successfully written to '{output_filepath}'.")
    except IOError:
        print(f"Error: Could not write to output file '{output_filepath}'. Please check permissions.")

# --- Main execution ---
if __name__ == "__main__":
    # Load the wordlist once at the start from the online URL
    my_wordlist = load_online_wordlist(WORDLIST_URL)

    process_data_from_file(INPUT_FILE, OUTPUT_FILE, my_wordlist)
