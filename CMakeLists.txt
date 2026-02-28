cmake_minimum_required(VERSION 3.24)

project(ParaViewMCP VERSION 0.1.0 LANGUAGES CXX) # x-release-please-version

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(BUILD_SHARED_LIBS ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(
  ParaView 6.0 REQUIRED
  COMPONENTS
    pqApplicationComponents
    pqComponents
    RemotingServerManagerPython
)

include(GNUInstallDirs)
include(CTest)
include("${CMAKE_CURRENT_SOURCE_DIR}/CMake/ParaViewMCPDevTools.cmake")
include("${ParaView_DIR}/ParaViewPlugin.cmake")

paraview_plugin_find_plugins(
  PARAVIEW_MCP_PLUGIN_FILES
  "${CMAKE_CURRENT_SOURCE_DIR}/Plugins"
)

paraview_plugin_scan(
  PLUGIN_FILES ${PARAVIEW_MCP_PLUGIN_FILES}
  PROVIDES_PLUGINS PARAVIEW_MCP_PLUGINS
  ENABLE_BY_DEFAULT ON
  HIDE_PLUGINS_FROM_CACHE ON
)

paraview_plugin_build(
  PLUGINS ${PARAVIEW_MCP_PLUGINS}
  TARGET ParaViewMCPPlugins
  INSTALL_EXPORT ParaViewMCP
  CMAKE_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/ParaViewMCP"
  PLUGINS_FILE_NAME "ParaViewMCP.plugins.xml"
  LIBRARY_SUBDIRECTORY "paraview-6.0/plugins"
)

if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
