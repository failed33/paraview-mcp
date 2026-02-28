#include "ParaViewMCPProtocol.h"

#include <QByteArray>
#include <QJsonObject>
#include <QList>
#include <QObject>
#include <QtTest>

class TestParaViewMCPProtocol : public QObject
{
  Q_OBJECT

private slots:
  void encodesAndDecodesSingleFrame();
  void decodesBackToBackFrames();
  void waitsForPartialFrames();
  void rejectsOversizedFrames();
  void rejectsMalformedJson();
  void detectsLoopbackHosts();
};

void TestParaViewMCPProtocol::encodesAndDecodesSingleFrame()
{
  const QJsonObject payload{
    { "request_id", QStringLiteral("one") },
    { "type", QStringLiteral("ping") },
  };

  QByteArray buffer = ParaViewMCP::encodeMessage(payload);
  QList<QJsonObject> messages;
  QString error;

  QVERIFY(ParaViewMCP::tryExtractMessages(buffer, messages, &error));
  QVERIFY(error.isEmpty());
  QCOMPARE(messages.size(), 1);
  QCOMPARE(messages.front(), payload);
  QVERIFY(buffer.isEmpty());
}

void TestParaViewMCPProtocol::decodesBackToBackFrames()
{
  const QJsonObject first{
    { "request_id", QStringLiteral("one") },
    { "type", QStringLiteral("ping") },
  };
  const QJsonObject second{
    { "request_id", QStringLiteral("two") },
    { "type", QStringLiteral("ping") },
  };

  QByteArray buffer = ParaViewMCP::encodeMessage(first) + ParaViewMCP::encodeMessage(second);
  QList<QJsonObject> messages;

  QVERIFY(ParaViewMCP::tryExtractMessages(buffer, messages, nullptr));
  QCOMPARE(messages.size(), 2);
  QCOMPARE(messages.at(0), first);
  QCOMPARE(messages.at(1), second);
}

void TestParaViewMCPProtocol::waitsForPartialFrames()
{
  const QJsonObject payload{
    { "request_id", QStringLiteral("one") },
    { "type", QStringLiteral("ping") },
    { "params", QJsonObject{ { "value", 42 } } },
  };

  const QByteArray encoded = ParaViewMCP::encodeMessage(payload);
  QByteArray buffer = encoded.left(5);
  QList<QJsonObject> messages;

  QVERIFY(ParaViewMCP::tryExtractMessages(buffer, messages, nullptr));
  QVERIFY(messages.isEmpty());

  buffer.append(encoded.mid(5));
  QVERIFY(ParaViewMCP::tryExtractMessages(buffer, messages, nullptr));
  QCOMPARE(messages.size(), 1);
  QCOMPARE(messages.front(), payload);
}

void TestParaViewMCPProtocol::rejectsOversizedFrames()
{
  QByteArray buffer(4, '\0');
  qToBigEndian<quint32>(ParaViewMCP::MaxFrameBytes + 1u, buffer.data());

  QList<QJsonObject> messages;
  QString error;

  QVERIFY(!ParaViewMCP::tryExtractMessages(buffer, messages, &error));
  QCOMPARE(error, QStringLiteral("Incoming frame exceeds the maximum allowed size"));
}

void TestParaViewMCPProtocol::rejectsMalformedJson()
{
  const QByteArray badPayload("{not-json");
  QByteArray buffer;
  buffer.resize(4 + badPayload.size());
  qToBigEndian<quint32>(static_cast<quint32>(badPayload.size()), buffer.data());
  std::copy(badPayload.cbegin(), badPayload.cend(), buffer.begin() + 4);

  QList<QJsonObject> messages;
  QString error;

  QVERIFY(!ParaViewMCP::tryExtractMessages(buffer, messages, &error));
  QCOMPARE(error, QStringLiteral("Received malformed JSON payload"));
}

void TestParaViewMCPProtocol::detectsLoopbackHosts()
{
  QCOMPARE(ParaViewMCP::defaultHost(), QStringLiteral("127.0.0.1"));
  QVERIFY(ParaViewMCP::isLoopbackHost(QStringLiteral("127.0.0.1")));
  QVERIFY(ParaViewMCP::isLoopbackHost(QStringLiteral("localhost")));
  QVERIFY(ParaViewMCP::isLoopbackHost(QStringLiteral("::1")));
  QVERIFY(!ParaViewMCP::isLoopbackHost(QStringLiteral("0.0.0.0")));
}

QTEST_APPLESS_MAIN(TestParaViewMCPProtocol)

#include "TestParaViewMCPProtocol.moc"
