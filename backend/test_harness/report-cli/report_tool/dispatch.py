from json import dumps


def render_text(report):
    return f"{report['count']} labels: {', '.join(report['labels'])}"


def render_json(report):
    return dumps(report, sort_keys=True)


FORMATTERS = {"text": render_text, "json": render_json}


def render(report, output_format):
    handler = FORMATTERS[output_format]
    return handler(report)
