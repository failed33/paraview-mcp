#pragma once

#include <algorithm>

#include <QByteArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QList>
#include <QString>
#include <QtEndian>

namespace ParaViewMCP
{
  inline constexpr int ProtocolVersion = 2;
  inline constexpr quint32 MaxFrameBytes = 25u * 1024u * 1024u;
  inline constexpr quint16 DefaultPort = 9877;

  inline QString defaultHost()
  {
    return QStringLiteral("127.0.0.1");
  }

  inline bool isLoopbackHost(const QString& host)
  {
    const QString normalized = host.trimmed().toLower();
    return normalized == QStringLiteral("127.0.0.1") || normalized == QStringLiteral("localhost") ||
           normalized == QStringLiteral("::1");
  }

  inline QByteArray encodeMessage(const QJsonObject& message)
  {
    const QByteArray payload = QJsonDocument(message).toJson(QJsonDocument::JsonFormat::Compact);
    QByteArray frame;
    frame.resize(4 + payload.size());
    qToBigEndian<quint32>(static_cast<quint32>(payload.size()), frame.data());
    std::copy(payload.cbegin(), payload.cend(), frame.begin() + 4);
    return frame;
  }

  inline bool tryExtractMessages(QByteArray& buffer, QList<QJsonObject>& messages, QString* error)
  {
    while (true)
    {
      if (buffer.size() < 4)
      {
        return true;
      }

      const quint32 frameLength =
        qFromBigEndian<quint32>(reinterpret_cast<const uchar*>(buffer.constData()));
      if (frameLength > MaxFrameBytes)
      {
        if (error)
        {
          *error = QStringLiteral("Incoming frame exceeds the maximum allowed size");
        }
        return false;
      }

      const qsizetype totalLength = 4 + static_cast<qsizetype>(frameLength);
      if (buffer.size() < totalLength)
      {
        return true;
      }

      const QByteArray payload = buffer.mid(4, frameLength);
      buffer.remove(0, totalLength);

      QJsonParseError parseError;
      const QJsonDocument document = QJsonDocument::fromJson(payload, &parseError);
      if (parseError.error != QJsonParseError::NoError || !document.isObject())
      {
        if (error)
        {
          *error = QStringLiteral("Received malformed JSON payload");
        }
        return false;
      }

      messages.push_back(document.object());
    }
  }
} // namespace ParaViewMCP
