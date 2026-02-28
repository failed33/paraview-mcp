#pragma once

#include "ParaViewMCPProtocol.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QHostAddress>
#include <QJsonObject>
#include <QList>
#include <QString>
#include <QTcpSocket>
#include <QTest>

inline bool
connectClientSocket(QTcpSocket& socket, quint16 port, QString* error, int timeoutMs = 5000)
{
  socket.connectToHost(QHostAddress::LocalHost, port);

  QElapsedTimer timer;
  timer.start();
  while (timer.elapsed() < timeoutMs)
  {
    QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
    if (socket.state() == QAbstractSocket::ConnectedState)
    {
      return true;
    }
    QTest::qWait(10);
  }

  if (error != nullptr)
  {
    *error = QStringLiteral("Timed out waiting for the test socket to connect");
  }
  return false;
}

inline void writeJsonFrame(QTcpSocket& socket, const QJsonObject& message)
{
  socket.write(ParaViewMCP::encodeMessage(message));
  socket.flush();
}

inline bool
waitForJsonMessage(QTcpSocket& socket, QJsonObject* message, QString* error, int timeoutMs = 2000)
{
  QByteArray buffer;
  QList<QJsonObject> messages;
  QElapsedTimer timer;
  timer.start();

  while (timer.elapsed() < timeoutMs)
  {
    QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
    const QByteArray chunk = socket.readAll();
    if (!chunk.isEmpty())
    {
      buffer.append(chunk);
      QString parseError;
      if (!ParaViewMCP::tryExtractMessages(buffer, messages, &parseError))
      {
        if (error != nullptr)
        {
          *error = parseError;
        }
        return false;
      }

      if (!messages.isEmpty())
      {
        if (message != nullptr)
        {
          *message = messages.front();
        }
        return true;
      }
    }

    QTest::qWait(10);
  }

  if (error != nullptr)
  {
    *error = QStringLiteral("Timed out waiting for a framed JSON message");
  }
  return false;
}
