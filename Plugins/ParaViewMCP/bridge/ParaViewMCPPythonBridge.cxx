#include "ParaViewMCPPythonBridge.h"

#include "pqPVApplicationCore.h"
#include "pqPythonManager.h"
#include "vtkPythonInterpreter.h"

#ifdef slots
#define PARAVIEW_MCP_RESTORE_QT_SLOTS
#undef slots
#endif
#include <Python.h>
#ifdef PARAVIEW_MCP_RESTORE_QT_SLOTS
#define slots Q_SLOTS
#undef PARAVIEW_MCP_RESTORE_QT_SLOTS
#endif

#include <QByteArray>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QString>

namespace
{
  QString pythonObjectToString(PyObject* value)
  {
    if (value == nullptr)
    {
      return QString();
    }

    PyObject* text = PyObject_Str(value);
    if (text == nullptr)
    {
      PyErr_Clear();
      return QStringLiteral("Unknown Python error");
    }

    const char* utf8 = PyUnicode_AsUTF8(text);
    const QString result = utf8 ? QString::fromUtf8(utf8) : QStringLiteral("Unknown Python error");
    Py_DECREF(text);
    return result;
  }
} // namespace

ParaViewMCPPythonBridge::ParaViewMCPPythonBridge() = default;

ParaViewMCPPythonBridge::~ParaViewMCPPythonBridge()
{
  this->shutdown();
}

