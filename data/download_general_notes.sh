#!/bin/bash
#
# Download HTS (Harmonized Tariff Schedule) General Notes 1-36
# from the USITC learning website
#

set -e  # Exit on error

# Configuration
BASE_URL="https://learning.usitc.gov/hts-docs/documents/General%20Note%20"
OUTPUT_DIR="./tariffs"
START_NOTE=1
END_NOTE=36

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Downloading HTS General Notes ${START_NOTE}-${END_NOTE}..."
echo "Output directory: $OUTPUT_DIR"
echo ""

# Download each general note
for i in $(seq $START_NOTE $END_NOTE); do
    url="${BASE_URL}${i}.pdf"
    output_file="${OUTPUT_DIR}/General_Note_${i}.pdf"
    
    echo "[$i/$END_NOTE] Downloading General Note $i..."
    
    # Download with curl (wget is blocked by the server)
    curl \
        --silent \
        --show-error \
        --location \
        --fail \
        --retry 3 \
        --retry-delay 1 \
        --output "$output_file" \
        "$url" || {
            echo "  ⚠️  Failed to download General Note $i"
            continue
        }
    
    # Check if the downloaded file is empty (reserved or invalid notes produce 0-byte PDFs)
    if [ ! -s "$output_file" ]; then
        echo "  ⚠️  General Note $i is empty (reserved or not available) - removing"
        rm -f "$output_file"
        continue
    fi
    
    echo "  ✓ Saved to $output_file"
done

echo ""
echo "Download complete! Files saved in: $OUTPUT_DIR"
echo "Total general notes: $(ls -1 "$OUTPUT_DIR" | wc -l)"

