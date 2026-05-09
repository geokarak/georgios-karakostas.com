AUTHOR = "Georgios Karakostas"
SITENAME = "Georgios Karakostas"
SITEURL = ""
SITE_DESCRIPTION = "My personal website"

TIMEZONE = "Europe/Brussels"
DEFAULT_LANG = "en"

PATH = "content"
STATIC_PATHS = [
    "extra/CNAME",
    "extra/favicons",
    "extra/robots.txt",
    "images",
    "extra",
]


EXTRA_PATH_METADATA = {
    "extra/CNAME": {"extra/CNAME": {"path": "CNAME"}},
    "extra/robots.txt": {"path": "robots.txt"},
}

FAVICONS_LIST = [
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
    "apple-touch-icon.png",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon.ico",
    "site.webmanifest",
]
for favicon in FAVICONS_LIST:
    EXTRA_PATH_METADATA[f"extra/favicons/{favicon}"] = {"path": f"favicons/{favicon}"}

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

DEFAULT_PAGINATION = False

# Uncomment following line if you want document-relative URLs when developing
# RELATIVE_URLS = True

PAGE_URL = "{slug}/"
PAGE_SAVE_AS = "{slug}.html"
PAGE_PATHS = ["pages"]
DEFAULT_CATEGORY = "blog"
ARTICLE_URL = "{category}/{slug}.html"
ARTICLE_SAVE_AS = "{category}/{slug}.html"
ARTICLE_EXCLUDES = ["html"]
ARTICLE_PATHS = ["articles"]
CATEGORY_URL = "category/{slug}.html"
CATEGORY_SAVE_AS = "category/{slug}.html"
USE_FOLDER_AS_CATEGORY = False
DRAFT_URL = "drafts/{slug}.html"

PLUGIN_PATHS = ["plugins"]
PLUGINS = ["plugins.photos"]
