import pytest

from volumina.patchAccessor import PatchAccessor


class TestPatchAccessorExactBorders:
    # Given cell size of 3
    # And following numbering scheme of patch coordinate system
    # +---+---+---+
    # | 0 | 1 | 2 |
    # +---+---+---+
    # | 3 | 4 | 5 |
    # +---+---+---+
    # | 6 | 7 | 8 |
    # +---+---+---+

    @pytest.fixture
    def accessor(self,):
        return PatchAccessor(9, 9, blockSize=3)

    @pytest.mark.parametrize(
        "coords,patches",
        [
            [(1, 1, 6, 6), [0, 1, 3, 4]],  # Covers blocks in topleft corner
            [(4, 0, 9, 5), [1, 2, 4, 5]],  # Topright
            [(0, 0, 1, 1), [0]],  # First block
            [(4, 0, 5, 1), [1]],  # Second block
            [(8, 8, 9, 9), [8]],  # Last block
        ],
    )
    def test_get_patches_for_rect(self, accessor, coords, patches):
        assert accessor.getPatchesForRect(*coords) == patches

    @pytest.mark.parametrize("patch_num", range(9))
    def test_santiy_check(self, accessor, patch_num):
        sx, ex, sy, ey = accessor.getPatchBounds(patch_num)
        assert accessor.getPatchesForRect(sx, sy, ex, ey) == [patch_num]


class TestPatchAccessorWithThinEdge:
    # Layout 29x1 blocksize 9
    # +---+---+----+
    # |9x1|9x1|11x1|
    # +---+---+----+

    @pytest.fixture
    def accessor(self):
        return PatchAccessor(29, 1, blockSize=9)

    def test_patch_with_small_trailing_edge(self, accessor):
        assert accessor.patchCount == 3, "Should merge last block 1x1 into previous"

    @pytest.mark.parametrize(
        "coords,patches",
        [
            [(0, 0, 8, 1), [0]],  # 1st block
            [(8, 0, 9, 1), [0]],  # 1st block, ends are not inclusive
            [(9, 0, 16, 1), [1]],  # 2nd block
            [(18, 0, 26, 1), [2]],  # 3rd block
        ],
    )
    def test_get_patches_for_rect(self, accessor, coords, patches):
        assert accessor.getPatchesForRect(*coords) == patches

    @pytest.mark.parametrize(
        "patch_num,bounds",
        # fmt: off
        [
            [0, [0, 9, 0, 1]],  # 1st block
            [1, [9, 18, 0, 1]],  # 2nd
            [2, [18, 29, 0, 1]]  # 3rd
        ]
        # fmt: on
    )
    def test_patch_bounds(self, accessor, patch_num, bounds):
        assert accessor.getPatchBounds(patch_num) == bounds

    @pytest.mark.parametrize("patch_num", [0, 1, 2])
    def test_santiy_check(self, accessor, patch_num):
        sx, ex, sy, ey = accessor.getPatchBounds(patch_num)
        assert accessor.getPatchesForRect(sx, sy, ex, ey) == [patch_num]
