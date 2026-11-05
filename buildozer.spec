[app]
title = My Shopping Lists
package.name = myshoppinglists
package.domain = org.u99119
source.dir = .
source.include_exts = py
source.include_patterns = msl/*,msl/core/*,msl/ui/*,msl/cal/*
source.exclude_dirs = tests, .venv, .buildozer, bin, .pytest_cache
version = 1.0.0

# kivymd 1.2.0 needs these at runtime on Android. MY CAL does OAuth2 + Calendar REST by
# hand against the public endpoints using `requests`. google-auth / google-auth-oauthlib
# are deliberately NOT included: they transitively require `cryptography`, whose native
# extensions don't build cleanly on Android. google-api-python-client is also avoided
# because it drags in protobuf, which has no Android wheel on PyPI.
requirements = python3,kivy==2.3.1,kivymd==1.2.0,pyjnius,android,materialyoucolor,exceptiongroup,asyncgui,asynckivy,pillow,sqlite3,requests,urllib3,certifi,charset-normalizer,idna

orientation = portrait
fullscreen = 0

# Targets Android 16 (API 36). minapi is 35 because NDK r28c (the version python-for-android
# pins) ships libraries only up to API 35, and Buildozer uses minapi as the NDK API level.
# INTERNET is required by MY CAL for Google OAuth + Calendar API calls.
android.api = 36
android.minapi = 35
android.archs = arm64-v8a
android.accept_sdk_license = True
# QUERY_ALL_PACKAGES is needed so the OAuth flow can resolve a browser via
# Intent(ACTION_VIEW, https://...) on API 30+ (strict package visibility).
android.permissions = android.permission.INTERNET, android.permission.QUERY_ALL_PACKAGES

[buildozer]
log_level = 2
warn_on_root = 1
