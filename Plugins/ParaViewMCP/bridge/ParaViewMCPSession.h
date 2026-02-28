#pragma once

#include <QByteArray>
#include <QPointer>
#include <QTcpSocket>

class ParaViewMCPSession
{
public:
  void attach(QTcpSocket* socket)
  {
    this->ActiveSocket = socket;
    this->ReadBuffer.clear();
    this->HandshakeComplete = false;
  }

  void clear()
  {
    this->ActiveSocket = nullptr;
    this->ReadBuffer.clear();
    this->HandshakeComplete = false;
  }

  [[nodiscard]] bool hasClient() const
  {
    return this->ActiveSocket != nullptr;
  }

  [[nodiscard]] bool handshakeComplete() const
  {
    return this->HandshakeComplete;
  }

  void setHandshakeComplete(bool value)
  {
    this->HandshakeComplete = value;
  }

  QByteArray& buffer()
  {
    return this->ReadBuffer;
  }

  [[nodiscard]] QTcpSocket* socket() const
  {
    return this->ActiveSocket;
  }

private:
  QPointer<QTcpSocket> ActiveSocket;
  QByteArray ReadBuffer;
  bool HandshakeComplete = false;
};
