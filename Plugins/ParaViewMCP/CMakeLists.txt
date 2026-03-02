set(paraview_mcp_bridge_core_sources
  bridge/IParaViewMCPPythonBridge.h
  bridge/ParaViewMCPProtocol.h
  bridge/ParaViewMCPRequestHandler.cxx
  bridge/ParaViewMCPRequestHandler.h
  bridge/ParaViewMCPServerConfig.h
  bridge/ParaViewMCPSession.h
  bridge/ParaViewMCPSocketBridge.cxx
  bridge/ParaViewMCPSocketBridge.h
  bridge/ParaViewMCPPythonBridge.cxx
  bridge/ParaViewMCPPythonBridge.h
)

set(paraview_mcp_plugin_sources
  bridge/ParaViewMCPBridgeController.cxx
  bridge/ParaViewMCPBridgeController.h
  lifecycle/ParaViewMCPAutoStart.cxx
  lifecycle/ParaViewMCPAutoStart.h
  ui/ParaViewMCPActionGroup.cxx
  ui/ParaViewMCPActionGroup.h
  ui/ParaViewMCPHistoryEntry.cxx
  ui/ParaViewMCPHistoryEntry.h
  ui/ParaViewMCPPopup.cxx
  ui/ParaViewMCPPopup.h
  ui/ParaViewMCPStateAppearance.h
  ui/ParaViewMCPToolbar.cxx
  ui/ParaViewMCPToolbar.h
)

set(paraview_mcp_lint_sources
  bridge/ParaViewMCPBridgeController.cxx
  bridge/ParaViewMCPRequestHandler.cxx
  bridge/ParaViewMCPSocketBridge.cxx
  bridge/ParaViewMCPPythonBridge.cxx
  lifecycle/ParaViewMCPAutoStart.cxx
  ui/ParaViewMCPActionGroup.cxx
  ui/ParaViewMCPHistoryEntry.cxx
  ui/ParaViewMCPPopup.cxx
  ui/ParaViewMCPToolbar.cxx
)

set(paraview_mcp_all_sources
  ${paraview_mcp_bridge_core_sources}
  ${paraview_mcp_plugin_sources}
)

set(paraview_mcp_ui_interfaces)
set(paraview_mcp_ui_sources)

paraview_plugin_add_toolbar(
  CLASS_NAME ParaViewMCPToolbar
  INTERFACES paraview_mcp_toolbar_interfaces
  SOURCES paraview_mcp_toolbar_wrapper_sources
)
list(APPEND paraview_mcp_ui_interfaces ${paraview_mcp_toolbar_interfaces})
list(APPEND paraview_mcp_ui_sources ${paraview_mcp_toolbar_wrapper_sources})

paraview_plugin_add_action_group(
  CLASS_NAME ParaViewMCPActionGroup
  GROUP_NAME "MenuBar/Tools"
  INTERFACES paraview_mcp_action_interfaces
  SOURCES paraview_mcp_action_wrapper_sources
)
list(APPEND paraview_mcp_ui_interfaces ${paraview_mcp_action_interfaces})
list(APPEND paraview_mcp_ui_sources ${paraview_mcp_action_wrapper_sources})

paraview_plugin_add_auto_start(
  CLASS_NAME ParaViewMCPAutoStart
  INTERFACES paraview_mcp_autostart_interfaces
  SOURCES paraview_mcp_autostart_wrapper_sources
)
list(APPEND paraview_mcp_ui_interfaces ${paraview_mcp_autostart_interfaces})
list(APPEND paraview_mcp_ui_sources ${paraview_mcp_autostart_wrapper_sources})

set(paraview_mcp_qt_targets)
set(paraview_mcp_qt_test_target)
if(TARGET Qt6::Widgets)
  list(APPEND paraview_mcp_qt_targets Qt6::Widgets)
  set(paraview_mcp_qt_test_target Qt6::Test)
elseif(TARGET Qt5::Widgets)
  list(APPEND paraview_mcp_qt_targets Qt5::Widgets)
  set(paraview_mcp_qt_test_target Qt5::Test)
endif()

if(TARGET Qt6::Network)
  list(APPEND paraview_mcp_qt_targets Qt6::Network)
elseif(TARGET Qt5::Network)
  list(APPEND paraview_mcp_qt_targets Qt5::Network)
endif()

add_library(ParaViewMCPBridgeCore STATIC ${paraview_mcp_bridge_core_sources})
set_target_properties(
  ParaViewMCPBridgeCore
  PROPERTIES
    AUTOMOC ON
)

target_include_directories(
  ParaViewMCPBridgeCore
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/bridge
    ${CMAKE_CURRENT_SOURCE_DIR}/lifecycle
    ${CMAKE_CURRENT_SOURCE_DIR}/ui
)

target_link_libraries(
  ParaViewMCPBridgeCore
  PUBLIC
    ParaView::pqApplicationComponents
    ParaView::pqComponents
    VTK::PythonInterpreter
    ${paraview_mcp_qt_targets}
)

paraview_mcp_configure_target(ParaViewMCPBridgeCore)

paraview_add_plugin(
  ParaViewMCP
  REQUIRED_ON_CLIENT
  VERSION "0.1.5" # x-release-please-version
  UI_INTERFACES ${paraview_mcp_ui_interfaces}
  SOURCES
    ${paraview_mcp_plugin_sources}
    ${paraview_mcp_ui_sources}
  UI_RESOURCES
    resources/ParaViewMCP.qrc
  PYTHON_MODULES
    paraview_mcp_bridge.py
)

target_include_directories(
  ParaViewMCP
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/bridge
    ${CMAKE_CURRENT_SOURCE_DIR}/lifecycle
    ${CMAKE_CURRENT_SOURCE_DIR}/ui
)

target_link_libraries(
  ParaViewMCP
  PRIVATE
    ParaViewMCPBridgeCore
)

paraview_mcp_configure_target(ParaViewMCP)
paraview_mcp_add_format_targets(
  BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
  SOURCES ${paraview_mcp_all_sources}
)
paraview_mcp_add_lint_target(
  BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}"
  SOURCES ${paraview_mcp_lint_sources}
)

set(PARAVIEW_MCP_QT_TEST_TARGET "${paraview_mcp_qt_test_target}" PARENT_SCOPE)
