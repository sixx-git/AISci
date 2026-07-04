"""FITS 天文数据上传解析测试"""
import asyncio
import os
import tempfile
import unittest

import numpy as np

from app.skills.data_finder.file_format_registry import is_allowed_upload_filename, is_fits_format
from app.skills.data_finder.fits_extraction_skill import FitsExtractionSkill, extract_fits_tables


def _make_sample_fits(path: str, *, scaled: bool = False) -> None:
    from astropy.io import fits

    if scaled:
        cube = (np.random.randn(8, 4, 4) * 10 + 100).astype(np.int16)
        primary = fits.PrimaryHDU()
        primary.header["TELESCOP"] = "JWST"
        primary.header["INSTRUME"] = "NIRSpec"
        sci = fits.ImageHDU(cube, name="SCI")
        sci.header["BZERO"] = 100.0
        sci.header["BSCALE"] = 0.01
        hdul = fits.HDUList([primary, sci])
    else:
        cube = np.random.randn(8, 4, 4).astype(np.float32)
        primary = fits.PrimaryHDU()
        primary.header["TELESCOP"] = "JWST"
        primary.header["INSTRUME"] = "NIRSpec"
        sci = fits.ImageHDU(cube, name="SCI")
        hdul = fits.HDUList([primary, sci])
    hdul.writeto(path, overwrite=True)


class TestFitsFormatRegistry(unittest.TestCase):
    def test_fits_allowed(self):
        name = "GS9209_g235h-f170lp_cgs_s3d.fits"
        self.assertTrue(is_fits_format(name))
        self.assertTrue(is_allowed_upload_filename(name))
        self.assertTrue(is_allowed_upload_filename("data.fits.gz"))


class TestFitsExtraction(unittest.TestCase):
    def test_extract_3d_cube(self):
        try:
            import astropy  # noqa: F401
        except ImportError:
            self.skipTest("astropy 未安装")

        with tempfile.TemporaryDirectory() as tmp:
            fits_path = os.path.join(tmp, "sample_s3d.fits")
            out_dir = os.path.join(tmp, "tables")
            _make_sample_fits(fits_path)

            tables = extract_fits_tables(
                fits_path,
                source_title="JWST NIRSpec sample",
                output_dir=out_dir,
            )
            self.assertGreaterEqual(len(tables), 2)
            data_tbl = next(t for t in tables if t.get("extraction_method") == "fits_data")
            self.assertGreater(data_tbl["row_count"], 0)
            self.assertTrue(os.path.exists(data_tbl["csv_path"]))

            skill = FitsExtractionSkill()
            res = asyncio.run(skill.run({
                "file_path": fits_path,
                "source_title": "JWST",
                "output_dir": out_dir,
                "filename": "sample_s3d.fits",
            }, {}))
            self.assertTrue(res.success)
            self.assertTrue(res.data.get("tables"))

    def test_extract_scaled_jwst_like_cube(self):
        try:
            import astropy  # noqa: F401
        except ImportError:
            self.skipTest("astropy 未安装")

        with tempfile.TemporaryDirectory() as tmp:
            fits_path = os.path.join(tmp, "scaled_s3d.fits")
            out_dir = os.path.join(tmp, "tables")
            _make_sample_fits(fits_path, scaled=True)

            tables = extract_fits_tables(
                fits_path,
                source_title="JWST scaled",
                output_dir=out_dir,
            )
            self.assertGreaterEqual(len(tables), 2)
            data_tbl = next(t for t in tables if t.get("extraction_method") == "fits_data")
            self.assertGreater(data_tbl["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
