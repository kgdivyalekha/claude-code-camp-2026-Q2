#!/bin/bash
# List all session IDs in events.db using a simple grep on the JSONL files

echo "Sessions in .boukensha/sessions:"
ls -1 .boukensha/sessions/*.jsonl 2>/dev/null | sed 's/.*\/\(.*\)\.jsonl/  \1/' | sort

echo ""
echo "Session files with their sizes:"
ls -lh .boukensha/sessions/*.jsonl 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
