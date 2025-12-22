import argparse
import contextlib
import json
import signal
import sys
from pathlib import Path
from typing import Tuple, Union

import h5py
import numpy
import xarray
from qtpy.QtWidgets import QApplication

from volumina import __version__
from volumina.api import Viewer
from volumina.colortables import default16_new
from volumina.layer import ColortableLayer, GrayscaleLayer
from volumina.pixelpipeline.datasources import ArraySinkSource, ArraySource


class _Suffixes:
    npy = [".npy"]
    h5 = [".h5", ".hdf5", ".hdf", ".ilp"]


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
        reasons.append("Each axis may only appear once")

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
    p.add_argument("image", help="Path to [.npy, .h5] image (in case of h5 with internal path)")
    p.add_argument(
        "--axistags",
        help="Strings describing axes in image. Valid values: 'tzyxc'. Required for `.npy` files.",
        type=axiorder_type,
        required=False,
    )
    p.add_argument("--version", action="version", version=__version__)

    args = p.parse_args()
    return args


def reorder_to_volumina(data, axistags):
    tagged_data = xarray.DataArray(data, dims=tuple(axistags))

    all_dims = {"t", "x", "y", "z", "c"}
    add_dims = tuple(all_dims.difference(tagged_data.dims))
    tagged_data_5d = tagged_data.expand_dims(add_dims).transpose("t", "x", "y", "z", "c")
    return tagged_data_5d.data


def is_npy(path: Path) -> bool:
    if path.suffix in _Suffixes.npy:
        return True

    return False


def _external_internal_h5(path: Path) -> Tuple[Path, Path]:
    if path.suffix in _Suffixes.h5:
        external_path = path
        # no internal path given!
        # guess if there is only one ds in file:
        with h5py.File(external_path, "r") as f:
            if len(f) == 1:
                internal_path = next(iter(f.keys()))
            else:
                raise ValueError("Could not determine internal path.")

    else:
        external_path = next(iter(a for a in path.parents if a.suffix in _Suffixes.h5), None)

        if not external_path:
            raise ValueError("Could not determine external path.")

        internal_path = path.relative_to(external_path)

    return external_path, internal_path


def is_h5(path: Path) -> bool:
    try:
        _ = _external_internal_h5(path)
    except ValueError:
        return False

    return True


def load(data_path: str) -> Tuple[numpy.ndarray, Union[str, None]]:
    p = Path(data_path)
    if is_npy(p):
        return load_npy(p), None
    elif is_h5(p):
        return load_h5(p)
    else:
        raise NotImplementedError("Unsupported file format - sorry.")


def load_npy(data_path: Path) -> numpy.ndarray:
    return numpy.load(data_path)


def determine_h5_axistags(ds: h5py.Dataset) -> str:
    if ds.dims:
        return "".join([dim.label for dim in ds.dims])
    elif "axistags" in ds.attrs:
        return "".join([ax["key"] for ax in json.loads(ds.attrs["axistags"])["axes"]])

    return ""


def load_h5(data_path: Path) -> Tuple[numpy.ndarray, str]:
    external_path, internal_path = _external_internal_h5(data_path)
    with h5py.File(external_path, "r") as f:
        ds: h5py.Dataset = f[str(internal_path)]
        axistags = determine_h5_axistags(ds)
        data = ds[()]
        return data, axistags


def main():
    args = parse_args()
    data, axistags = load(args.image)

    if not (args.axistags or axistags):
        print(f"Axistags required for file {args.image} with shape {data.shape}")
        return 1

    reordered_data = reorder_to_volumina(data, args.axistags or axistags)

    with volumina_viewer() as v:
        v.addGrayscaleLayer(reordered_data, name="raw")
        v.setWindowTitle(f"Volumina - {args.image}-{args.axistags}")
        v.showMaximized()

    return 0


if __name__ == "__main__":
    sys.exit(main())
