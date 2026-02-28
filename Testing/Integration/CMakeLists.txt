add_subdirectory(Cpp)

set(PARAVIEW_MCP_TEST_PYTHON_EXECUTABLE
  ""
  CACHE FILEPATH
  "Python interpreter used for ParaView MCP Python integration tests"
)

set(paraview_mcp_test_python "${PARAVIEW_MCP_TEST_PYTHON_EXECUTABLE}")
if(NOT paraview_mcp_test_python)
  find_package(Python3 QUIET COMPONENTS Interpreter)
  if(Python3_Interpreter_FOUND)
    set(paraview_mcp_test_python "${Python3_EXECUTABLE}")
  endif()
endif()

if(paraview_mcp_test_python)
  add_test(
    NAME ParaViewMCP.PythonIntegration
    COMMAND
      "${paraview_mcp_test_python}"
      -m
      unittest
      discover
      -s
      "${PROJECT_SOURCE_DIR}/Wrapping/Python/MCPServer/tests"
  )
  set_tests_properties(
    ParaViewMCP.PythonIntegration
    PROPERTIES
      ENVIRONMENT "PYTHONPATH=${PROJECT_SOURCE_DIR}/Wrapping/Python/MCPServer/src"
  )
else()
  message(STATUS "Python interpreter not found; skipping ParaView MCP Python integration ctest")
endif()
