[app]
title = My Shopping Lists
package.name = myshoppinglists
package.domain = org.u99119
source.dir = .
source.include_exts = py
source.include_patterns = msl/*,msl/core/*,msl/ui/*,msl/cal/*
source.exclude_dirs = tests, .venv, .buildozer, bin, .pytest_cache
version = 1.0.0

# kivymd 1.2.0 needs these at runtime on Android. Google* + requests/urllib3/certifi/charset-normalizer/idna/
# httplib2/oauthlib/requests-oauthlib/cachetools/pyasn1/pyasn1-modules/rsa/uritemplate/six support MY CAL (Phase 2b).
requirements = python3,kivy==2.3.1,kivymd==1.2.0,pyjnius,android,materialyoucolor,exceptiongroup,asyncgui,asynckivy,pillow,sqlite3,google-auth,google-auth-oauthlib,google-api-python-client,httplib2,oauthlib,requests-oauthlib,requests,urllib3,certifi,charset-normalizer,idna,cachetools,pyasn1,pyasn1-modules,rsa,uritemplate,six

orientation = portrait
fullscreen = 0

# Targets Android 16 (API 36). minapi is 35 because NDK r28c (the version python-for-android
# pins) ships libraries only up to API 35, and Buildozer uses minapi as the NDK API level.
# INTERNET is required by MY CAL for Google OAuth + Calendar API calls.
android.api = 36
android.minapi = 35
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = android.permission.INTERNET

[buildozer]
log_level = 2
warn_on_root = 1
