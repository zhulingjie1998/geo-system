#!/usr/bin/env python
"""Test script to verify Flask routes"""
import sys
import os

# Set working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

print(f"Working directory: {os.getcwd()}")
print(f"Python path[0]: {sys.path[0]}")
print()

print("Importing app...")
from app import app

print(f"App file: {app.__file__}")
print()

# Find all routes containing 'test' or 'history'
print("Routes containing 'test':")
for rule in app.url_map.iter_rules():
    if 'test' in rule.rule.lower():
        print(f"  {rule.rule} -> {rule.endpoint}")

print()
print("Routes containing 'history':")
for rule in app.url_map.iter_rules():
    if 'history' in rule.rule.lower():
        print(f"  {rule.rule} -> {rule.endpoint}")

print()
print("Total routes:", len(list(app.url_map.iter_rules())))