bool ParaViewMCPPythonBridge::initialize(QString* error)
{
  if (this->Ready)
  {
    return true;
  }

  bool interpreterReady = false;
  if (auto* appCore = pqPVApplicationCore::instance())
  {
    if (auto* pythonManager = appCore->pythonManager())
    {
      interpreterReady = pythonManager->initializeInterpreter();
    }
  }

  if (!interpreterReady)
  {
    vtkPythonInterpreter::Initialize();
    interpreterReady = vtkPythonInterpreter::IsInitialized() != 0;
  }

  if (!interpreterReady)
  {
    if (error)
    {
      *error = QStringLiteral("Unable to initialize the ParaView Python interpreter");
    }
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  const bool imported = this->importModule(error) && this->cacheFunctions(error);
  if (imported)
  {
    QJsonObject ignored;
    if (!this->callFunction(QStringLiteral("bootstrap"), PyTuple_New(0), &ignored, error))
    {
      this->clearPythonObjects();
      this->Ready = false;
      PyGILState_Release(gilState);
      return false;
    }
    this->Ready = true;
  }
  PyGILState_Release(gilState);

  return this->Ready;
}

void ParaViewMCPPythonBridge::shutdown()
{
  if (!vtkPythonInterpreter::IsInitialized())
  {
    this->Ready = false;
    this->Module = nullptr;
    this->Functions.clear();
    return;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  this->clearPythonObjects();
  this->Ready = false;
  PyGILState_Release(gilState);
}

bool ParaViewMCPPythonBridge::isReady() const
{
  return this->Ready;
}

bool ParaViewMCPPythonBridge::resetSession(QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = PyTuple_New(0);
  QJsonObject ignored;
  const bool ok = this->callFunction(QStringLiteral("reset_session"), args, &ignored, error);
  PyGILState_Release(gilState);
  return ok;
}

bool ParaViewMCPPythonBridge::executePython(const QString& code,
                                            QJsonObject* result,
                                            QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = Py_BuildValue("(s)", code.toUtf8().constData());
  const bool ok = this->callFunction(QStringLiteral("execute_python"), args, result, error);
  PyGILState_Release(gilState);
  return ok;
}

bool ParaViewMCPPythonBridge::inspectPipeline(QJsonObject* result, QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = PyTuple_New(0);
  const bool ok = this->callFunction(QStringLiteral("inspect_pipeline"), args, result, error);
  PyGILState_Release(gilState);
  return ok;
}

bool ParaViewMCPPythonBridge::captureScreenshot(int width,
                                                int height,
                                                QJsonObject* result,
                                                QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = Py_BuildValue("(ii)", width, height);
  const bool ok = this->callFunction(QStringLiteral("capture_screenshot"), args, result, error);
  PyGILState_Release(gilState);
  return ok;
}

bool ParaViewMCPPythonBridge::getHistory(QJsonArray* result, QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();

  PyObject* callable = this->Functions.value(QStringLiteral("get_history"), nullptr);
  if (callable == nullptr)
  {
    if (error)
    {
      *error = QStringLiteral("get_history function not available");
    }
    PyGILState_Release(gilState);
    return false;
  }

  PyObject* args = PyTuple_New(0);
  PyObject* value = PyObject_CallObject(callable, args);
  Py_XDECREF(args);
  if (value == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    PyGILState_Release(gilState);
    return false;
  }

  if (!PyUnicode_Check(value))
  {
    Py_DECREF(value);
    if (error)
    {
      *error = QStringLiteral("get_history did not return a string");
    }
    PyGILState_Release(gilState);
    return false;
  }

  const char* utf8 = PyUnicode_AsUTF8(value);
  QJsonParseError parseError;
  const QJsonDocument document = QJsonDocument::fromJson(QByteArray(utf8), &parseError);
  Py_DECREF(value);
  PyGILState_Release(gilState);

  if (parseError.error != QJsonParseError::NoError || !document.isArray())
  {
    if (error)
    {
      *error = QStringLiteral("get_history returned invalid JSON array");
    }
    return false;
  }

  *result = document.array();
  return true;
}

bool ParaViewMCPPythonBridge::restoreSnapshot(int entryId, QJsonObject* result, QString* error)
{
  if (!this->initialize(error))
  {
    return false;
  }

  PyGILState_STATE gilState = PyGILState_Ensure();
  PyObject* args = Py_BuildValue("(i)", entryId);
  const bool ok = this->callFunction(QStringLiteral("restore_snapshot"), args, result, error);
  PyGILState_Release(gilState);
  return ok;
}

bool ParaViewMCPPythonBridge::importModule(QString* error)
{
  if (this->Module != nullptr)
  {
    return true;
  }

  PyObject* moduleName = PyUnicode_FromString("paraview_mcp_bridge");
  if (moduleName == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    return false;
  }

  this->Module = PyImport_Import(moduleName);
  Py_DECREF(moduleName);

  if (this->Module == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    return false;
  }

  return true;
}

bool ParaViewMCPPythonBridge::cacheFunctions(QString* error)
{
  static const char* functionNames[] = {
    "bootstrap",
    "reset_session",
    "execute_python",
    "inspect_pipeline",
    "capture_screenshot",
    "get_history",
    "restore_snapshot",
  };

  for (const char* functionName : functionNames)
  {
    const QString key = QString::fromUtf8(functionName);
    if (this->Functions.contains(key))
    {
      continue;
    }

    PyObject* callable = PyObject_GetAttrString(this->Module, functionName);
    if (callable == nullptr || !PyCallable_Check(callable))
    {
      Py_XDECREF(callable);
      if (error)
      {
        *error = this->fetchPythonError();
      }
      return false;
    }

    this->Functions.insert(key, callable);
  }

  return true;
}

bool ParaViewMCPPythonBridge::callFunction(const QString& functionName,
                                           PyObject* args,
                                           QJsonObject* result,
                                           QString* error)
{
  if (result == nullptr)
  {
    if (error)
    {
      *error = QStringLiteral("Result object is required");
    }
    Py_XDECREF(args);
    return false;
  }

  PyObject* callable = this->Functions.value(functionName, nullptr);
  if (callable == nullptr)
  {
    if (error)
    {
      *error = QStringLiteral("Requested Python helper is not available");
    }
    Py_XDECREF(args);
    return false;
  }

  PyObject* value = PyObject_CallObject(callable, args);
  Py_XDECREF(args);
  if (value == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    return false;
  }

  const bool ok = this->parseJsonResult(value, result, error);
  Py_DECREF(value);
  return ok;
}

bool ParaViewMCPPythonBridge::parseJsonResult(PyObject* value, QJsonObject* result, QString* error)
{
  if (!PyUnicode_Check(value))
  {
    if (error)
    {
      *error = QStringLiteral("Python helper did not return a JSON string");
    }
    return false;
  }

  const char* utf8 = PyUnicode_AsUTF8(value);
  if (utf8 == nullptr)
  {
    if (error)
    {
      *error = this->fetchPythonError();
    }
    return false;
  }

  QJsonParseError parseError;
  const QJsonDocument document = QJsonDocument::fromJson(QByteArray(utf8), &parseError);
  if (parseError.error != QJsonParseError::NoError || !document.isObject())
  {
    if (error)
    {
      *error = QStringLiteral("Python helper returned invalid JSON");
    }
    return false;
  }

  *result = document.object();
  return true;
}

QString ParaViewMCPPythonBridge::fetchPythonError() const
{
  PyObject* type = nullptr;
  PyObject* value = nullptr;
  PyObject* traceback = nullptr;
  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  QString message = pythonObjectToString(value);
  if (message.isEmpty())
  {
    message = pythonObjectToString(type);
  }
  if (message.isEmpty())
  {
    message = QStringLiteral("Unknown Python bridge failure");
  }

  Py_XDECREF(type);
  Py_XDECREF(value);
  Py_XDECREF(traceback);
  return message;
}

void ParaViewMCPPythonBridge::clearPythonObjects()
{
  for (auto it = this->Functions.begin(); it != this->Functions.end(); ++it)
  {
    Py_XDECREF(it.value());
  }
  this->Functions.clear();

  Py_XDECREF(this->Module);
  this->Module = nullptr;
}
