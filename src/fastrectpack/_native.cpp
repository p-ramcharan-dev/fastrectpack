// Native core for the MaxRects family of rectpack (https://github.com/secnot/rectpack, Apache-2.0).
//
// This is a port of rectpack.maxrects (MaxRectsBl / Bssf / Baf / Blsf). It reproduces the original's behaviour
// exactly, including its quirks:
//   * candidates are scanned in free-rectangle order, normal orientation first, then rotated, and the FIRST
//     minimal candidate wins (Python's min() semantics);
//   * MaxRectsBl compares only (y + height); its docstring promises an x tie-break but the code does not do it;
//   * _remove_duplicates removes every free rectangle whose *value* equals that of a contained rectangle, so two
//     identical free rectangles are both dropped.
//
// The algorithm is written once (CoreT) and instantiated twice:
//   * CoreT<i64>: every size is a plain Python int. Exact 64-bit integer arithmetic.
//   * CoreT<Num>: sizes are any mix of Python int, Python float, numpy.float64 and numpy.int64. Every value is
//     a double plus a tag that records which Python type the original would have produced, so results have the
//     same values AND the same types as the original.
//
// Anything else (Decimal, bool, other numpy types, NaN, infinity, zero, negative or very large sizes) raises
// Deopt and the Python wrapper falls back to the original code.

#include <pybind11/pybind11.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <tuple>
#include <vector>

namespace py = pybind11;
using i64 = std::int64_t;

namespace {

// Largest size on the all-int path: keeps every sum, and the products used by Baf, far from int64 overflow.
constexpr i64 kLimit = i64(1) << 30;
// Largest size on the mixed path for Baf: the product of two integers must stay exact in a double (2^52).
constexpr i64 kMixedBafLimit = i64(1) << 26;

// The mixed path needs double arithmetic that is evaluated exactly as written (no x87 excess precision).
// Where the compiler cannot promise that, the mixed path is switched off and those inputs fall back.
#if defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD == 0
constexpr bool kMixedPath = true;
#else
constexpr bool kMixedPath = false;
#endif

struct Deopt : std::runtime_error {
    Deopt() : std::runtime_error("input outside the native fast path") {}
};

// Which Python type a value has. Chosen so that the type of `a + b`, `a - b` and `a * b` is `a.tag | b.tag`:
// bit 0 = floating point, bit 1 = numpy scalar. For example int + numpy.float64 -> numpy.float64 (0 | 3 = 3)
// and numpy.int64 * float -> numpy.float64 (2 | 1 = 3), as in Python.
enum Tag : std::uint8_t { kPyInt = 0, kPyFloat = 1, kNpInt = 2, kNpFloat = 3 };

// A number on the mixed path. Integers are held in the double too: every integer that can occur is below 2^53,
// so it is represented exactly, and comparing an integer with a float gives the same answer as Python.
struct Num {
    double v;
    std::uint8_t tag;
};
inline Num operator+(Num a, Num b) { return Num{a.v + b.v, static_cast<std::uint8_t>(a.tag | b.tag)}; }
inline Num operator-(Num a, Num b) { return Num{a.v - b.v, static_cast<std::uint8_t>(a.tag | b.tag)}; }
inline Num operator*(Num a, Num b) { return Num{a.v * b.v, static_cast<std::uint8_t>(a.tag | b.tag)}; }
// Comparisons look at the value only, as Python does (5 == 5.0, and hash(5) == hash(5.0)).
inline bool operator==(Num a, Num b) { return a.v == b.v; }
inline bool operator<(Num a, Num b) { return a.v < b.v; }
inline bool operator<=(Num a, Num b) { return a.v <= b.v; }
inline bool operator>(Num a, Num b) { return a.v > b.v; }
inline bool operator>=(Num a, Num b) { return a.v >= b.v; }

template <class V>
struct RectT {
    V x, y, w, h;
    V top() const { return y + h; }
    V right() const { return x + w; }
    bool operator==(const RectT& o) const { return x == o.x && y == o.y && w == o.w && h == o.h; }
    bool operator<(const RectT& o) const { return std::tie(x, y, w, h) < std::tie(o.x, o.y, o.w, o.h); }
};

enum Variant : int { kBl = 0, kBssf = 1, kBaf = 2, kBlsf = 3 };

// rectpack Rectangle.contains(): `a` contains `b`
template <class V>
inline bool contains(const RectT<V>& a, const RectT<V>& b) {
    return b.y >= a.y && b.x >= a.x && b.top() <= a.top() && b.right() <= a.right();
}

template <class V>
class CoreT {
public:
    using Rect = RectT<V>;

