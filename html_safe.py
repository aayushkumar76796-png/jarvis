"""Safe JSON for embedding inside <script> tags. Plain json.dumps() leaves '</script>' intact, which lets text from an AI reply,
a web page or a user-typed title end the script early and inject HTML into the page. js() makes that impossible."""
import json


def js(obj):
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
