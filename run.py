#!/usr/bin/env python3
import os
import sys

# Ensure we're in the right directory
os.chdir('/Users/jingtaoli/Desktop/job-tracker-v2')

# Add to path
sys.path.insert(0, os.getcwd())

# Import and run
from app import create_app

if __name__ == '__main__':
    app, scheduler = create_app()
    print(f"✓ Starting NewWhale Career v2 on port 5002...")
    app.run(host='0.0.0.0', port=5002, debug=True, use_reloader=False)
