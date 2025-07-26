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

def markdown_escape(code: str) -> str:
    return code.replace('\\', '\\\\').replace('`', '\\`')

def pro_idx_to_pro_alphabet(num: int) -> str:
    s = "p"

    if num >= 26:
        i = num // 26 - 1
        num %= 26
        s += chr(65 + i)

    s += chr(65 + num)

    return s
