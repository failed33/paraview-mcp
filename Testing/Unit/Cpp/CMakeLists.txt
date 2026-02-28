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

function(paraview_mcp_add_cpp_test target_name source_file test_name)
  add_executable("${target_name}" "${source_file}")
  target_link_libraries(
    "${target_name}"
    PRIVATE
      ParaViewMCPBridgeCore
      "${paraview_mcp_qt_test_target}"
  )
  target_include_directories(
    "${target_name}"
    PRIVATE
      ${PROJECT_SOURCE_DIR}/Testing/CppSupport
  )
  set_target_properties(
    "${target_name}"
    PROPERTIES
      AUTOMOC ON
  )
  paraview_mcp_configure_target("${target_name}")
  add_test(NAME "${test_name}" COMMAND "${target_name}")
endfunction()

paraview_mcp_add_cpp_test(
  TestParaViewMCPProtocol
  TestParaViewMCPProtocol.cxx
  ParaViewMCP.Protocol
)
paraview_mcp_add_cpp_test(
  TestParaViewMCPServerConfig
  TestParaViewMCPServerConfig.cxx
  ParaViewMCP.ServerConfig
)
paraview_mcp_add_cpp_test(
  TestParaViewMCPRequestHandler
  TestParaViewMCPRequestHandler.cxx
  ParaViewMCP.RequestHandler
)
paraview_mcp_add_cpp_test(
  TestParaViewMCPSocketBridge
  TestParaViewMCPSocketBridge.cxx
  ParaViewMCP.SocketBridge
)
