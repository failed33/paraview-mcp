include_guard(GLOBAL)

option(PARAVIEW_MCP_ENABLE_WARNINGS "Enable compiler warnings for ParaView MCP targets" ON)
option(PARAVIEW_MCP_ENABLE_CLANG_TIDY "Run clang-tidy during C++ compilation" OFF)
option(PARAVIEW_MCP_ENABLE_IWYU "Run include-what-you-use during C++ compilation" OFF)

function(paraview_mcp_get_clang_tidy_extra_args output_var)
  set(_paraview_mcp_extra_args)

  if(APPLE)
    find_program(PARAVIEW_MCP_XCRUN_BIN NAMES xcrun)
    if(PARAVIEW_MCP_XCRUN_BIN)
      execute_process(
        COMMAND "${PARAVIEW_MCP_XCRUN_BIN}" --show-sdk-path
        OUTPUT_VARIABLE _paraview_mcp_sdk_path
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
      )
      if(_paraview_mcp_sdk_path)
        list(APPEND _paraview_mcp_extra_args
          "--extra-arg-before=--driver-mode=clang++"
          "--extra-arg=-isysroot"
          "--extra-arg=${_paraview_mcp_sdk_path}"
          "--extra-arg=-iframework"
          "--extra-arg=${_paraview_mcp_sdk_path}/System/Library/Frameworks"
        )
      endif()

      execute_process(
        COMMAND "${PARAVIEW_MCP_XCRUN_BIN}" --find clang++
        OUTPUT_VARIABLE _paraview_mcp_clangxx
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
      )
      if(_paraview_mcp_clangxx)
        get_filename_component(_paraview_mcp_clangxx_bin "${_paraview_mcp_clangxx}" DIRECTORY)
        get_filename_component(_paraview_mcp_toolchain_root "${_paraview_mcp_clangxx_bin}" DIRECTORY)
        set(_paraview_mcp_libcxx_dir "${_paraview_mcp_toolchain_root}/include/c++/v1")
        if(EXISTS "${_paraview_mcp_libcxx_dir}")
          list(APPEND _paraview_mcp_extra_args
            "--extra-arg=-stdlib=libc++"
            "--extra-arg=-isystem"
            "--extra-arg=${_paraview_mcp_libcxx_dir}"
          )
        endif()
      endif()
    endif()
  endif()

  set("${output_var}" "${_paraview_mcp_extra_args}" PARENT_SCOPE)
endfunction()

function(paraview_mcp_configure_target target)
  if(NOT TARGET "${target}")
    message(FATAL_ERROR "paraview_mcp_configure_target expected an existing target: ${target}")
  endif()

  if(PARAVIEW_MCP_ENABLE_WARNINGS)
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|AppleClang")
      target_compile_options(
        "${target}"
        PRIVATE
          -Wall
          -Wextra
          -Wpedantic
          -Wconversion
          -Wsign-conversion
          -Wshadow
          -Wnon-virtual-dtor
      )
    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
      target_compile_options(
        "${target}"
        PRIVATE
          -Wall
          -Wextra
          -Wpedantic
          -Wconversion
          -Wsign-conversion
          -Wshadow
          -Wnon-virtual-dtor
      )
    elseif(MSVC)
      target_compile_options(
        "${target}"
        PRIVATE
          /W4
          /permissive-
      )
    endif()
  endif()

  if(PARAVIEW_MCP_ENABLE_CLANG_TIDY)
    find_program(PARAVIEW_MCP_CLANG_TIDY_BIN NAMES clang-tidy)
    if(PARAVIEW_MCP_CLANG_TIDY_BIN)
      paraview_mcp_get_clang_tidy_extra_args(_paraview_mcp_extra_args)
      set(_paraview_mcp_clang_tidy_args
        "${PARAVIEW_MCP_CLANG_TIDY_BIN}"
        "--config-file=${CMAKE_SOURCE_DIR}/.clang-tidy"
        "--header-filter=^${CMAKE_SOURCE_DIR}/Plugins/.*"
        ${_paraview_mcp_extra_args}
      )
      set_target_properties(
        "${target}"
        PROPERTIES
          CXX_CLANG_TIDY "${_paraview_mcp_clang_tidy_args}"
      )
    else()
      message(WARNING "PARAVIEW_MCP_ENABLE_CLANG_TIDY is ON, but clang-tidy was not found")
    endif()
  endif()

  if(PARAVIEW_MCP_ENABLE_IWYU)
    find_program(PARAVIEW_MCP_IWYU_BIN NAMES include-what-you-use iwyu)
    if(PARAVIEW_MCP_IWYU_BIN)
      set_target_properties(
        "${target}"
        PROPERTIES
          CXX_INCLUDE_WHAT_YOU_USE "${PARAVIEW_MCP_IWYU_BIN};-Xiwyu;--mapping_file=${CMAKE_SOURCE_DIR}/.iwyu.imp"
      )
    else()
      message(WARNING "PARAVIEW_MCP_ENABLE_IWYU is ON, but include-what-you-use was not found")
    endif()
  endif()