    CoreT(V width, V height, bool rot, Variant variant) : rot_(rot), variant_(variant) {
        free_.push_back(Rect{V{}, V{}, width, height});
    }
    CoreT(std::vector<Rect> free, bool rot, Variant variant) : rot_(rot), variant_(variant), free_(std::move(free)) {}

    // Returns false when the rectangle cannot be placed.
    bool fitness(V w, V h, V& out) const {
        Rect placed;
        size_t idx;
        if (!select(w, h, placed, idx)) return false;
        out = rect_fitness(free_[idx], placed.w, placed.h);
        return true;
    }

    bool add_rect(V w, V h, Rect& placed) {
        size_t idx;
        if (!select(w, h, placed, idx)) return false;
        split(placed);
        return true;
    }

    const std::vector<Rect>& free_rects() const { return free_; }

private:
    // Mirrors MaxRects*._rect_fitness for the variant. Caller guarantees (cw, ch) fits inside m.
    // std::min and std::max return their first argument on a tie, as Python's min() and max() do.
    V rect_fitness(const Rect& m, V cw, V ch) const {
        switch (variant_) {
            case kBssf:
                return std::min(m.w - cw, m.h - ch);
            case kBaf:
                return m.w * m.h - cw * ch;
            case kBlsf:
                return std::max(m.w - cw, m.h - ch);
            default:
                return V{};  // MaxRectsBl uses the base-class fitness: the int 0
        }
    }

