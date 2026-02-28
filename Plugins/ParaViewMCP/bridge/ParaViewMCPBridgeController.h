#pragma once

#include "ParaViewMCPSocketBridge.h"
#include "ParaViewMCPRequestHandler.h"
#include "ParaViewMCPServerConfig.h"
#include "ParaViewMCPPythonBridge.h"

#include <QObject>
#include <QPointer>
#include <QString>

class ParaViewMCPDockWindow;

class ParaViewMCPBridgeController : public QObject
{
  Q_OBJECT

public:
  static ParaViewMCPBridgeController& instance();

  void initialize();
  void shutdown();

  void registerDockWindow(ParaViewMCPDockWindow* dockWindow);
  void showDockWindow();

  bool startServer(const QString& host, quint16 port, const QString& authToken);
  void stopServer();

  QString host() const;
  quint16 port() const;
  bool isListening() const;
  bool hasClient() const;
  QString lastStatus() const;
  QString lastLog() const;

signals:
  void statusChanged(const QString& status);
  void logChanged(const QString& message);

private:
  explicit ParaViewMCPBridgeController(QObject* parent = nullptr);

  void setStatus(const QString& status);
  void setLog(const QString& message);

  bool Initialized = false;
  ParaViewMCPServerConfig Config;
  QPointer<ParaViewMCPDockWindow> DockWindow;
  QString LastStatus;
  QString LastLog;
  ParaViewMCPPythonBridge PythonBridge;
  ParaViewMCPRequestHandler RequestHandler;
  ParaViewMCPSocketBridge SocketBridge;
};
