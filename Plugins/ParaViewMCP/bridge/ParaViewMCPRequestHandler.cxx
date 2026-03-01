#include "ParaViewMCPRequestHandler.h"

#include "IParaViewMCPPythonBridge.h"
#include "ParaViewMCPProtocol.h"

#include <QJsonArray>
#include <QJsonDocument>

namespace
{
  constexpr const char* PluginVersion = "0.1.0";
}

ParaViewMCPRequestHandler::ParaViewMCPRequestHandler(IParaViewMCPPythonBridge& pythonBridge)
    : PythonBridge(pythonBridge)
{
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::handleMessage(
  const QJsonObject& message, bool handshakeComplete, const QString& authToken)
{
  const QString type = message.value(QStringLiteral("type")).toString();
  if (!handshakeComplete)
  {
    if (type != QStringLiteral("hello"))
    {
      return ParaViewMCPRequestHandler::protocolError(
        QStringLiteral("HANDSHAKE_REQUIRED"),
        QStringLiteral("The first request on a new connection must be 'hello'"));
    }
    return this->handleHello(message, authToken);
  }

  return this->handleCommand(message);
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::busyResult()
{
  return ParaViewMCPRequestHandler::error(QString(),
                                          QStringLiteral("CLIENT_BUSY"),
                                          QStringLiteral("Another client is already connected"));
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::protocolError(const QString& code,
                                                                           const QString& message)
{
  Result result = ParaViewMCPRequestHandler::error(QString(), code, message);
  result.CloseConnection = true;
  result.ResetSession = true;
  return result;
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::handleHello(const QJsonObject& message,
                                                                         const QString& authToken)
{
  const QString requestId = message.value(QStringLiteral("request_id")).toString();
  const int protocolVersion = message.value(QStringLiteral("protocol_version")).toInt(-1);
  if (protocolVersion != ParaViewMCP::ProtocolVersion)
  {
    Result result = ParaViewMCPRequestHandler::error(
      requestId,
      QStringLiteral("PROTOCOL_MISMATCH"),
      QStringLiteral("The requested protocol version is not supported"),
      QJsonObject{
        {"expected", ParaViewMCP::ProtocolVersion},
        {"received", protocolVersion},
      });
    result.CloseConnection = true;
    result.ResetSession = true;
    return result;
  }

  if (message.value(QStringLiteral("auth_token")).toString() != authToken)
  {
    Result result =
      ParaViewMCPRequestHandler::error(requestId,
                                       QStringLiteral("AUTH_FAILED"),
                                       QStringLiteral("The authentication token was rejected"));
    result.CloseConnection = true;
    result.ResetSession = true;
    return result;
  }

  QString pythonError;
  bool pythonReady = this->PythonBridge.initialize(&pythonError);
  QString logMessage;
  if (pythonReady)
  {
    QString resetError;
    if (!this->PythonBridge.resetSession(&resetError))
    {
      pythonReady = false;
      logMessage = resetError;
    }
  }
  else
  {
    logMessage = pythonError;
  }

  Result result =
    ParaViewMCPRequestHandler::success(requestId,
                                       QJsonObject{
                                         {"protocol_version", ParaViewMCP::ProtocolVersion},
                                         {"plugin_version", QString::fromLatin1(PluginVersion)},
                                         {"python_ready", pythonReady},
                                         {"capabilities",
                                          QJsonArray{
                                            QStringLiteral("ping"),
                                            QStringLiteral("execute_python"),
                                            QStringLiteral("inspect_pipeline"),
                                            QStringLiteral("capture_screenshot"),
                                          }},
                                       });
  result.HandshakeCompleted = true;
  result.LogMessage = logMessage;
  return result;
}

ParaViewMCPRequestHandler::Result
ParaViewMCPRequestHandler::handleCommand(const QJsonObject& message)
{
  const QString requestId = message.value(QStringLiteral("request_id")).toString();
  const QString type = message.value(QStringLiteral("type")).toString();
  const QJsonObject params = message.value(QStringLiteral("params")).toObject();

  if (type == QStringLiteral("ping"))
  {
    return ParaViewMCPRequestHandler::success(requestId, QJsonObject{{"ok", true}});
  }

  if (type == QStringLiteral("execute_python"))
  {
    const QString code = params.value(QStringLiteral("code")).toString();
    if (code.isEmpty())
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("INVALID_PARAMS"),
        QStringLiteral("execute_python requires a non-empty 'code' string"));
    }

    QJsonObject result;
    QString errorText;
    if (!this->PythonBridge.executePython(code, &result, &errorText))
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("PYTHON_BRIDGE_ERROR"),
        errorText.isEmpty() ? QStringLiteral("Python execution failed") : errorText);
    }

    Result handlerResult = ParaViewMCPRequestHandler::success(requestId, result);

    QJsonArray historyArray;
    if (this->PythonBridge.getHistory(&historyArray, nullptr))
    {
      handlerResult.HistoryJson =
        QString::fromUtf8(QJsonDocument(historyArray).toJson(QJsonDocument::Compact));
    }
    return handlerResult;
  }

  if (type == QStringLiteral("inspect_pipeline"))
  {
    QJsonObject result;
    QString errorText;
    if (!this->PythonBridge.inspectPipeline(&result, &errorText))
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("PIPELINE_ERROR"),
        errorText.isEmpty() ? QStringLiteral("Unable to inspect the pipeline") : errorText);
    }

    return ParaViewMCPRequestHandler::success(requestId, result);
  }

  if (type == QStringLiteral("capture_screenshot"))
  {
    const int width = params.value(QStringLiteral("width")).toInt(1600);
    const int height = params.value(QStringLiteral("height")).toInt(900);
    QJsonObject result;
    QString errorText;
    if (!this->PythonBridge.captureScreenshot(width, height, &result, &errorText))
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("SCREENSHOT_ERROR"),
        errorText.isEmpty() ? QStringLiteral("Unable to capture a screenshot") : errorText);
    }

    return ParaViewMCPRequestHandler::success(requestId, result);
  }

  if (type == QStringLiteral("get_history"))
  {
    QJsonArray historyArray;
    QString errorText;
    if (!this->PythonBridge.getHistory(&historyArray, &errorText))
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("HISTORY_ERROR"),
        errorText.isEmpty() ? QStringLiteral("Unable to retrieve history") : errorText);
    }

    Result handlerResult =
      ParaViewMCPRequestHandler::success(requestId, QJsonObject{{"history", historyArray}});
    handlerResult.HistoryJson =
      QString::fromUtf8(QJsonDocument(historyArray).toJson(QJsonDocument::Compact));
    return handlerResult;
  }

  if (type == QStringLiteral("restore_snapshot"))
  {
    const int entryId = params.value(QStringLiteral("entry_id")).toInt(-1);
    if (entryId < 1)
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("INVALID_PARAMS"),
        QStringLiteral("restore_snapshot requires a positive 'entry_id' integer"));
    }

    QJsonObject result;
    QString errorText;
    if (!this->PythonBridge.restoreSnapshot(entryId, &result, &errorText))
    {
      return ParaViewMCPRequestHandler::error(
        requestId,
        QStringLiteral("RESTORE_ERROR"),
        errorText.isEmpty() ? QStringLiteral("Unable to restore snapshot") : errorText);
    }

    return ParaViewMCPRequestHandler::success(requestId, result);
  }

  return ParaViewMCPRequestHandler::error(requestId,
                                          QStringLiteral("UNKNOWN_COMMAND"),
                                          QStringLiteral("The requested command is not supported"));
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::success(const QString& requestId,
                                                                     const QJsonObject& result)
{
  Result response;
  response.Response = QJsonObject{
    {"request_id", requestId},
    {"status", QStringLiteral("success")},
    {"result", result},
  };
  return response;
}

ParaViewMCPRequestHandler::Result ParaViewMCPRequestHandler::error(const QString& requestId,
                                                                   const QString& code,
                                                                   const QString& messageText,
                                                                   const QJsonObject& details)
{
  QJsonObject errorObject = {
    {"code", code},
    {"message", messageText},
  };
  if (!details.isEmpty())
  {
    errorObject.insert(QStringLiteral("details"), details);
  }

  Result response;
  response.Response = QJsonObject{
    {"request_id", requestId},
    {"status", QStringLiteral("error")},
    {"error", errorObject},
  };
  return response;
}
