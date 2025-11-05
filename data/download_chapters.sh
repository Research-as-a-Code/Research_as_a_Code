#!/bin/bash
#
# Download HTS (Harmonized Tariff Schedule) chapters 1-99
# from the USITC website
#

set -e  # Exit on error

# Configuration
BASE_URL="https://hts.usitc.gov/reststop/file?release=currentRelease&filename=Chapter%20"
OUTPUT_DIR="./chapters"
START_CHAPTER=1
END_CHAPTER=99

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Downloading HTS chapters ${START_CHAPTER}-${END_CHAPTER}..."
echo "Output directory: $OUTPUT_DIR"
echo ""

# Download each chapter
for i in $(seq $START_CHAPTER $END_CHAPTER); do
    url="${BASE_URL}${i}"
    output_file="${OUTPUT_DIR}/Chapter_${i}.pdf"
    
    echo "[$i/$END_CHAPTER] Downloading Chapter $i..."
    
    # Download with wget, with retry logic and rate limiting
    wget \
        --quiet \
        --show-progress \
        --tries=3 \
        --wait=1 \
        --random-wait \
        --output-document="$output_file" \
        "$url" || {
            echo "  ⚠️  Failed to download Chapter $i"
            continue
        }
    
    echo "  ✓ Saved to $output_file"
done

echo ""
echo "Download complete! Files saved in: $OUTPUT_DIR"
echo "Total chapters: $(ls -1 "$OUTPUT_DIR" | wc -l)"

