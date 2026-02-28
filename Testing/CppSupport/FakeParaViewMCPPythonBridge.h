#pragma once

#include "IParaViewMCPPythonBridge.h"

class FakeParaViewMCPPythonBridge : public IParaViewMCPPythonBridge
{
public:
  bool InitializeResult = true;
  bool Ready = true;
  bool ResetResult = true;
  bool ExecuteResult = true;
  bool InspectResult = true;
  bool ScreenshotResult = true;

  QString InitializeError;
  QString ResetError;
  QString ExecuteError;
  QString InspectError;
  QString ScreenshotError;

  QJsonObject ExecutePayload = QJsonObject{ { "ok", true } };
  QJsonObject InspectPayload = QJsonObject{ { "count", 0 } };
  QJsonObject ScreenshotPayload = QJsonObject{
    { "format", QStringLiteral("png") },
    { "image_data", QStringLiteral("ZmFrZQ==") },
  };

  int ResetCalls = 0;
  int ExecuteCalls = 0;
  int InspectCalls = 0;
  int ScreenshotCalls = 0;
  QString LastCode;
  int LastWidth = 0;
  int LastHeight = 0;

  bool initialize(QString* error = nullptr) override
  {
    if (error != nullptr && !this->InitializeResult)
    {
      *error = this->InitializeError;
    }
    this->Ready = this->InitializeResult;
    return this->InitializeResult;
  }

  void shutdown() override
  {
    this->Ready = false;
  }

  [[nodiscard]] bool isReady() const override
  {
    return this->Ready;
  }

  bool resetSession(QString* error = nullptr) override
  {
    ++this->ResetCalls;
    if (error != nullptr && !this->ResetResult)
    {
      *error = this->ResetError;
    }
    return this->ResetResult;
  }

  bool executePython(
    const QString& code,
    QJsonObject* result,
    QString* error = nullptr) override
  {
    ++this->ExecuteCalls;
    this->LastCode = code;
    if (!this->ExecuteResult)
    {
      if (error != nullptr)
      {
        *error = this->ExecuteError;
      }
      return false;
    }
    if (result != nullptr)
    {
      *result = this->ExecutePayload;
    }
    return true;
  }

  bool inspectPipeline(QJsonObject* result, QString* error = nullptr) override
  {
    ++this->InspectCalls;
    if (!this->InspectResult)
    {
      if (error != nullptr)
      {
        *error = this->InspectError;
      }
      return false;
    }
    if (result != nullptr)
    {
      *result = this->InspectPayload;
    }
    return true;
  }

  bool captureScreenshot(
    int width,
    int height,
    QJsonObject* result,
    QString* error = nullptr) override
  {
    ++this->ScreenshotCalls;
    this->LastWidth = width;
    this->LastHeight = height;
    if (!this->ScreenshotResult)
    {
      if (error != nullptr)
      {
        *error = this->ScreenshotError;
      }
      return false;
    }
    if (result != nullptr)
    {
      *result = this->ScreenshotPayload;
    }
    return true;
  }
};
