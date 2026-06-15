#!/usr/bin/env python3
"""CutCtx compress helper — compress text from stdin or a file.

Usage:
    echo "large text" | python3 compress.py
    python3 compress.py --file large_file.txt
    python3 compress.py --model claude-3-opus --text "your text here"
"""
import argparse
import sys
import json


def compress_text(text: str, model: str = "claude-3-opus") -> dict:
    """Compress text using CutCtx and return stats."""
    try:
        from headroom.compress import compress
        result = compress(text, model=model)
        return {
            "original_tokens": result.original_tokens,
            "compressed_tokens": result.compressed_tokens,
            "savings_percent": result.savings_percent,
            "compressed_text": result.compressed_text,
        }
    except ImportError:
        return {
            "error": "headroom-ai not installed",
            "install": "pip install headroom-ai",
        }


def main():
    parser = argparse.ArgumentParser(description="CutCtx text compression")
    parser.add_argument("--file", "-f", help="File to compress")
    parser.add_argument("--text", "-t", help="Text to compress")
    parser.add_argument("--model", "-m", default="claude-3-opus", help="Target model")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    result = compress_text(text, model=args.model)

    if args.json:
        print(json.dumps(result, indent=2))
    elif "error" in result:
        print(f"Error: {result['error']}")
        print(f"Install: {result['install']}")
        sys.exit(1)
    else:
        print(f"Original:   {result['original_tokens']} tokens")
        print(f"Compressed: {result['compressed_tokens']} tokens")
        print(f"Savings:    {result['savings_percent']:.1f}%")
        print()
        print("--- Compressed Output ---")
        print(result["compressed_text"])


if __name__ == "__main__":
    main()
