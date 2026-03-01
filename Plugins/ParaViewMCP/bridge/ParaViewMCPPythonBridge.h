#pragma once

#include "IParaViewMCPPythonBridge.h"

#include <QHash>

struct _object;
using PyObject = _object;

class ParaViewMCPPythonBridge : public IParaViewMCPPythonBridge
{
public:
  ParaViewMCPPythonBridge();
  ~ParaViewMCPPythonBridge();

  bool initialize(QString* error = nullptr) override;
  void shutdown() override;

  [[nodiscard]] bool isReady() const override;
  bool resetSession(QString* error = nullptr) override;
  bool executePython(const QString& code, QJsonObject* result, QString* error = nullptr) override;
  bool inspectPipeline(QJsonObject* result, QString* error = nullptr) override;
  bool
  captureScreenshot(int width, int height, QJsonObject* result, QString* error = nullptr) override;
  bool getHistory(QJsonArray* result, QString* error = nullptr) override;
  bool restoreSnapshot(int entryId, QJsonObject* result, QString* error = nullptr) override;

private:
  bool importModule(QString* error);
  bool cacheFunctions(QString* error);
  bool
  callFunction(const QString& functionName, PyObject* args, QJsonObject* result, QString* error);
  bool parseJsonResult(PyObject* value, QJsonObject* result, QString* error);
  QString fetchPythonError() const;
  void clearPythonObjects();

  bool Ready = false;
  PyObject* Module = nullptr;
  QHash<QString, PyObject*> Functions;
};
