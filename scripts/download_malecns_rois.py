"""MaleCNS 뇌/VNC neuropil ROI 메시(neuroglancer precomputed)를 data/malecns/rois 에 내려받는다."""
import json
import pathlib
import urllib.parse
import urllib.request

BUCKET = "flyem-male-cns"
PREFIXES = [
    "rois/fullbrain-roi-v4/",
    "rois/malecns-vnc-neuropil-roi-v0/",
]
SUBDIRS = ("info", "mesh/", "segment_properties/")
DEST = pathlib.Path(__file__).resolve().parent.parent / "data" / "malecns"


def list_objects(prefix):
    token = None
    while True:
        q = {"prefix": prefix, "maxResults": "1000"}
        if token:
            q["pageToken"] = token
        url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url) as r:
            data = json.load(r)
        yield from data.get("items", [])
        token = data.get("nextPageToken")
        if not token:
            return


def main():
    count = 0
    for root in PREFIXES:
        for sub in SUBDIRS:
            for obj in list_objects(root + sub):
                out = DEST / obj["name"]
                if out.exists() and out.stat().st_size == int(obj["size"]):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://storage.googleapis.com/{BUCKET}/" + urllib.parse.quote(obj["name"])
                urllib.request.urlretrieve(url, out)
                count += 1
    print(f"downloaded {count} files to {DEST / 'rois'}")


if __name__ == "__main__":
    main()
