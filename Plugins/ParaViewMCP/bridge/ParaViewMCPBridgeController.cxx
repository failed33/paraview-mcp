#include "ParaViewMCPBridgeController.h"

#include "ParaViewMCPDockWindow.h"

ParaViewMCPBridgeController& ParaViewMCPBridgeController::instance()
{
  static ParaViewMCPBridgeController controller;
  return controller;
}

ParaViewMCPBridgeController::ParaViewMCPBridgeController(QObject* parent)
    : QObject(parent), Config(ParaViewMCPServerConfig::load()), RequestHandler(this->PythonBridge),
      SocketBridge(this->PythonBridge, this->RequestHandler, this)
{
  QObject::connect(&this->SocketBridge,
                   &ParaViewMCPSocketBridge::statusChanged,
                   this,
                   &ParaViewMCPBridgeController::setStatus);
  QObject::connect(&this->SocketBridge,
                   &ParaViewMCPSocketBridge::logChanged,
                   this,
                   &ParaViewMCPBridgeController::setLog);
}

void ParaViewMCPBridgeController::initialize()
{
  if (this->Initialized)
  {
    return;
  }

  this->Initialized = true;
  this->Config = ParaViewMCPServerConfig::load();

  QString pythonError;
  this->PythonBridge.initialize(&pythonError);
  if (!pythonError.isEmpty())
  {
    this->setLog(pythonError);
  }

  this->setStatus(QStringLiteral("Stopped"));
}

void ParaViewMCPBridgeController::shutdown()
{
  if (!this->Initialized)
  {
    return;
  }

  this->stopServer();
  this->PythonBridge.shutdown();
  this->Initialized = false;
}

void ParaViewMCPBridgeController::registerDockWindow(ParaViewMCPDockWindow* dockWindow)
{
  this->DockWindow = dockWindow;
}

void ParaViewMCPBridgeController::showDockWindow()
{
  if (!this->DockWindow)
  {
    return;
  }

  this->DockWindow->show();
  this->DockWindow->raise();
  this->DockWindow->activateWindow();
}

bool ParaViewMCPBridgeController::startServer(const QString& host,
                                              quint16 port,
                                              const QString& authToken)
{
  // Ensure the Python bridge is ready before accepting clients.
  QString pythonError;
  if (!this->PythonBridge.initialize(&pythonError))
  {
    this->setLog(
      QStringLiteral("Python bridge: %1").arg(pythonError.isEmpty()
        ? QStringLiteral("initialization failed")
        : pythonError));
  }

  ParaViewMCPServerConfig requestedConfig = this->Config;
  requestedConfig.Host = host.trimmed();
  requestedConfig.Port = port;
  requestedConfig.AuthToken = authToken;

  if (!this->SocketBridge.start(requestedConfig))
  {
    return false;
  }

  this->Config = requestedConfig;
  this->Config.save();
  return true;
}

void ParaViewMCPBridgeController::stopServer()
{
  this->SocketBridge.stop();
}

QString ParaViewMCPBridgeController::host() const
{
  return this->Config.Host;
}

quint16 ParaViewMCPBridgeController::port() const
{
  return this->Config.Port;
}

bool ParaViewMCPBridgeController::isListening() const
{
  return this->SocketBridge.isListening();
}

bool ParaViewMCPBridgeController::hasClient() const
{
  return this->SocketBridge.hasClient();
}

QString ParaViewMCPBridgeController::lastStatus() const
{
  return this->LastStatus;
}

QString ParaViewMCPBridgeController::lastLog() const
{
  return this->LastLog;
}

void ParaViewMCPBridgeController::setStatus(const QString& status)
{
  this->LastStatus = status;
  emit this->statusChanged(status);
}

void ParaViewMCPBridgeController::setLog(const QString& message)
{
  this->LastLog = message;
  emit this->logChanged(message);
}
