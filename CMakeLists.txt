cmake_minimum_required(VERSION 3.15...3.31)
project(${SKBUILD_PROJECT_NAME} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_native MODULE src/fastrectpack/_native.cpp)

# Float results must match Python bit for bit, so the compiler may not fuse a*b - c*d into a
# multiply-add (which rounds once instead of twice). Clang does that by default where the CPU has the
# instruction, for example on Apple silicon.
if(MSVC)
  target_compile_options(_native PRIVATE /fp:precise)
else()
  target_compile_options(_native PRIVATE -ffp-contract=off)
endif()

# Optional sanitizer build for the correctness phase: pip install . -C cmake.define.FASTRECTPACK_SANITIZE=address
set(FASTRECTPACK_SANITIZE "" CACHE STRING "Sanitizers to enable (address, undefined, thread)")
if(FASTRECTPACK_SANITIZE)
  if(MSVC)
    target_compile_options(_native PRIVATE /fsanitize=${FASTRECTPACK_SANITIZE} /Zi)
  else()
    target_compile_options(_native PRIVATE -fsanitize=${FASTRECTPACK_SANITIZE} -fno-omit-frame-pointer -g)
    target_link_options(_native PRIVATE -fsanitize=${FASTRECTPACK_SANITIZE})
  endif()
endif()

install(TARGETS _native LIBRARY DESTINATION fastrectpack)
