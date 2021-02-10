import argparse
import contextlib
import signal
import sys

import numpy
import xarray
from PyQt5.QtWidgets import QApplication

from volumina import __version__
from volumina.api import Viewer
from volumina.colortables import default16_new
from volumina.pixelpipeline.datasources import ArraySinkSource, ArraySource
from volumina.layer import ColortableLayer, GrayscaleLayer


@contextlib.contextmanager
def volumina_viewer():
    app = QApplication(sys.argv)
    v = Viewer()
    v.editor.setInteractionMode("navigation")
    yield v
    try:
        signal.signal(signal.SIGINT, lambda *_: app.quit())
        app.exec_()
    finally:
        app.quit()


def axiorder_type(value):
    reasons = []
    if len(set(value)) != len(value):
        reasons.append("Each axis may only appear ones")

    if any(dim not in "txyzc" for dim in value):
        reasons.append("Unrecognized axis value encountered. Only allowed axes: 'txyzc'.")

    if reasons:
        reasons.append(f"Got '{value}'.")
        raise argparse.ArgumentTypeError(" ".join(reasons))

    return value


def parse_args():
    p = argparse.ArgumentParser(
        description="",
        usage="",
        epilog="",
    )
    p.add_argument("image", help="Path to .npy image")
    p.add_argument("axistags", help="Strings describing axes in image. Valid values: 'tzyxc'", type=axiorder_type)
    p.add_argument("--version", action="version", version=__version__)

    args = p.parse_args()
    return args


def reorder_to_volumina(data, axistags):
    tagged_data = xarray.DataArray(data, dims=tuple(axistags))

    all_dims = {"t", "x", "y", "z", "c"}
    add_dims = tuple(all_dims.difference(tagged_data.dims))
    tagged_data_5d = tagged_data.expand_dims(add_dims).transpose("t", "x", "y", "z", "c")
    return tagged_data_5d.data


def main():
    args = parse_args()
    data = numpy.load(args.image)
    reordered_data = reorder_to_volumina(data, args.axistags)

    with volumina_viewer() as v:
        v.addGrayscaleLayer(reordered_data, name="raw")
        v.setWindowTitle(f"Volumina - {args.image}-{args.axistags}")
        v.showMaximized()


if __name__ == "__main__":
    main()
