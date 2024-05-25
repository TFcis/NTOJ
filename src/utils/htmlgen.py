import config

def set_page_title(title: str, site_title: str = None):
    if site_title is None:
        site_title = config.SITE_TITLE

    if title == "":
        t = site_title
    else:
        t = f"{title} | {site_title}"

    return f"""
    <script>
        document.title = "{t}";
    </script>
    """
