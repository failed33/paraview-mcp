set(paraview_mcp_qt_test_target "${PARAVIEW_MCP_QT_TEST_TARGET}")

if(NOT paraview_mcp_qt_test_target)
  if(TARGET Qt6::Widgets)
    find_package(Qt6 QUIET COMPONENTS Test)
    if(TARGET Qt6::Test)
      set(paraview_mcp_qt_test_target Qt6::Test)
    endif()
  elseif(TARGET Qt5::Widgets)
    find_package(Qt5 QUIET COMPONENTS Test)
    if(TARGET Qt5::Test)
      set(paraview_mcp_qt_test_target Qt5::Test)
    endif()
  endif()
endif()

if(NOT paraview_mcp_qt_test_target)
  message(FATAL_ERROR "Qt Test is required to build ParaView MCP C++ tests")
endif()

add_executable(TestParaViewMCPLocalBridge TestParaViewMCPLocalBridge.cxx)
target_link_libraries(
  TestParaViewMCPLocalBridge
  PRIVATE
    ParaViewMCPBridgeCore
    "${paraview_mcp_qt_test_target}"
)
target_include_directories(
  TestParaViewMCPLocalBridge
  PRIVATE
    ${PROJECT_SOURCE_DIR}/Testing/CppSupport
)
set_target_properties(
  TestParaViewMCPLocalBridge
  PROPERTIES
    AUTOMOC ON
)
paraview_mcp_configure_target(TestParaViewMCPLocalBridge)
add_test(NAME ParaViewMCP.LocalBridge COMMAND TestParaViewMCPLocalBridge)
