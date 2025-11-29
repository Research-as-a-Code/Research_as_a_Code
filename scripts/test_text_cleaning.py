#!/usr/bin/env python3
"""
Test text cleaning strategies for chunks that fail embedding

Tests various cleaning approaches:
1. UTF-8 normalization
2. ASCII conversion
3. Unicode normalization (NLTK/unicodedata)
4. Special character removal
"""

import sys
import unicodedata
from pathlib import Path


def analyze_text_issues(text: str) -> dict:
    """Analyze potential issues in text"""
    issues = {
        "length": len(text),
        "has_null_bytes": '\x00' in text,
        "has_control_chars": any(ord(c) < 32 and c not in '\n\r\t' for c in text),
        "has_non_utf8": False,
        "has_surrogates": any(0xD800 <= ord(c) <= 0xDFFF for c in text),
        "has_special_unicode": any(ord(c) > 127 for c in text),
        "is_mostly_punctuation": sum(c in '|-.,:;!?()[]{}' for c in text) / len(text) > 0.5 if text else False,
    }
    
    # Check if valid UTF-8
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        issues["has_non_utf8"] = True
    
    return issues


def clean_method_1_strict_ascii(text: str) -> str:
    """Method 1: Convert to ASCII (removes all non-ASCII)"""
    return text.encode('ascii', errors='ignore').decode('ascii')


def clean_method_2_unicode_normalize(text: str) -> str:
    """Method 2: Unicode NFKD normalization (decomposes characters)"""
    # NFKD: Compatibility decomposition
    normalized = unicodedata.normalize('NFKD', text)
    # Keep only ASCII-compatible
    return normalized.encode('ascii', errors='ignore').decode('ascii')


def clean_method_3_replace_special(text: str) -> str:
    """Method 3: Replace common problematic characters"""
    replacements = {
        '\x00': '',  # Null bytes
        '\r\n': '\n',  # Windows line endings
        '\r': '\n',  # Old Mac line endings
        '\u200b': '',  # Zero-width space
        '\ufeff': '',  # BOM
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2013': '-',  # En dash
        '\u2014': '--',  # Em dash
        '\u2026': '...',  # Ellipsis
    }
    
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    # Remove control characters except newline, tab
    result = ''.join(c for c in result if ord(c) >= 32 or c in '\n\t')
    
    return result


def clean_method_4_smart_unicode(text: str) -> str:
    """Method 4: Keep unicode but normalize (best for international text)"""
    # NFKC: Compatibility composition (normalizes similar chars)
    normalized = unicodedata.normalize('NFKC', text)
    
    # Remove control chars and surrogates
    cleaned = ''.join(
        c for c in normalized
        if not unicodedata.category(c).startswith('C')  # Control chars
        and not (0xD800 <= ord(c) <= 0xDFFF)  # Surrogates
    )
    
    return cleaned


def test_on_problematic_chunks():
    """Test cleaning methods on known problematic patterns"""
    
    print("=" * 80)
    print("TESTING TEXT CLEANING METHODS")
    print("=" * 80)
    print()
    
    # Problematic chunks found in tariffs
    test_cases = [
        ("Table artifact", "|---|---|---|---|---|---|"),
        ("Null bytes", "Text with\x00null\x00bytes"),
        ("Control chars", "Text\x01with\x02control\x03chars"),
        ("Smart quotes", 'The "quote" and \'apostrophe\' test with smart: \u201cquotes\u201d'),
        ("Em/En dashes", "Range 1–10 (that's an en-dash) or this—em dash"),
        ("Mixed unicode", "Café résumé naïve"),
        ("Whitespace only", "   \n  \t  \n   "),
        ("Normal text", "The tariff code for chocolate is 1806.32."),
    ]
    
    methods = [
        ("Original", lambda x: x),
        ("Strict ASCII", clean_method_1_strict_ascii),
        ("Unicode NFKD→ASCII", clean_method_2_unicode_normalize),
        ("Replace Special", clean_method_3_replace_special),
        ("Smart Unicode", clean_method_4_smart_unicode),
    ]
    
    for test_name, test_text in test_cases:
        print(f"\n📝 Test: {test_name}")
        print("-" * 80)
        print(f"Input: '{test_text}'")
        print(f"Issues: {analyze_text_issues(test_text)}")
        print()
        
        for method_name, clean_func in methods:
            try:
                cleaned = clean_func(test_text)
                issues_after = analyze_text_issues(cleaned)
                
                # Check if potentially embeddable
                embeddable = (
                    len(cleaned.strip()) > 10 and
                    not issues_after['has_null_bytes'] and
                    not issues_after['has_control_chars'] and
                    not issues_after['is_mostly_punctuation']
                )
                
                status = "✅" if embeddable else "❌"
                print(f"  {status} {method_name:25} → '{cleaned[:50]}...' ({len(cleaned)} chars)")
                
            except Exception as e:
                print(f"  ❌ {method_name:25} → ERROR: {e}")
        
        print()
    
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()
    print("Based on tests:")
    print("  ✅ Method 4 (Smart Unicode) - Best for international text")
    print("     • Keeps unicode (café, résumé)")
    print("     • Removes problematic control chars")
    print("     • Normalizes similar characters")
    print()
    print("  ✅ Method 3 (Replace Special) - Good for English-heavy")
    print("     • Converts smart quotes to regular")
    print("     • Handles common issues")
    print("     • ASCII-friendly")
    print()
    print("For your use case (tariffs, congress, sustainability):")
    print("  → Method 4 (Smart Unicode) recommended")
    print("  → Preserves international content")
    print("  → Removes problematic characters")


def test_on_real_file(file_path: str):
    """Test on actual file and count potential issues"""
    print("\n" + "=" * 80)
    print(f"TESTING REAL FILE: {Path(file_path).name}")
    print("=" * 80)
    print()
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    print(f"File size: {len(text):,} characters")
    print()
    
    # Simulate chunking (simple 1000 char chunks)
    chunks = []
    start = 0
    while start < len(text):
        end = start + 1000
        chunk = text[start:end]
        if len(chunk) > 50:
            chunks.append(chunk)
        start += 800
    
    print(f"Chunks: {len(chunks)}")
    print()
    
    # Analyze each chunk
    problematic = []
    for i, chunk in enumerate(chunks):
        issues = analyze_text_issues(chunk)
        if any([
            issues['has_null_bytes'],
            issues['has_control_chars'],
            issues['has_surrogates'],
            issues['is_mostly_punctuation']
        ]):
            problematic.append((i, chunk, issues))
    
    print(f"Problematic chunks: {len(problematic)} / {len(chunks)} ({len(problematic)/len(chunks)*100:.1f}%)")
    print()
    
    if problematic:
        print("Sample problematic chunks:")
        for i, (idx, chunk, issues) in enumerate(problematic[:3]):
            print(f"\n  Chunk {idx+1}:")
            print(f"    Issues: {[k for k,v in issues.items() if v and k != 'length']}")
            print(f"    Preview: {chunk[:100]}...")
            print(f"    After Method 4: {clean_method_4_smart_unicode(chunk)[:100]}...")
    else:
        print("✅ No problematic chunks found!")
    
    return problematic


def main():
    if len(sys.argv) > 1:
        # Test on provided file
        test_on_real_file(sys.argv[1])
    else:
        # Run synthetic tests
        test_on_problematic_chunks()


if __name__ == "__main__":
    main()

