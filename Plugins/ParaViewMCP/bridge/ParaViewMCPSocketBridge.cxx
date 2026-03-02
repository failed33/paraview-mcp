#include "ParaViewMCPSocketBridge.h"

#include "ParaViewMCPProtocol.h"

#include <QList>
#include <QTcpServer>
#include <QTcpSocket>

ParaViewMCPSocketBridge::ParaViewMCPSocketBridge(IParaViewMCPPythonBridge& pythonBridge,
                                                 ParaViewMCPRequestHandler& requestHandler,
                                                 QObject* parent)
    : QObject(parent), PythonBridge(pythonBridge), RequestHandler(requestHandler)
{
}

bool ParaViewMCPSocketBridge::start(const ParaViewMCPServerConfig& config, QString* error)
{
  QHostAddress address;
  QString listenError;
  if (!config.validateForListen(&address, &listenError))
  {
    if (error != nullptr)
    {
      *error = listenError;
    }
    this->setStatus(QStringLiteral("Error"));
    this->setLog(listenError);
    return false;
  }

  if (this->Server == nullptr)
  {
    this->Server = new QTcpServer(this);
    QObject::connect(
      this->Server, &QTcpServer::newConnection, this, &ParaViewMCPSocketBridge::onNewConnection);
  }

  if (this->Server->isListening())
  {
    this->stop();
  }

  if (!this->Server->listen(address, config.Port))
  {
    const QString serverError = this->Server->errorString();
    if (error != nullptr)
    {
      *error = serverError;
    }
    this->setStatus(QStringLiteral("Error"));
    this->setLog(serverError);
    return false;
  }

  this->Config = config;
  this->setStatus(QStringLiteral("Listening"));
  this->setLog(
    QStringLiteral("Listening on %1:%2").arg(this->Config.Host).arg(this->Server->serverPort()));
  return true;
}

void ParaViewMCPSocketBridge::stop()
{
  if (this->Server != nullptr && this->Server->isListening())
  {
    this->Server->close();
  }
  this->closeClientSocket(true, false);
  this->setStatus(QStringLiteral("Stopped"));
}

bool ParaViewMCPSocketBridge::isListening() const
{
  return this->Server != nullptr && this->Server->isListening();
}

bool ParaViewMCPSocketBridge::hasClient() const
{
  return this->Session.hasClient();
}

bool ParaViewMCPSocketBridge::handshakeComplete() const
{
  return this->Session.handshakeComplete();
}

quint16 ParaViewMCPSocketBridge::serverPort() const
{
  return this->Server != nullptr ? this->Server->serverPort() : 0;
}

const ParaViewMCPSession& ParaViewMCPSocketBridge::session() const
{
  return this->Session;
}

void ParaViewMCPSocketBridge::setStatus(const QString& status)
{
  emit this->statusChanged(status);
}

void ParaViewMCPSocketBridge::setLog(const QString& message)
{
  emit this->logChanged(message);
}

void ParaViewMCPSocketBridge::onNewConnection()
{
  if (this->Server == nullptr)
  {
    return;
  }

  while (this->Server->hasPendingConnections())
  {
    QTcpSocket* socket = this->Server->nextPendingConnection();
    if (socket == nullptr)
    {
      continue;
    }

    if (this->Session.hasClient())
    {
      const auto result = ParaViewMCPRequestHandler::busyResult();
      ParaViewMCPSocketBridge::sendMessage(socket, result.Response);
      socket->disconnectFromHost();
      socket->deleteLater();
      continue;
    }

    this->Session.attach(socket);

    QObject::connect(
      socket, &QTcpSocket::readyRead, this, &ParaViewMCPSocketBridge::onSocketReadyRead);
    QObject::connect(
      socket, &QTcpSocket::disconnected, this, &ParaViewMCPSocketBridge::onSocketDisconnected);
    QObject::connect(
      socket, &QTcpSocket::errorOccurred, this, &ParaViewMCPSocketBridge::onSocketError);

    this->setStatus(QStringLiteral("Client connected"));
    this->setLog(QStringLiteral("Client connected from %1").arg(socket->peerAddress().toString()));
  }
}

void ParaViewMCPSocketBridge::onSocketReadyRead()
{
  QTcpSocket* socket = this->Session.socket();
  if (socket == nullptr)
  {
    return;
  }

  this->Session.buffer().append(socket->readAll());

  QList<QJsonObject> messages;
  QString parseError;
  if (!ParaViewMCP::tryExtractMessages(this->Session.buffer(), messages, &parseError))
  {
    this->applyHandlerResult(
      ParaViewMCPRequestHandler::protocolError(QStringLiteral("PROTOCOL_ERROR"), parseError));
    return;
  }

  for (const QJsonObject& message : messages)
  {
    this->applyHandlerResult(this->RequestHandler.handleMessage(
      message, this->Session.handshakeComplete(), this->Config.AuthToken));
    if (!this->Session.hasClient())
    {
      return;
    }
  }
}

void ParaViewMCPSocketBridge::onSocketDisconnected()
{
  this->closeClientSocket(true);
}

void ParaViewMCPSocketBridge::onSocketError(QAbstractSocket::SocketError socketError)
{
  Q_UNUSED(socketError);

  if (this->Session.socket() != nullptr)
  {
    this->setLog(this->Session.socket()->errorString());
  }
}

void ParaViewMCPSocketBridge::applyHandlerResult(const ParaViewMCPRequestHandler::Result& result)
{
  if (!result.LogMessage.isEmpty())
  {
    this->setLog(result.LogMessage);
  }

  if (!result.HistoryJson.isEmpty())
  {
    emit this->historyChanged(result.HistoryJson);
  }

  if (!result.Response.isEmpty())
  {
    ParaViewMCPSocketBridge::sendMessage(this->Session.socket(), result.Response);
  }

  if (result.HandshakeCompleted)
  {
    this->Session.setHandshakeComplete(true);
  }

  if (result.CloseConnection)
  {
    this->closeClientSocket(result.ResetSession);
  }
}

void ParaViewMCPSocketBridge::sendMessage(QTcpSocket* socket, const QJsonObject& message)
{
  if (socket == nullptr)
  {
    return;
  }

  socket->write(ParaViewMCP::encodeMessage(message));
  socket->flush();
}

void ParaViewMCPSocketBridge::closeClientSocket(bool resetSession, bool emitStateUpdate)
{
  const bool listening = this->isListening();
  QTcpSocket* socket = this->Session.socket();
  this->Session.clear();

  if (socket != nullptr)
  {
    QObject::disconnect(socket, nullptr, this, nullptr);
    socket->close();
    socket->deleteLater();
  }

  if (resetSession && this->PythonBridge.isReady())
  {
    this->PythonBridge.resetSession();
  }

  if (emitStateUpdate)
  {
    this->setStatus(listening ? QStringLiteral("Listening") : QStringLiteral("Stopped"));
  }
}
