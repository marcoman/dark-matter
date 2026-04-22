cmake_minimum_required(VERSION 3.21)

project(dark_matter_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# Crow is a small C++ web framework. We fetch the sources at build time.
FetchContent_Declare(
  Crow
  GIT_REPOSITORY https://github.com/CrowCpp/Crow.git
  GIT_TAG v1.3.2
)
FetchContent_MakeAvailable(Crow)

add_executable(dark-matter-cpp
  src/main.cpp
)

target_link_libraries(dark-matter-cpp PRIVATE Crow::Crow)
