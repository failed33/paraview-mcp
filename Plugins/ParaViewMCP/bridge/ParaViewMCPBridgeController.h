#pragma once

#include "ParaViewMCPSocketBridge.h"
#include "ParaViewMCPRequestHandler.h"
#include "ParaViewMCPServerConfig.h"
#include "ParaViewMCPPythonBridge.h"

#include <QObject>
#include <QPointer>
#include <QString>

class ParaViewMCPPopup;

class ParaViewMCPBridgeController : public QObject
{
  Q_OBJECT

public:
  enum class ServerState
  {
    Stopped,
    Listening,
    Connected,
    Error
  };
  Q_ENUM(ServerState)

  static ParaViewMCPBridgeController& instance();

  void initialize();
  void shutdown();

  void registerPopup(ParaViewMCPPopup* popup);
  void showPopup(QWidget* anchor = nullptr);

  bool startServer(const QString& host, quint16 port, const QString& authToken);
  void stopServer();

  QString host() const;
  quint16 port() const;
  QString authToken() const;
  bool isListening() const;
  bool hasClient() const;
  QString lastStatus() const;
  QString lastLog() const;
  ServerState serverState() const;

signals:
  void statusChanged(const QString& status);
  void logChanged(const QString& message);
  void serverStateChanged(ServerState state);

private:
  explicit ParaViewMCPBridgeController(QObject* parent = nullptr);

  void setStatus(const QString& status);
  void setLog(const QString& message);
  void updateServerState();

  bool Initialized = false;
  ParaViewMCPServerConfig Config;
  QPointer<ParaViewMCPPopup> Popup;
  ServerState CurrentState = ServerState::Stopped;
  QString LastStatus;
  QString LastLog;
  ParaViewMCPPythonBridge PythonBridge;
  ParaViewMCPRequestHandler RequestHandler;
  ParaViewMCPSocketBridge SocketBridge;
};
