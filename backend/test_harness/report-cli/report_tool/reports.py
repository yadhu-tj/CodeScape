def normalize(label):
    return label.strip()


def build_report(labels):
    return {"count": len(labels), "labels": [normalize(label) for label in labels]}
