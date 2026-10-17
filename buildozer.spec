[app]
title = My Shopping Lists
package.name = myshoppinglists
package.domain = org.u99119
source.dir = .
source.include_exts = py
source.include_patterns = msl/*,msl/core/*,msl/ui/*
source.exclude_dirs = tests, .venv, .buildozer, bin, .pytest_cache
version = 1.0.0

# kivymd 1.2.0 needs these at runtime on Android
requirements = python3,kivy==2.3.1,kivymd==1.2.0,pyjnius,android,materialyoucolor,exceptiongroup,asyncgui,asynckivy,pillow,sqlite3

orientation = portrait
fullscreen = 0

# Android 16 (API 36) and newer only. No permissions needed: sharing and files use system pickers.
android.api = 36
android.minapi = 36
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions =

[buildozer]
log_level = 2
warn_on_root = 1
