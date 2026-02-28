#pragma once

#include "ParaViewMCPProtocol.h"

#include <QHostAddress>
#include <QSettings>
#include <QString>

struct ParaViewMCPServerConfig
{
  QString Host = ParaViewMCP::defaultHost();
  quint16 Port = ParaViewMCP::DefaultPort;
  QString AuthToken;

  static ParaViewMCPServerConfig load()
  {
    QSettings settings;
    ParaViewMCPServerConfig config;
    config.Host = settings.value(QStringLiteral("ParaViewMCP/ListenHost"), config.Host).toString();
    const uint storedPort =
      settings.value(QStringLiteral("ParaViewMCP/ListenPort"), static_cast<int>(config.Port))
        .toUInt();
    if (storedPort > 0 && storedPort <= 65535u)
    {
      config.Port = static_cast<quint16>(storedPort);
    }
    if (config.Host.isEmpty())
    {
      config.Host = ParaViewMCP::defaultHost();
    }
    if (config.Port == 0)
    {
      config.Port = ParaViewMCP::DefaultPort;
    }
    return config;
  }

  void save() const
  {
    QSettings settings;
    settings.setValue(QStringLiteral("ParaViewMCP/ListenHost"), this->Host);
    settings.setValue(QStringLiteral("ParaViewMCP/ListenPort"), this->Port);
  }

  bool validateForListen(QHostAddress* address, QString* error) const
  {
    const QString trimmedHost = this->Host.trimmed();
    if (trimmedHost.isEmpty())
    {
      if (error)
      {
        *error = QStringLiteral("Listen host must not be empty");
      }
      return false;
    }

    if (!ParaViewMCP::isLoopbackHost(trimmedHost) && this->AuthToken.trimmed().isEmpty())
    {
      if (error)
      {
        *error = QStringLiteral("A non-loopback bind address requires an authentication token");
      }
      return false;
    }

    if (trimmedHost == QStringLiteral("localhost"))
    {
      if (address)
      {
        *address = QHostAddress(QHostAddress::LocalHost);
      }
      return true;
    }

    QHostAddress parsedAddress;
    if (!parsedAddress.setAddress(trimmedHost))
    {
      if (error)
      {
        *error = QStringLiteral("Listen host must be 'localhost' or a literal IP address");
      }
      return false;
    }

    if (address)
    {
      *address = parsedAddress;
    }
    return true;
  }
};
