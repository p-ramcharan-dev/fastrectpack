// Native core for the MaxRects family of rectpack (https://github.com/secnot/rectpack, Apache-2.0).
//
// This is a port of rectpack.maxrects (MaxRectsBl / Bssf / Baf / Blsf) for plain Python int dimensions.
// It reproduces the original's behaviour exactly, including its quirks:
//   * candidates are scanned in free-rectangle order, normal orientation first, then rotated, and the FIRST
//     minimal candidate wins (Python's min() semantics);
//   * MaxRectsBl compares only (y + height); its docstring promises an x tie-break but the code does not do it;
//   * _remove_duplicates removes every free rectangle whose *value* equals that of a contained rectangle, so two
//     identical free rectangles are both dropped.
//
// Anything outside the exact-int fast path raises Deopt and the Python wrapper falls back to the original code.

#include <pybind11/pybind11.h>

#include <algorithm>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <tuple>
#include <vector>

namespace py = pybind11;
using i64 = std::int64_t;

namespace {

// Keep every intermediate (sums, and products used by Baf) far from int64 overflow.
constexpr i64 kLimit = i64(1) << 30;

struct Deopt : std::runtime_error {
    Deopt() : std::runtime_error("input outside the native fast path") {}
};

struct Rect {
    i64 x, y, w, h;
    i64 top() const { return y + h; }
    i64 right() const { return x + w; }
    bool operator==(const Rect& o) const { return x == o.x && y == o.y && w == o.w && h == o.h; }
    bool operator<(const Rect& o) const { return std::tie(x, y, w, h) < std::tie(o.x, o.y, o.w, o.h); }
};

enum Variant : int { kBl = 0, kBssf = 1, kBaf = 2, kBlsf = 3 };

// Exact Python int only (not bool, not numpy ints, not floats). Returns false when not representable.
bool as_i64(PyObject* o, i64& out) {
    if (!PyLong_CheckExact(o)) return false;
    int overflow = 0;
    long long v = PyLong_AsLongLongAndOverflow(o, &overflow);
    if (overflow != 0) return false;
    if (v == -1 && PyErr_Occurred()) {
        PyErr_Clear();
        return false;
    }
    out = static_cast<i64>(v);
    return true;
}

// rectpack Rectangle.contains(): `a` contains `b`
inline bool contains(const Rect& a, const Rect& b) {
    return b.y >= a.y && b.x >= a.x && b.top() <= a.top() && b.right() <= a.right();
}

class Core {
public:
    Core(i64 width, i64 height, bool rot, int variant) : rot_(rot), variant_(static_cast<Variant>(variant)) {
        free_.push_back(Rect{0, 0, width, height});
    }

    // Returns fitness (>= 0), or -1 when the rectangle cannot be placed.
    i64 fitness(i64 w, i64 h) const {
        Rect placed;
        size_t idx;
        if (!select(w, h, placed, idx)) return -1;
        return rect_fitness(free_[idx], placed.w, placed.h);
    }

    bool add_rect(i64 w, i64 h, Rect& placed) {
        size_t idx;
        if (!select(w, h, placed, idx)) return false;
        split(placed);
        return true;
    }

    const std::vector<Rect>& free_rects() const { return free_; }

private:
    // Mirrors MaxRects*._rect_fitness for the variant. Caller guarantees (cw, ch) fits inside m.
    i64 rect_fitness(const Rect& m, i64 cw, i64 ch) const {
        switch (variant_) {
            case kBssf:
                return std::min(m.w - cw, m.h - ch);
            case kBaf:
                return m.w * m.h - cw * ch;
            case kBlsf:
                return std::max(m.w - cw, m.h - ch);
            default:
                return 0;  // MaxRectsBl uses the base-class fitness
        }
    }

    // Mirrors MaxRects*._select_position: first minimal candidate, normal orientation before rotated.
    bool select(i64 w, i64 h, Rect& placed, size_t& idx) const {
        bool have = false;
        i64 best_key = 0;
        for (size_t i = 0; i < free_.size(); ++i) {
            const Rect& m = free_[i];
            if (w <= m.w && h <= m.h) {
                i64 key = (variant_ == kBl) ? m.y + h : rect_fitness(m, w, h);
                if (!have || key < best_key) {
                    have = true;
                    best_key = key;
                    placed = Rect{m.x, m.y, w, h};
                    idx = i;
                }
            }
        }
        if (rot_) {
            for (size_t i = 0; i < free_.size(); ++i) {
                const Rect& m = free_[i];
                if (h <= m.w && w <= m.h) {
                    i64 key = (variant_ == kBl) ? m.y + w : rect_fitness(m, h, w);
                    if (!have || key < best_key) {
                        have = true;
                        best_key = key;
                        placed = Rect{m.x, m.y, h, w};
                        idx = i;
                    }
                }
            }
        }
        return have;
    }

