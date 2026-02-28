#pragma once

#include "IParaViewMCPPythonBridge.h"
#include "ParaViewMCPRequestHandler.h"
#include "ParaViewMCPServerConfig.h"
#include "ParaViewMCPSession.h"

#include <QAbstractSocket>
#include <QObject>

class QTcpServer;
class QTcpSocket;

class ParaViewMCPSocketBridge : public QObject
{
  Q_OBJECT

public:
  explicit ParaViewMCPSocketBridge(IParaViewMCPPythonBridge& pythonBridge,
                                   ParaViewMCPRequestHandler& requestHandler,
                                   QObject* parent = nullptr);

  bool start(const ParaViewMCPServerConfig& config, QString* error = nullptr);
  void stop();

  [[nodiscard]] bool isListening() const;
  [[nodiscard]] bool hasClient() const;
  [[nodiscard]] bool handshakeComplete() const;
  [[nodiscard]] quint16 serverPort() const;
  [[nodiscard]] const ParaViewMCPSession& session() const;

signals:
  void statusChanged(const QString& status);
  void logChanged(const QString& message);

private:
  void setStatus(const QString& status);
  void setLog(const QString& message);
  void onNewConnection();
  void onSocketReadyRead();
  void onSocketDisconnected();
  void onSocketError(QAbstractSocket::SocketError socketError);
  void applyHandlerResult(const ParaViewMCPRequestHandler::Result& result);
  static void sendMessage(QTcpSocket* socket, const QJsonObject& message);
  void closeClientSocket(bool resetSession, bool emitStateUpdate = true);

  QTcpServer* Server = nullptr;
  ParaViewMCPServerConfig Config;
  ParaViewMCPSession Session;
  IParaViewMCPPythonBridge& PythonBridge;
  ParaViewMCPRequestHandler& RequestHandler;
};
