#include "ParaViewMCPPythonBridge.h"

#include "vtkNew.h"
#include "vtkPVPythonModule.h"

#include <QtTest>

class TestParaViewMCPPythonBridge : public QObject
{
  Q_OBJECT

private slots:
  void initializesRegisteredModuleInFreshInterpreter();
};

void TestParaViewMCPPythonBridge::initializesRegisteredModuleInFreshInterpreter()
{
  vtkNew<vtkPVPythonModule> module;
  module->SetFullName("paraview_mcp_bridge");
  module->SetSource(R"PY(
import json


def _object_result(*_args):
    return json.dumps({})


def _array_result(*_args):
    return json.dumps([])


bootstrap = _object_result
reset_session = _object_result
execute_python = _object_result
inspect_pipeline = _object_result
capture_screenshot = _object_result
get_history = _array_result
restore_snapshot = _object_result
)PY");
  module->SetIsPackage(0);
  vtkPVPythonModule::RegisterModule(module);

  ParaViewMCPPythonBridge bridge;
  QString error;
  QVERIFY2(bridge.initialize(&error), qPrintable(error));
  QVERIFY(bridge.isReady());
}

QTEST_APPLESS_MAIN(TestParaViewMCPPythonBridge)

#include "TestParaViewMCPPythonBridge.moc"
