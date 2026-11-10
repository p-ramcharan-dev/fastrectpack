"""Demonstrations of behaviour found in the ORIGINAL rectpack 0.2.2 while porting. Nothing here is 'fixed' in
fastrectpack: the accelerated classes reproduce or inherit all of it on purpose."""
import rectpack
from rectpack.geometry import Rectangle

# 1. validate_packing() never compares the LAST rectangle with any other (loop bounds are len-2 / len-1).
a = rectpack.MaxRectsBssf(100, 100)
a.rectangles = [Rectangle(0, 0, 10, 10), Rectangle(50, 50, 10, 10), Rectangle(0, 0, 10, 10)]  # last overlaps first
try:
    a.validate_packing()
    print("1. validate_packing: overlapping LAST rectangle NOT detected (bug confirmed)")
except Exception as e:  # noqa: BLE001
    print("1. validate_packing detected the overlap:", e)
a.rectangles = [Rectangle(0, 0, 10, 10), Rectangle(0, 0, 10, 10), Rectangle(50, 50, 10, 10)]  # overlap not last
try:
    a.validate_packing()
    print("   control: overlap among earlier rectangles NOT detected")
except Exception as e:  # noqa: BLE001
    print("   control: overlap among earlier rectangles detected ->", e)

# 2. MaxRectsBl docstring promises ties go to the smallest x; the code compares only y + height.
b = rectpack.MaxRectsBl(10, 10, rot=False)
b._max_rects = [Rectangle(5, 0, 5, 10), Rectangle(0, 0, 5, 10)]  # same y; the second has the smaller x
r, _ = b._select_position(2, 2)
print(f"2. MaxRectsBl tie-break: chose x={r.x} (docstring says smallest x, i.e. 0; code takes the first candidate)")

# 3. PackerBBF.add_rect returns True/False, the other bin heuristics return the Rectangle or None.
res = {}
for name, algo in (("BNF", rectpack.PackingBin.BNF), ("BFF", rectpack.PackingBin.BFF), ("BBF", rectpack.PackingBin.BBF)):
    p = rectpack.newPacker(mode=rectpack.PackingMode.Online, bin_algo=algo)
    p.add_bin(10, 10)
    res[name] = type(p.add_rect(2, 2)).__name__
print("3. online add_rect return types:", res)