    // Mirrors MaxRects._split followed by MaxRects._remove_duplicates.
    void split(const Rect& r) {
        std::vector<Rect> next;
        std::vector<char> is_new;
        next.reserve(free_.size() + 8);
        is_new.reserve(free_.size() + 8);
        for (const Rect& m : free_) {
            bool intersects = !(m.y >= r.top() || m.top() <= r.y || m.x >= r.right() || m.right() <= r.x);
            if (!intersects) {
                next.push_back(m);
                is_new.push_back(0);
                continue;
            }
            // _generate_splits, same order: left, right, top, bottom
            if (r.x > m.x) {
                next.push_back(Rect{m.x, m.y, r.x - m.x, m.h});
                is_new.push_back(1);
            }
            if (r.right() < m.right()) {
                next.push_back(Rect{r.right(), m.y, m.right() - r.right(), m.h});
                is_new.push_back(1);
            }
            if (r.top() < m.top()) {
                next.push_back(Rect{m.x, r.top(), m.w, m.top() - r.top()});
                is_new.push_back(1);
            }
            if (r.y > m.y) {
                next.push_back(Rect{m.x, m.y, m.w, r.y - m.y});
                is_new.push_back(1);
            }
        }

        // _remove_duplicates. The original drops every rectangle whose VALUE equals the value of some rectangle
        // that is contained by another one. Because the list it leaves behind never contains a containing pair,
        // only pairs that involve a newly created piece can add to that set, so checking those is equivalent
        // to the original's all-pairs scan (verified against the original by the parity tests).
        std::vector<Rect> flagged;
        const size_t n = next.size();
        for (size_t i = 0; i < n; ++i) {
            if (!is_new[i]) continue;
            for (size_t j = 0; j < n; ++j) {
                if (j == i) continue;
                if (contains(next[i], next[j])) flagged.push_back(next[j]);
                if (contains(next[j], next[i])) flagged.push_back(next[i]);
            }
        }
        if (flagged.empty()) {
            free_.swap(next);
            return;
        }
        std::sort(flagged.begin(), flagged.end());
        flagged.erase(std::unique(flagged.begin(), flagged.end()), flagged.end());
        free_.clear();
        for (const Rect& m : next) {
            if (!std::binary_search(flagged.begin(), flagged.end(), m)) free_.push_back(m);
        }
    }

    bool rot_;
    Variant variant_;
    std::vector<Rect> free_;
};

inline void need_dim(PyObject* o, i64& out) {
    if (!as_i64(o, out) || out < 1 || out > kLimit) throw Deopt();
}

std::unique_ptr<Core> make_core(py::handle width, py::handle height, bool rot, int variant) {
    i64 w, h;
    need_dim(width.ptr(), w);
    need_dim(height.ptr(), h);
    return std::make_unique<Core>(w, h, rot, variant);
}

}  // namespace

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native core for the MaxRects family of rectpack (exact-int fast path)";
    py::register_exception<Deopt>(m, "Deopt");

    py::class_<Core>(m, "Core")
        .def(py::init(&make_core), py::arg("width"), py::arg("height"), py::arg("rot"), py::arg("variant"))
        .def("fitness",
             [](const Core& c, py::handle w, py::handle h) -> py::object {
                 i64 iw, ih;
                 need_dim(w.ptr(), iw);
                 need_dim(h.ptr(), ih);
                 i64 f = c.fitness(iw, ih);
                 if (f < 0) return py::none();
                 return py::int_(f);
             })
        .def("add_rect",
             [](Core& c, py::handle w, py::handle h) -> py::object {
                 i64 iw, ih;
                 need_dim(w.ptr(), iw);
                 need_dim(h.ptr(), ih);
                 Rect placed;
                 if (!c.add_rect(iw, ih, placed)) return py::none();
                 return py::make_tuple(placed.x, placed.y, placed.w, placed.h);
             })
        .def("free_rects", [](const Core& c) {
            py::list out;
            for (const Rect& r : c.free_rects()) out.append(py::make_tuple(r.x, r.y, r.w, r.h));
            return out;
        });

    m.attr("BL") = static_cast<int>(kBl);
    m.attr("BSSF") = static_cast<int>(kBssf);
    m.attr("BAF") = static_cast<int>(kBaf);
    m.attr("BLSF") = static_cast<int>(kBlsf);
}