endfunction()

function(paraview_mcp_add_format_targets)
  cmake_parse_arguments(PARSE_ARGV 0 PARAVIEW_MCP_FORMAT "" "BASE_DIR" "SOURCES")

  if(NOT PARAVIEW_MCP_FORMAT_BASE_DIR)
    set(PARAVIEW_MCP_FORMAT_BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
  endif()

  set(_paraview_mcp_sources)
  foreach(_paraview_mcp_source IN LISTS PARAVIEW_MCP_FORMAT_SOURCES)
    if(IS_ABSOLUTE "${_paraview_mcp_source}")
      list(APPEND _paraview_mcp_sources "${_paraview_mcp_source}")
    else()
      list(APPEND _paraview_mcp_sources "${PARAVIEW_MCP_FORMAT_BASE_DIR}/${_paraview_mcp_source}")
    endif()
  endforeach()

  if(NOT _paraview_mcp_sources)
    return()
  endif()

  find_program(PARAVIEW_MCP_CLANG_FORMAT_BIN NAMES clang-format)
  if(NOT PARAVIEW_MCP_CLANG_FORMAT_BIN)
    message(STATUS "clang-format not found; skipping format-cpp targets")
    return()
  endif()

  add_custom_target(
    format-cpp
    COMMAND "${PARAVIEW_MCP_CLANG_FORMAT_BIN}" -i ${_paraview_mcp_sources}
    COMMENT "Formatting ParaView MCP C++ sources with clang-format"
    VERBATIM
  )

  add_custom_target(
    format-cpp-check
    COMMAND "${PARAVIEW_MCP_CLANG_FORMAT_BIN}" --dry-run --Werror ${_paraview_mcp_sources}
    COMMENT "Checking ParaView MCP C++ formatting with clang-format"
    VERBATIM
  )
endfunction()

function(paraview_mcp_add_lint_target)
  cmake_parse_arguments(PARSE_ARGV 0 PARAVIEW_MCP_LINT "" "BASE_DIR" "SOURCES")

  if(NOT PARAVIEW_MCP_LINT_BASE_DIR)
    set(PARAVIEW_MCP_LINT_BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
  endif()

  set(_paraview_mcp_sources)
  foreach(_paraview_mcp_source IN LISTS PARAVIEW_MCP_LINT_SOURCES)
    if(IS_ABSOLUTE "${_paraview_mcp_source}")
      list(APPEND _paraview_mcp_sources "${_paraview_mcp_source}")
    else()
      list(APPEND _paraview_mcp_sources "${PARAVIEW_MCP_LINT_BASE_DIR}/${_paraview_mcp_source}")
    endif()
  endforeach()

  if(NOT _paraview_mcp_sources)
    return()
  endif()

  find_program(PARAVIEW_MCP_CLANG_TIDY_BIN NAMES clang-tidy)
  if(NOT PARAVIEW_MCP_CLANG_TIDY_BIN)
    message(STATUS "clang-tidy not found; skipping lint-cpp target")
    return()
  endif()

  paraview_mcp_get_clang_tidy_extra_args(_paraview_mcp_extra_args)

  add_custom_target(
    lint-cpp
    COMMAND "${PARAVIEW_MCP_CLANG_TIDY_BIN}"
            "--config-file=${CMAKE_SOURCE_DIR}/.clang-tidy"
            ${_paraview_mcp_extra_args}
            -p
            "${CMAKE_BINARY_DIR}"
            ${_paraview_mcp_sources}
    COMMENT "Linting ParaView MCP C++ sources with clang-tidy"
    VERBATIM
  )

  add_custom_target(
    lint-cpp-fix
    COMMAND "${PARAVIEW_MCP_CLANG_TIDY_BIN}"
            "--config-file=${CMAKE_SOURCE_DIR}/.clang-tidy"
            "--fix"
            ${_paraview_mcp_extra_args}
            -p
            "${CMAKE_BINARY_DIR}"
            ${_paraview_mcp_sources}
    COMMENT "Fixing ParaView MCP C++ lint issues with clang-tidy"
    VERBATIM
  )
endfunction()
