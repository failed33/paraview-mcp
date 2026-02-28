#include "FakeParaViewMCPPythonBridge.h"
#include "ParaViewMCPRequestHandler.h"
#include "ParaViewMCPSocketBridge.h"
#include "TestSocketHelpers.h"

#include <QJsonObject>
#include <QObject>
#include <QTcpSocket>
#include <QtTest>

class TestParaViewMCPSocketBridge : public QObject
{
  Q_OBJECT

private slots:
  void acceptsOneClientAndRejectsTheSecond();
  void malformedFramesCloseTheConnection();
  void helloCompletesTheHandshake();
  void disconnectResetsSessionState();
  void preservesRequestIdsAcrossResponses();
};

void TestParaViewMCPSocketBridge::acceptsOneClientAndRejectsTheSecond()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket firstClient;
  QVERIFY(connectClientSocket(firstClient, bridge.serverPort(), &error));
  QTRY_VERIFY_WITH_TIMEOUT(bridge.hasClient(), 2000);

  QTcpSocket secondClient;
  QVERIFY(connectClientSocket(secondClient, bridge.serverPort(), &error));

  QJsonObject busyResponse;
  QVERIFY(waitForJsonMessage(secondClient, &busyResponse, &error));
  QCOMPARE(
    busyResponse.value(QStringLiteral("error")).toObject().value(QStringLiteral("code")).toString(),
    QStringLiteral("CLIENT_BUSY"));

  bridge.stop();
}

void TestParaViewMCPSocketBridge::malformedFramesCloseTheConnection()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket client;
  QVERIFY(connectClientSocket(client, bridge.serverPort(), &error));
  QTRY_VERIFY_WITH_TIMEOUT(bridge.hasClient(), 2000);

  client.write(ParaViewMCP::encodeMessage(QJsonObject{
    { "request_id", QStringLiteral("hello-1") },
    { "type", QStringLiteral("hello") },
    { "protocol_version", ParaViewMCP::ProtocolVersion },
    { "auth_token", QString() },
  }));
  client.write(QByteArray::fromHex("000000027b7b"));
  client.flush();

  QTRY_VERIFY_WITH_TIMEOUT(!bridge.hasClient(), 2000);
  QVERIFY(bridgeImpl.ResetCalls >= 1);

  bridge.stop();
}

void TestParaViewMCPSocketBridge::helloCompletesTheHandshake()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket client;
  QVERIFY(connectClientSocket(client, bridge.serverPort(), &error));

  writeJsonFrame(client, QJsonObject{
    { "request_id", QStringLiteral("hello-1") },
    { "type", QStringLiteral("hello") },
    { "protocol_version", ParaViewMCP::ProtocolVersion },
    { "auth_token", QString() },
  });

  QJsonObject response;
  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("status")).toString(), QStringLiteral("success"));
  QTRY_VERIFY_WITH_TIMEOUT(bridge.handshakeComplete(), 2000);

  bridge.stop();
}

void TestParaViewMCPSocketBridge::disconnectResetsSessionState()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket client;
  QVERIFY(connectClientSocket(client, bridge.serverPort(), &error));

  writeJsonFrame(client, QJsonObject{
    { "request_id", QStringLiteral("hello-1") },
    { "type", QStringLiteral("hello") },
    { "protocol_version", ParaViewMCP::ProtocolVersion },
    { "auth_token", QString() },
  });

  QJsonObject response;
  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(bridgeImpl.ResetCalls, 1);

  client.disconnectFromHost();
  QTRY_VERIFY_WITH_TIMEOUT(!bridge.hasClient(), 2000);
  QCOMPARE(bridgeImpl.ResetCalls, 2);
  QVERIFY(!bridge.handshakeComplete());

  bridge.stop();
}

void TestParaViewMCPSocketBridge::preservesRequestIdsAcrossResponses()
{
  FakeParaViewMCPPythonBridge bridgeImpl;
  ParaViewMCPRequestHandler handler(bridgeImpl);
  ParaViewMCPSocketBridge bridge(bridgeImpl, handler);

  ParaViewMCPServerConfig config;
  config.Host = QStringLiteral("127.0.0.1");
  config.Port = 0;
  QString error;
  if (!bridge.start(config, &error))
  {
    QSKIP(qPrintable(error));
  }

  QTcpSocket client;
  QVERIFY(connectClientSocket(client, bridge.serverPort(), &error));

  writeJsonFrame(client, QJsonObject{
    { "request_id", QStringLiteral("hello-1") },
    { "type", QStringLiteral("hello") },
    { "protocol_version", ParaViewMCP::ProtocolVersion },
    { "auth_token", QString() },
  });

  QJsonObject response;
  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("request_id")).toString(), QStringLiteral("hello-1"));

  writeJsonFrame(client, QJsonObject{
    { "request_id", QStringLiteral("ping-1") },
    { "type", QStringLiteral("ping") },
    { "params", QJsonObject() },
  });

  QVERIFY(waitForJsonMessage(client, &response, &error));
  QCOMPARE(response.value(QStringLiteral("request_id")).toString(), QStringLiteral("ping-1"));

  bridge.stop();
}

QTEST_MAIN(TestParaViewMCPSocketBridge)

#include "TestParaViewMCPSocketBridge.moc"