    // Mirrors MaxRects*._select_position: first minimal candidate, normal orientation before rotated.
    bool select(V w, V h, Rect& placed, size_t& idx) const {
        bool have = false;
        V best_key{};
        for (size_t i = 0; i < free_.size(); ++i) {
            const Rect& m = free_[i];
            if (w <= m.w && h <= m.h) {
                V key = (variant_ == kBl) ? m.y + h : rect_fitness(m, w, h);
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
                    V key = (variant_ == kBl) ? m.y + w : rect_fitness(m, h, w);
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

        // _remove_duplicates. The original looks at every pair (a before b in the list): if a contains b it
        // marks b, otherwise if b contains a it marks a. It then drops every rectangle whose VALUE equals a
        // marked one. Because the list it leaves behind never contains a containing pair, only pairs that
        // involve a newly created piece can be marked, so checking those is equivalent to the original's
        // all-pairs scan (verified against the original by the parity tests).
        // The "otherwise" could matter with floats: two rectangles with different widths would each contain the
        // other if x + width rounded to the same number, and then only the later one is marked. No fuzz run has
        // produced that case, but the rule is copied as written.
        std::vector<Rect> flagged;
        const size_t n = next.size();
        for (size_t i = 0; i < n; ++i) {
            if (!is_new[i]) continue;
            for (size_t j = 0; j < n; ++j) {
                if (j == i) continue;
                const size_t a = std::min(i, j), b = std::max(i, j);
                if (contains(next[a], next[b])) {
                    flagged.push_back(next[b]);
                } else if (contains(next[b], next[a])) {
                    flagged.push_back(next[a]);
                }
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

// ---------------------------------------------------------------------------------------------------------
// Reading Python numbers

// numpy is never imported from here. Its scalar types are looked up the first time an object whose type name
// starts with "numpy." is seen, which can only happen after the caller has imported numpy.
PyTypeObject* g_np_float64 = nullptr;
PyTypeObject* g_np_int64 = nullptr;

void find_numpy_types(PyObject* o) {
    if (g_np_float64 != nullptr || std::strncmp(Py_TYPE(o)->tp_name, "numpy.", 6) != 0) return;
    PyObject* numpy = PyDict_GetItemString(PyImport_GetModuleDict(), "numpy");  // borrowed
    if (numpy == nullptr) return;
    PyObject* f = PyObject_GetAttrString(numpy, "float64");
    PyObject* i = PyObject_GetAttrString(numpy, "int64");
    if (f != nullptr && i != nullptr && PyType_Check(f) && PyType_Check(i) &&
        PyType_IsSubtype(reinterpret_cast<PyTypeObject*>(f), &PyFloat_Type)) {
        g_np_float64 = reinterpret_cast<PyTypeObject*>(f);  // references kept for the life of the process
        g_np_int64 = reinterpret_cast<PyTypeObject*>(i);
        return;
    }
    PyErr_Clear();
    Py_XDECREF(f);
    Py_XDECREF(i);
}

// Exact Python int only (not bool, not a subclass). Returns false when it does not fit in 64 bits.
bool as_i64(PyObject* o, i64& out) {
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

// One size as given by the caller. `is_int` means a plain Python int, which is also valid on the all-int path.
struct Arg {
    bool is_int;
    i64 i;
    Num n;
};

// Accepts int, float, numpy.float64 and numpy.int64 with 0 < value <= 2^30. Everything else: Deopt.
Arg read_size(PyObject* o) {
    Arg a{false, 0, Num{0.0, kPyInt}};
    if (PyLong_CheckExact(o)) {
        if (!as_i64(o, a.i) || a.i < 1 || a.i > kLimit) throw Deopt();
        a.is_int = true;
        a.n = Num{static_cast<double>(a.i), kPyInt};
        return a;
    }
    if (!kMixedPath) throw Deopt();
    if (PyFloat_CheckExact(o)) {
        a.n = Num{PyFloat_AS_DOUBLE(o), kPyFloat};
    } else {
        find_numpy_types(o);
        if (g_np_float64 != nullptr && Py_TYPE(o) == g_np_float64) {
            a.n = Num{PyFloat_AS_DOUBLE(o), kNpFloat};  // numpy.float64 is a subclass of float
        } else if (g_np_int64 != nullptr && Py_TYPE(o) == g_np_int64) {
            PyObject* as_int = PyNumber_Index(o);
            if (as_int == nullptr) {
                PyErr_Clear();
                throw Deopt();
            }
            i64 v = 0;
            const bool ok = as_i64(as_int, v);
            Py_DECREF(as_int);
            if (!ok || v < 1 || v > kLimit) throw Deopt();
            a.n = Num{static_cast<double>(v), kNpInt};
        } else {
            throw Deopt();
        }
    }
    // Written so that NaN fails the test; infinity fails the upper bound.
    if (!(a.n.v > 0.0 && a.n.v <= static_cast<double>(kLimit))) throw Deopt();
    return a;
}

py::object to_py(i64 v) { return py::reinterpret_steal<py::object>(PyLong_FromLongLong(v)); }

py::object to_py(Num n) {
    PyObject* out = nullptr;
    switch (n.tag) {
        case kPyInt:
            out = PyLong_FromLongLong(static_cast<long long>(n.v));
            break;
        case kPyFloat:
            out = PyFloat_FromDouble(n.v);
            break;
        case kNpFloat:
            out = PyObject_CallFunction(reinterpret_cast<PyObject*>(g_np_float64), "d", n.v);
            break;
        default:
            out = PyObject_CallFunction(reinterpret_cast<PyObject*>(g_np_int64), "L", static_cast<long long>(n.v));
            break;
    }
    if (out == nullptr) throw py::error_already_set();
    return py::reinterpret_steal<py::object>(out);
}

template <class V>
py::object rect_to_py(const RectT<V>& r) {
    return py::make_tuple(to_py(r.x), to_py(r.y), to_py(r.w), to_py(r.h));
}

// ---------------------------------------------------------------------------------------------------------
// What Python sees: starts on the all-int path when it can, and moves to the mixed path, once, on the first
// size that is not a plain int.
class Core {
public:
    Core(py::handle width, py::handle height, bool rot, int variant)
        : rot_(rot), variant_(static_cast<Variant>(variant)) {
        const Arg w = read_size(width.ptr()), h = read_size(height.ptr());
        if (w.is_int && h.is_int) {
            int_ = std::make_unique<CoreT<i64>>(w.i, h.i, rot_, variant_);
        } else {
            check_mixed(w);
            check_mixed(h);
            num_ = std::make_unique<CoreT<Num>>(w.n, h.n, rot_, variant_);
        }
    }

    py::object fitness(py::handle width, py::handle height) {
        const Arg w = read_size(width.ptr()), h = read_size(height.ptr());
        if (int_ && w.is_int && h.is_int) {
            i64 f;
            if (!int_->fitness(w.i, h.i, f)) return py::none();
            return to_py(f);
        }
        to_mixed(w, h);
        Num f;
        if (!num_->fitness(w.n, h.n, f)) return py::none();
        return to_py(f);
    }

    py::object add_rect(py::handle width, py::handle height) {
        const Arg w = read_size(width.ptr()), h = read_size(height.ptr());
        if (int_ && w.is_int && h.is_int) {
            RectT<i64> placed;
            if (!int_->add_rect(w.i, h.i, placed)) return py::none();
            return rect_to_py(placed);
        }
        to_mixed(w, h);
        RectT<Num> placed;
        if (!num_->add_rect(w.n, h.n, placed)) return py::none();
        return rect_to_py(placed);
    }

    py::list free_rects() const {
        py::list out;
        if (int_) {
            for (const auto& r : int_->free_rects()) out.append(rect_to_py(r));
        } else {
            for (const auto& r : num_->free_rects()) out.append(rect_to_py(r));
        }
        return out;
    }

    const char* mode() const { return int_ ? "int" : "mixed"; }

private:
    void check_mixed(const Arg& a) const {
        if (variant_ == kBaf && a.n.v > static_cast<double>(kMixedBafLimit)) throw Deopt();
    }

    // Makes sure the mixed core is the active one. Throws Deopt, leaving the state untouched, when a size is
    // too large for it.
    void to_mixed(const Arg& w, const Arg& h) {
        check_mixed(w);
        check_mixed(h);
        if (num_) return;
        std::vector<RectT<Num>> free;
        free.reserve(int_->free_rects().size());
        for (const auto& r : int_->free_rects()) {
            // Every coordinate is at most the bin size, so checking the far edges covers all four numbers.
            if (variant_ == kBaf && (r.right() > kMixedBafLimit || r.top() > kMixedBafLimit)) throw Deopt();
            free.push_back(RectT<Num>{Num{static_cast<double>(r.x), kPyInt}, Num{static_cast<double>(r.y), kPyInt},
                                      Num{static_cast<double>(r.w), kPyInt}, Num{static_cast<double>(r.h), kPyInt}});
        }
        num_ = std::make_unique<CoreT<Num>>(std::move(free), rot_, variant_);
        int_.reset();
    }

    bool rot_;
    Variant variant_;
    std::unique_ptr<CoreT<i64>> int_;
    std::unique_ptr<CoreT<Num>> num_;
};

}  // namespace

PYBIND11_MODULE(_native, m) {
    m.doc() = "Native core for the MaxRects family of rectpack (int, float and numpy scalar sizes)";
    py::register_exception<Deopt>(m, "Deopt");

    py::class_<Core>(m, "Core")
        .def(py::init<py::handle, py::handle, bool, int>(), py::arg("width"), py::arg("height"), py::arg("rot"),
             py::arg("variant"))
        .def("fitness", &Core::fitness)
        .def("add_rect", &Core::add_rect)
        .def("free_rects", &Core::free_rects)
        .def_property_readonly("mode", &Core::mode);

    m.attr("BL") = static_cast<int>(kBl);
    m.attr("BSSF") = static_cast<int>(kBssf);
    m.attr("BAF") = static_cast<int>(kBaf);
    m.attr("BLSF") = static_cast<int>(kBlsf);
    m.attr("MIXED_PATH") = kMixedPath;
}
