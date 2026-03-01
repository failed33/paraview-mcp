#pragma once

#include <QJsonObject>
#include <QString>

class IParaViewMCPPythonBridge;

class ParaViewMCPRequestHandler
{
public:
  struct Result
  {
    QJsonObject Response;
    bool CloseConnection = false;
    bool ResetSession = false;
    bool HandshakeCompleted = false;
    QString LogMessage;
    QString HistoryJson;
  };

  explicit ParaViewMCPRequestHandler(IParaViewMCPPythonBridge& pythonBridge);

  Result
  handleMessage(const QJsonObject& message, bool handshakeComplete, const QString& authToken);

  static Result busyResult();
  static Result protocolError(const QString& code, const QString& message);

private:
  Result handleHello(const QJsonObject& message, const QString& authToken);
  Result handleCommand(const QJsonObject& message);

  static Result success(const QString& requestId, const QJsonObject& result);
  static Result error(const QString& requestId,
                      const QString& code,
                      const QString& messageText,
                      const QJsonObject& details = QJsonObject());

  IParaViewMCPPythonBridge& PythonBridge;
};
