#pragma once

#include <QJsonObject>
#include <QString>

class IParaViewMCPPythonBridge
{
public:
  virtual ~IParaViewMCPPythonBridge() = default;

  virtual bool initialize(QString* error = nullptr) = 0;
  virtual void shutdown() = 0;

  [[nodiscard]] virtual bool isReady() const = 0;
  virtual bool resetSession(QString* error = nullptr) = 0;
  virtual bool
  executePython(const QString& code, QJsonObject* result, QString* error = nullptr) = 0;
  virtual bool inspectPipeline(QJsonObject* result, QString* error = nullptr) = 0;
  virtual bool
  captureScreenshot(int width, int height, QJsonObject* result, QString* error = nullptr) = 0;
};
